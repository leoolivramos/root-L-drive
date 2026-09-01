"""
Fixtures compartilhadas para os testes do Private Driver backend.
"""

import base64
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_test_aes_key() -> str:
    """Gera uma chave AES-256 válida (32 bytes) em base64 para testes."""
    raw = os.urandom(32)
    return base64.b64encode(raw).decode("ascii")


# ---------------------------------------------------------------------------
# MongoDB mock (mongomock-motor)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def mongo_mock_client():
    """Motor client falso em memória via mongomock-motor."""
    import mongomock_motor
    return mongomock_motor.AsyncMongoMockClient()


@pytest.fixture()
def mock_db(mongo_mock_client):
    """Banco de dados isolado por teste (evita vazamento entre testes)."""
    return mongo_mock_client["test_private_drive"]


# ---------------------------------------------------------------------------
# App override fixture
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture()
async def client(mock_db):
    """
    AsyncClient do httpx apontando para a FastAPI com MongoDB mockado.
    O banco real é substituído pelo mock via monkeypatch do get_database().
    """
    from app.main import app

    with patch("app.db.mongodb.get_database", return_value=mock_db), \
         patch("app.db.mongodb.get_client", return_value=None):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as ac:
            yield ac


# ---------------------------------------------------------------------------
# Crypto fixture
# ---------------------------------------------------------------------------

@pytest.fixture()
def aes_key_b64() -> str:
    return _make_test_aes_key()


@pytest.fixture()
def crypto_service(aes_key_b64: str):
    """ServerCryptoService com chave aleatória gerada por fixture."""
    with patch("app.core.config.settings") as mock_settings:
        mock_settings.file_encryption_key_base64 = aes_key_b64
        from app.services.server_crypto_service import ServerCryptoService
        return ServerCryptoService()
