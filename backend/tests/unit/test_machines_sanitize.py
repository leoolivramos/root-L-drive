"""
Testes unitários para _sanitize_machine_command e helpers de path do machines.py.
"""

import os
import sys
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException


# ---------------------------------------------------------------------------
# Import das funções a testar (sem subir a app inteira)
# ---------------------------------------------------------------------------

# Importamos diretamente as funções do módulo de rotas
from app.routes.machines import (
    _MAX_READ_BYTES,
    _is_path_allowed,
    _normalize_path,
    _resolve_requested_path,
    _sanitize_machine_command,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_machine(allowed_paths: list[str]):
    """Cria um mock de Machine com allowed_paths."""
    m = MagicMock()
    m.allowed_paths = allowed_paths
    return m


# ---------------------------------------------------------------------------
# Testes de _normalize_path
# ---------------------------------------------------------------------------

class TestNormalizePath:
    def test_expands_home(self):
        home = os.path.expanduser("~")
        assert _normalize_path("~") == os.path.abspath(home)

    def test_absolute_path_unchanged(self):
        path = os.path.abspath("/tmp/test")
        assert _normalize_path(path) == path

    def test_relative_path_resolved(self):
        result = _normalize_path("relative/path")
        assert os.path.isabs(result)


# ---------------------------------------------------------------------------
# Testes de _is_path_allowed
# ---------------------------------------------------------------------------

class TestIsPathAllowed:
    def test_exact_match(self, tmp_path):
        target = str(tmp_path)
        assert _is_path_allowed(target, [target]) is True

    def test_subdirectory_allowed(self, tmp_path):
        subdir = str(tmp_path / "sub")
        assert _is_path_allowed(subdir, [str(tmp_path)]) is True

    def test_sibling_not_allowed(self, tmp_path):
        dir_a = str(tmp_path / "a")
        dir_b = str(tmp_path / "b")
        assert _is_path_allowed(dir_a, [dir_b]) is False

    def test_empty_allowed_list(self, tmp_path):
        assert _is_path_allowed(str(tmp_path), []) is False


# ---------------------------------------------------------------------------
# Testes de _resolve_requested_path
# ---------------------------------------------------------------------------

class TestResolveRequestedPath:
    def test_none_returns_base(self, tmp_path):
        base = str(tmp_path)
        result = _resolve_requested_path(None, [base])
        assert result == base

    def test_dot_returns_base(self, tmp_path):
        base = str(tmp_path)
        result = _resolve_requested_path(".", [base])
        assert result == base

    def test_empty_allowed_raises(self):
        with pytest.raises(HTTPException) as exc_info:
            _resolve_requested_path(None, [])
        assert exc_info.value.status_code == 409

    def test_absolute_path_resolved(self, tmp_path):
        abs_path = str(tmp_path / "file.txt")
        result = _resolve_requested_path(abs_path, [str(tmp_path)])
        assert result == abs_path

    def test_relative_path_joined_to_base(self, tmp_path):
        base = str(tmp_path)
        result = _resolve_requested_path("subdir/file.txt", [base])
        assert result == os.path.normpath(os.path.join(base, "subdir/file.txt"))


# ---------------------------------------------------------------------------
# Testes de _sanitize_machine_command
# ---------------------------------------------------------------------------

class TestSanitizeMachineCommand:
    """Testes para o sanitizador de comandos do agente."""

    # --- Comandos inválidos ---

    def test_unsupported_cmd_raises_400(self, tmp_path):
        machine = _make_machine([str(tmp_path)])
        with pytest.raises(HTTPException) as exc_info:
            _sanitize_machine_command(machine, {"cmd": "delete"})
        assert exc_info.value.status_code == 400
        assert exc_info.value.detail == "unsupported-command"

    def test_missing_cmd_raises_400(self, tmp_path):
        machine = _make_machine([str(tmp_path)])
        with pytest.raises(HTTPException) as exc_info:
            _sanitize_machine_command(machine, {"path": "/tmp"})
        assert exc_info.value.status_code == 400

    def test_invalid_payload_type_raises_400(self, tmp_path):
        machine = _make_machine([str(tmp_path)])
        with pytest.raises(HTTPException) as exc_info:
            _sanitize_machine_command(machine, "not-a-dict")  # type: ignore
        assert exc_info.value.status_code == 400
        assert exc_info.value.detail == "invalid-command-payload"

    # --- Comando list ---

    def test_list_allowed_path_returns_sanitized(self, tmp_path):
        base = str(tmp_path)
        machine = _make_machine([base])
        result = _sanitize_machine_command(machine, {"cmd": "list", "path": "."})
        assert result["cmd"] == "list"
        assert result["path"] == base

    def test_list_outside_allowed_raises_403(self, tmp_path, tmp_path_factory):
        allowed = str(tmp_path)
        forbidden = str(tmp_path_factory.mktemp("other"))
        machine = _make_machine([allowed])
        with pytest.raises(HTTPException) as exc_info:
            _sanitize_machine_command(machine, {"cmd": "list", "path": forbidden})
        assert exc_info.value.status_code == 403
        assert exc_info.value.detail == "path-not-allowed"

    def test_list_no_allowed_paths_raises_409(self):
        machine = _make_machine([])
        with pytest.raises(HTTPException) as exc_info:
            _sanitize_machine_command(machine, {"cmd": "list", "path": "."})
        assert exc_info.value.status_code == 409

    # --- Comando read ---

    def test_read_no_path_raises_400(self, tmp_path):
        machine = _make_machine([str(tmp_path)])
        with pytest.raises(HTTPException) as exc_info:
            _sanitize_machine_command(machine, {"cmd": "read"})
        assert exc_info.value.status_code == 400
        assert exc_info.value.detail == "path-is-required"

    def test_read_outside_allowed_raises_403(self, tmp_path, tmp_path_factory):
        allowed = str(tmp_path)
        forbidden = str(tmp_path_factory.mktemp("other") / "secret.txt")
        machine = _make_machine([allowed])
        with pytest.raises(HTTPException) as exc_info:
            _sanitize_machine_command(machine, {"cmd": "read", "path": forbidden})
        assert exc_info.value.status_code == 403

    def test_read_clamps_max_bytes_to_limit(self, tmp_path):
        machine = _make_machine([str(tmp_path)])
        result = _sanitize_machine_command(
            machine,
            {"cmd": "read", "path": str(tmp_path / "f.txt"), "max_bytes": 999_999_999},
        )
        assert result["max_bytes"] == _MAX_READ_BYTES

    def test_read_invalid_max_bytes_raises_400(self, tmp_path):
        machine = _make_machine([str(tmp_path)])
        with pytest.raises(HTTPException) as exc_info:
            _sanitize_machine_command(
                machine, {"cmd": "read", "path": str(tmp_path / "f.txt"), "max_bytes": "not-an-int"}
            )
        assert exc_info.value.status_code == 400
        assert exc_info.value.detail == "invalid-max-bytes"

    def test_read_zero_max_bytes_raises_400(self, tmp_path):
        machine = _make_machine([str(tmp_path)])
        with pytest.raises(HTTPException) as exc_info:
            _sanitize_machine_command(
                machine, {"cmd": "read", "path": str(tmp_path / "f.txt"), "max_bytes": 0}
            )
        assert exc_info.value.status_code == 400

    def test_read_valid_payload_returns_sanitized(self, tmp_path):
        machine = _make_machine([str(tmp_path)])
        file_path = str(tmp_path / "doc.txt")
        result = _sanitize_machine_command(
            machine, {"cmd": "read", "path": file_path, "max_bytes": 1024}
        )
        assert result["cmd"] == "read"
        assert result["path"] == file_path
        assert result["max_bytes"] == 1024
