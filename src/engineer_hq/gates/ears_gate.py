"""Gate EARS — valida .req.md (requisitos em EARS + seção DoD).

Formas EARS canônicas reconhecidas:
  1. Ubíquo:      "O sistema deve <resposta>."
  2. Evento:      "Quando <gatilho>, o sistema deve <resposta>."
  3. Estado:      "Enquanto <estado>, o sistema deve <resposta>."
  4. Opcional:    "Onde <feature>, o sistema deve <resposta>."
  5. Incondicional: "O sistema deve <resposta>." (sem pré-condição)

Variantes aceitas: "deve"/"shall", singular/plural ("sistema"/"sistemas"),
português e inglês. Detecção: pelo menos UMA sentença EARS válida dentro da
seção `## Requisito`. Adjetivos ambíguos (lista negra) geram issues se
`require_unambiguous=true`. Seção `## Critérios de Aceite (DoD)` com checklist
mínimo se `require_dod_section=true`.
"""
from __future__ import annotations

import re
from pathlib import Path

from .base import Issue, GateResult, fail, pass_

# ---- Formas EARS (regex multiline, case-insensitive pt+en) -----------------

# Pré-condições aceitam "Quando/Enquanto/Onde" (pt) e "When/While/Where" (en).
_PRECOND = (
    r"(?:"
    r"(?:Quando|When)\s+.+?,\s*"
    r"|(?:Enquanto|While)\s+.+?,\s*"
    r"|(?:Onde|Where)\s+.+?,\s*"
    r")?"
)
# Sujeito: "O sistema"/"Os sistemas"/"The system"/"The systems"
_SUBJECT = r"(?:O\s+sistema|Os\s+sistemas|The\s+systems?)\s+"
# Verbo modal: deve/devem/shall/should (must optional em ing)
_MODAL = r"(?:deve|devem|shall|should)\s+"
# Resposta: texto até ponto final.
_RESPONSE = r"[^.]+?\."

_EARS_SENTENCE = re.compile(
    rf"^\s*{_PRECOND}{_SUBJECT}{_MODAL}{_RESPONSE}\s*$",
    re.MULTILINE | re.IGNORECASE,
)

# ---- Adjetivos ambíguos (lista negra) ---------------------------------------

_AMBIGUOUS = [
    # pt
    "user-friendly", "amigável", "fácil", "rápido", "eficiente",
    "robusto", "flexível", "leve", "simples", "intuitivo", "moderno",
    # en
    "fast", "easy", "efficient", "robust", "flexible", "lightweight",
    "simple", "intuitive", "modern", "user-friendly",
]
_AMBIGUOUS_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(w) for w in _AMBIGUOUS) + r")\b",
    re.IGNORECASE,
)

# ---- Seções do .req.md ------------------------------------------------------

_REQ_SECTION_RE = re.compile(
    r"^##\s+Requisito\s*$", re.MULTILINE | re.IGNORECASE
)
_DOD_SECTION_RE = re.compile(
    r"^##\s+Crit[eé]rios?\s+de\s+Aceite(?:\s*\(DoD\))?\s*$",
    re.MULTILINE | re.IGNORECASE,
)
_DOD_CHECKLIST_RE = re.compile(r"^\s*-\s*\[[\sxX]\]\s+\S", re.MULTILINE)


def _split_sections(text: str) -> dict[str, str]:
    """Divide o markdown em seções por cabeçalho `##`."""
    sections: dict[str, str] = {}
    # find all `##` headers and their content
    matches = list(re.finditer(r"^##\s+(.+?)\s*$", text, re.MULTILINE))
    for i, m in enumerate(matches):
        title = m.group(1).strip().lower()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections[title] = text[start:end]
    return sections


def _collect_ambiguous_issues(text: str) -> list[Issue]:
    issues: list[Issue] = []
    for m in _AMBIGUOUS_RE.finditer(text):
        line = text.count("\n", 0, m.start()) + 1
        issues.append(
            Issue(
                severity="warning",
                code="EARS_AMBIGUOUS",
                message=f"Termo ambíguo: '{m.group(0)}'. Quantifique-o.",
                line=line,
                context=text.splitlines()[line - 1].strip() if line <= len(text.splitlines()) else "",
            )
        )
    return issues


def _check_ears_format(req_body: str) -> tuple[bool, list[Issue], int]:
    """Retorna (ok, issues, count)."""
    sentences = _EARS_SENTENCE.findall(req_body)
    issues: list[Issue] = []
    if not sentences:
        issues.append(
            Issue(
                severity="error",
                code="EARS_NO_SENTENCE",
                message="Nenhuma sentença EARS válida na seção '## Requisito'. "
                        "Use: 'O sistema deve <resposta>.' ou "
                        "'Quando <gatilho>, o sistema deve <resposta>.'.",
            )
        )
        return False, issues, 0
    return True, issues, len(sentences)


def _check_dod(dod_body: str | None, text: str) -> list[Issue]:
    issues: list[Issue] = []
    if dod_body is None:
        issues.append(
            Issue(
                severity="error",
                code="EARS_NO_DOD_SECTION",
                message="Seção '## Critérios de Aceite (DoD)' ausente.",
            )
        )
        return issues
    checks = _DOD_CHECKLIST_RE.findall(dod_body)
    if not checks:
        issues.append(
            Issue(
                severity="error",
                code="EARS_DOD_EMPTY",
                message="DoD sem checklist. Adicione ao menos 1 item '- [ ] ...'.",
            )
        )
    elif len(checks) < 1:
        issues.append(
            Issue(
                severity="warning",
                code="EARS_DOD_THIN",
                message=f"DoD com apenas {len(checks)} item(ns). Considere mais critérios objetivos.",
            )
        )
    return issues


# ---- API pública ------------------------------------------------------------


def run(req_path: Path, config: dict | None = None) -> GateResult:
    """Executa gate ears sobre um .req.md.

    config: chaves do [gate.ears] do .engineer-hq.toml.
    """
    cfg = config or {}
    require_format = bool(cfg.get("require_ears_format", True))
    require_unambiguous = bool(cfg.get("require_unambiguous", True))
    require_dod = bool(cfg.get("require_dod_section", True))

    if not req_path.exists():
        return fail(
            "ears",
            "requirements",
            [Issue(
                severity="error",
                code="EARS_FILE_MISSING",
                message=f"Arquivo de requisito ausente: {req_path}",
            )],
        )

    text = req_path.read_text(encoding="utf-8")
    sections = _split_sections(text)
    # localizar seção requisito (case-insensitive já no split)
    req_body: str | None = None
    for key in sections:
        if "requisito" in key or "requirement" in key:
            req_body = sections[key]
            break

    issues: list[Issue] = []
    details: dict = {"file": str(req_path)}

    # 1) formato EARS
    ears_count = 0
    if require_format:
        if req_body is None:
            issues.append(Issue(
                severity="error", code="EARS_NO_REQ_SECTION",
                message="Seção '## Requisito' ausente.",
            ))
        else:
            ok, ears_issues, ears_count = _check_ears_format(req_body)
            issues.extend(ears_issues)
            details["ears_sentences"] = ears_count

    # 2) ambiguidade
    if require_unambiguous:
        amb = _collect_ambiguous_issues(text)
        # ambiguidades são warnings; só contam como fail se houver errors críticos
        issues.extend(amb)
        details["ambiguous_terms"] = len(amb)

    # 3) DoD
    if require_dod:
        dod_body: str | None = None
        for key in sections:
            if "crit" in key and "aceite" in key or "definition of done" in key:
                dod_body = sections[key]
                break
        issues.extend(_check_dod(dod_body, text))
        details["dod_checks"] = len(_DOD_CHECKLIST_RE.findall(dod_body or ""))

    # decisão: fail se há qualquer issue de severity=error; else pass (mesmo com warnings)
    has_errors = any(i.severity == "error" for i in issues)
    details["issues_count"] = len(issues)

    if not has_errors:
        # se formato exigido, precisa ter >=1 sentença; se desligado, basta não ter errors
        if require_format and ears_count == 0:
            return fail("ears", "requirements", issues, details)
        return pass_("ears", "requirements", details, issues)
    return fail("ears", "requirements", issues, details)
