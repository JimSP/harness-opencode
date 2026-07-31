"""Testes do gate EARS (parser de .req.md)."""
from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from engineer_hq.gates import ears


def _write(tmp_path: Path, name: str, content: str) -> Path:
    p = tmp_path / name
    p.write_text(dedent(content).strip() + "\n", encoding="utf-8")
    return p


def test_pass_valid_ears_with_precond_and_dod(tmp_path: Path) -> None:
    p = _write(tmp_path, "f.req.md", """
        # Login com senha

        > feature: FT-0001-x

        ## Requisito

        Quando o usuário submete credenciais válidas, o sistema deve emitir um token JWT com validade de 15 minutos.

        ## Critérios de Aceite (DoD)

        - [ ] Token contém claim `exp` = emissão + 900s
        - [ ] Status 401 retornado para credenciais inválidas
    """)
    r = ears.run(p)
    assert r.status == "pass", r.to_dict()
    assert r.details["ears_sentences"] >= 1
    assert r.details["dod_checks"] >= 2


def test_pass_unconditional_ears_english(tmp_path: Path) -> None:
    p = _write(tmp_path, "f.req.md", """
        # Title

        ## Requirement

        The system shall log every authentication attempt.

        ## Definition of Done

        - [ ] Audit log entry persisted
    """)
    r = ears.run(p)
    assert r.status == "pass"


def test_fail_no_ears_sentence(tmp_path: Path) -> None:
    p = _write(tmp_path, "f.req.md", """
        # X

        ## Requisito

        O login precisa funcionar direito.
    """)
    r = ears.run(p)
    assert r.status == "fail"
    codes = [i.code for i in r.issues]
    assert "EARS_NO_SENTENCE" in codes


def test_fail_no_dod_section(tmp_path: Path) -> None:
    p = _write(tmp_path, "f.req.md", """
        # X

        ## Requisito

        O sistema deve emitir um token JWT.
    """)
    r = ears.run(p)
    assert r.status == "fail"
    assert any(i.code == "EARS_NO_DOD_SECTION" for i in r.issues)


def test_fail_dod_empty_checklist(tmp_path: Path) -> None:
    p = _write(tmp_path, "f.req.md", """
        # X

        ## Requisito

        O sistema deve emitir um token JWT.

        ## Critérios de Aceite (DoD)

        Ainda vou definir.
    """)
    r = ears.run(p)
    assert r.status == "fail"
    assert any(i.code == "EARS_DOD_EMPTY" for i in r.issues)


def test_warn_ambiguous_term_but_still_pass_if_no_errors(tmp_path: Path) -> None:
    # termo ambíguo é warning, não error; só falhará se houver outro erro
    p = _write(tmp_path, "f.req.md", """
        # X

        ## Requisito

        O sistema deve oferecer uma interface amigável ao usuário.

        ## Critérios de Aceite (DoD)

        - [ ] Mockup aprovado
    """)
    r = ears.run(p)
    assert r.status == "pass"  # warning não bloqueia
    assert r.details["ambiguous_terms"] >= 1
    assert any(i.code == "EARS_AMBIGUOUS" for i in r.issues)


def test_fail_missing_req_section(tmp_path: Path) -> None:
    p = _write(tmp_path, "f.req.md", """
        # X

        ## Outro

        Qualquer coisa.
    """)
    r = ears.run(p)
    assert r.status == "fail"
    assert any(i.code == "EARS_NO_REQ_SECTION" for i in r.issues)


def test_fail_file_missing(tmp_path: Path) -> None:
    r = ears.run(tmp_path / "nope.req.md")
    assert r.status == "fail"
    assert any(i.code == "EARS_FILE_MISSING" for i in r.issues)


def test_ears_forms_precondition_variants(tmp_path: Path) -> None:
    """Enquanto/Onde aceitos como pré-condição."""
    p = _write(tmp_path, "f.req.md", """
        # X

        ## Requisito

        Enquanto o usuário estiver autenticado, o sistema deve renovar a sessão a cada 5 minutos.
        Onde o módulo premium estiver ativo, o sistema deve liberar a API de relatórios.

        ## Critérios de Aceite (DoD)

        - [ ] renovação ocorre
    """)
    r = ears.run(p)
    assert r.status == "pass"
    assert r.details["ears_sentences"] >= 2


def test_config_can_disable_dod_check(tmp_path: Path) -> None:
    p = _write(tmp_path, "f.req.md", """
        # X

        ## Requisito

        O sistema deve logar tentativas.
    """)
    r = ears.run(p, {"require_dod_section": False})
    assert r.status == "pass"


def test_config_can_disable_format_check(tmp_path: Path) -> None:
    p = _write(tmp_path, "f.req.md", """
        # X

        ## Requisito

        Algo genérico qualquer.
    """)
    r = ears.run(p, {"require_ears_format": False, "require_dod_section": False})
    assert r.status == "pass"  # tudo desligado
