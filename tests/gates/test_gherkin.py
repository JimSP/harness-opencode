"""Testes do gate gherkin (parser de .feature)."""
from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from engineer_hq.gates import gherkin_gate as gherkin


def _write(tmp_path: Path, name: str, content: str) -> Path:
    p = tmp_path / name
    p.write_text(dedent(content).strip() + "\n", encoding="utf-8")
    return p


def test_pass_simple_pt_feature(tmp_path: Path) -> None:
    p = _write(tmp_path, "f.feature", """
        # language: pt
        Funcionalidade: Login

          @req:FT-0001-x
          Cenário: credenciais válidas
            Dado um usuário cadastrado
            Quando submete credenciais válidas
            Então emite token JWT
    """)
    r = gherkin.run(p, {"require_scenario_outline": False})  # desliga outline p/ teste simples
    assert r.status == "pass", r.to_dict()
    assert r.details["scenarios_count"] == 1


def test_pass_english_feature_with_outline(tmp_path: Path) -> None:
    p = _write(tmp_path, "f.feature", """
        Feature: Login

          @req:FT-0001-x
          Scenario Outline: credenciais inválidas
            Given a user with <attempts> failed attempts
            When submits invalid password
            Then returns 401
            Examples:
              | attempts |
              | 1        |
              | 3        |
    """)
    r = gherkin.run(p)
    assert r.status == "pass"
    assert r.details["outlines_count"] >= 1
    assert r.details["req_refs"] >= 1


def test_fail_no_req_ref(tmp_path: Path) -> None:
    p = _write(tmp_path, "f.feature", """
        # language: pt
        Funcionalidade: Login

          Cenário: x
            Dado um usuário
            Quando submete senha
            Então emite token
    """)
    r = gherkin.run(p, {"require_scenario_outline": False})
    assert r.status == "fail"
    assert any(i.code == "GHERKIN_NO_REQ_REF" for i in r.issues)


def test_fail_missing_step_then(tmp_path: Path) -> None:
    p = _write(tmp_path, "f.feature", """
        # language: pt
        Funcionalidade: Login

          @req:FT-0001-x
          Cenário: sem Then
            Dado um usuário
            Quando submete senha
    """)
    r = gherkin.run(p, {"require_scenario_outline": False})
    assert r.status == "fail"
    assert any(i.code == "GHERKIN_MISSING_STEPS" for i in r.issues)


def test_fail_parse_error_sintaxe_invalida(tmp_path: Path) -> None:
    p = _write(tmp_path, "f.feature", """
        Feature: Login

          Scenario: x
            Given algo
            isso não é um passo válido gherkin
    """)
    r = gherkin.run(p, {"require_scenario_outline": False, "require_req_ref": False})
    # keyword inválida -> parse_error OR missing steps; aceitamos ambos
    codes = [i.code for i in r.issues]
    assert r.status == "fail"
    assert any(c in ("GHERKIN_PARSE_ERROR", "GHERKIN_MISSING_STEPS") for c in codes)


def test_fail_outline_without_examples(tmp_path: Path) -> None:
    p = _write(tmp_path, "f.feature", """
        Feature: Login

          @req:FT-0001-x
          Scenario Outline: sem examples
            Given user with <n> attempts
            When submits invalid password
            Then returns 401
    """)
    r = gherkin.run(p)
    assert r.status == "fail"
    assert any(i.code == "GHERKIN_OUTLINE_NO_EXAMPLES" for i in r.issues)


def test_fail_file_missing(tmp_path: Path) -> None:
    r = gherkin.run(tmp_path / "nope.feature")
    assert r.status == "fail"
    assert any(i.code == "GHERKIN_FILE_MISSING" for i in r.issues)


def test_fail_no_scenarios(tmp_path: Path) -> None:
    p = _write(tmp_path, "f.feature", """
        Feature: Login
    """)
    r = gherkin.run(p, {"require_scenario_outline": False})
    assert r.status == "fail"
    assert any(i.code == "GHERKIN_NO_SCENARIOS" for i in r.issues)


def test_config_disable_all_passes_minimal(tmp_path: Path) -> None:
    p = _write(tmp_path, "f.feature", """
        Feature: Login
          Scenario: x
            Given algo
            When algo
            Then algo
    """)
    r = gherkin.run(p, {
        "require_scenario_outline": False,
        "require_req_ref": False,
    })
    assert r.status == "pass"
