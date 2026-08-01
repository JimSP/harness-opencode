"""Gate Gherkin — valida .feature (sintaxe + tag @req + scenario outline).

Usa `gherkin-official` (parser canônico do Cucumber) que aceita múltiplos
idiomas via `# language: pt`. Roda sobre o artefato ``artifacts.feature`` da
feature (criado pelo subagent ehq-bdd).

Config lido do [gate.gherkin] do .engineer-hq.toml:
- require_format (bool): parse OK + ≥1 Feature + ≥1 Scenario
- require_scenario_outline (bool): ≥1 Scenario Outline com Examples
- require_req_ref (bool): todo Scenario tem tag @req:<id>
"""
from __future__ import annotations

import re
from pathlib import Path

from gherkin.parser import Parser
from gherkin.token_scanner import TokenScanner  # noqa: F401 (garante import exposto)

from .base import Issue, GateResult, fail, pass_

_REQ_TAG_RE = re.compile(r"@req:(\S+)")
_REQUIRED_STEPS = {"given", "when", "then"}


def _walk_scenarios(parse_out: dict) -> list[dict]:
    """Extrai lista de scenarios (inclui outlines) com {name, tags, is_outline, steps}."""
    scenarios: list[dict] = []
    feature = parse_out.get("feature", {})
    for child in feature.get("children", []):
        sc = child.get("scenario") or child.get("background")
        if not sc or "name" not in sc:
            continue
        scenarios.append(
            {
                "name": sc.get("name", ""),
                "tags": [t.get("name", "") for t in sc.get("tags", [])],
                "is_outline": sc.get("keyword", "").lower().startswith("scenario outline")
                or sc.get("keyword", "").lower().startswith("esquema")
                or sc.get("examples", []) != [],
                "has_examples": bool(sc.get("examples")),
                "steps": [(s.get("keyword", "").strip().lower(), s.get("text", "")) for s in sc.get("steps", [])],
                "location": sc.get("location", {}).get("line"),
            }
        )
    return scenarios


def _check_req_ref(scenarios: list[dict]) -> list[Issue]:
    issues: list[Issue] = []
    for sc in scenarios:
        tags = sc["tags"]
        refs = [t for t in tags if _REQ_TAG_RE.match(t)]
        if not refs:
            issues.append(
                Issue(
                    severity="error",
                    code="GHERKIN_NO_REQ_REF",
                    message=f"Scenario '{sc['name']}' sem tag @req:<id>.",
                    line=sc["location"],
                )
            )
    return issues


def _check_outline(scenarios: list[dict]) -> list[Issue]:
    issues: list[Issue] = []
    outlines = [s for s in scenarios if s["is_outline"]]
    if not outlines:
        issues.append(
            Issue(
                severity="warning",
                code="GHERKIN_NO_OUTLINE",
                message="Nenhum Scenario Outline. Considere adicionar um para casos de borda.",
            )
        )
    else:
        for o in outlines:
            if not o["has_examples"]:
                issues.append(
                    Issue(
                        severity="error",
                        code="GHERKIN_OUTLINE_NO_EXAMPLES",
                        message=f"Scenario Outline '{o['name']}' sem Examples.",
                        line=o["location"],
                    )
                )
    return issues


def _check_steps(scenarios: list[dict]) -> list[Issue]:
    """Verifica presença mínima Given/When/Then em cada cenário."""
    issues: list[Issue] = []
    # normaliza keywords para ignorar idioma (usando lowercase + prefix)
    def _kw(kw: str) -> str:
        k = kw.strip().lower()
        if k.startswith("dado") or k == "given":
            return "given"
        if k.startswith("quando") or k == "when":
            return "when"
        if k.startswith("entao") or k.startswith("então") or k == "then":
            return "then"
        # '*' é wildcard aceito pelo gherkin
        if k == "*":
            return "given"  # treat wildcard as given/when/then indistintamente
        return k

    for sc in scenarios:
        present = set()
        for raw_kw, _ in sc["steps"]:
            present.add(_kw(raw_kw))
        missing = _REQUIRED_STEPS - present
        if missing:
            issues.append(
                Issue(
                    severity="error",
                    code="GHERKIN_MISSING_STEPS",
                    message=f"Scenario '{sc['name']}' sem passos({','.join(sorted(missing))}).",
                    line=sc["location"],
                )
            )
    return issues


# ---- API pública ------------------------------------------------------------


def run(feature_path: Path, config: dict | None = None) -> GateResult:
    cfg = config or {}
    require_format = bool(cfg.get("require_format", True))
    require_outline = bool(cfg.get("require_scenario_outline", True))
    require_req_ref = bool(cfg.get("require_req_ref", True))

    if not feature_path.exists():
        return fail(
            "gherkin",
            "bdd",
            [Issue(
                severity="error",
                code="GHERKIN_FILE_MISSING",
                message=f"Arquivo .feature ausente: {feature_path}",
            )],
        )

    text = feature_path.read_text(encoding="utf-8")

    issues: list[Issue] = []
    details: dict = {"file": str(feature_path)}

    # 1) parse (sintaxe)
    parse_out: dict | None = None
    if require_format:
        try:
            parse_out = Parser().parse(text)
        except Exception as exc:
            return fail(
                "gherkin",
                "bdd",
                [Issue(
                    severity="error",
                    code="GHERKIN_PARSE_ERROR",
                    message=f"Sintaxe Gherkin inválida: {exc}",
                )],
            )
        feature = parse_out.get("feature") or {}
        name = feature.get("name", "")
        if not name:
            issues.append(Issue(
                severity="error", code="GHERKIN_NO_FEATURE_NAME",
                message="Feature sem nome.",
            ))
        scenarios = _walk_scenarios(parse_out)
        if not scenarios:
            issues.append(Issue(
                severity="error", code="GHERKIN_NO_SCENARIOS",
                message="Nenhum Scenario/Scenario Outline encontrado.",
            ))
        details["scenarios_count"] = len(scenarios)
        details["feature_name"] = name

    if parse_out is not None and scenarios:
        # 2) passos Given/When/Then
        issues.extend(_check_steps(scenarios))
        # 3) req_ref (tag @req)
        if require_req_ref:
            issues.extend(_check_req_ref(scenarios))
            details["req_refs"] = sum(1 for s in scenarios for t in s["tags"] if _REQ_TAG_RE.match(t))
        # 4) scenario outline
        if require_outline:
            issues.extend(_check_outline(scenarios))
            details["outlines_count"] = sum(1 for s in scenarios if s["is_outline"])

    has_errors = any(i.severity == "error" for i in issues)
    details["issues_count"] = len(issues)

    if not has_errors:
        return pass_("gherkin", "bdd", details, issues)
    return fail("gherkin", "bdd", issues, details)
