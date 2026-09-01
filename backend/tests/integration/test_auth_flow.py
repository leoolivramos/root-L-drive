"""
Testes de integração para o fluxo de autenticação (register → login → profile).

Usa mongomock-motor para simular o MongoDB sem depender de uma instância real.
"""

import pytest
from httpx import ASGITransport, AsyncClient
from unittest.mock import patch, AsyncMock


# ---------------------------------------------------------------------------
# Fixture: app com MongoDB mockado
# ---------------------------------------------------------------------------

@pytest.fixture()
async def app_client():
    """
    Sobe a FastAPI com MongoDB completamente mockado via mongomock-motor.
    Cada teste recebe um banco isolado.
    """
    import mongomock_motor

    mock_client = mongomock_motor.AsyncMongoMockClient()
    mock_db = mock_client["test_auth_flow"]

    from app.main import app

    with patch("app.db.mongodb.get_database", return_value=mock_db), \
         patch("app.db.mongodb.get_client", return_value=mock_client), \
         patch("app.services.minio_service.MinioService.ensure_bucket_exists", new_callable=AsyncMock), \
         patch("app.services.file_cleanup_service.run_trash_cleanup_loop", new_callable=AsyncMock):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as ac:
            yield ac


# ---------------------------------------------------------------------------
# Testes
# ---------------------------------------------------------------------------

class TestRegisterEndpoint:
    async def test_register_success(self, app_client):
        response = await app_client.post(
            "/api/v1/auth/register",
            json={"email": "test@example.com", "password": "SecurePass123!"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "test@example.com"
        assert "id" in data

    async def test_register_duplicate_email_raises(self, app_client):
        payload = {"email": "dup@example.com", "password": "Pass123!"}
        r1 = await app_client.post("/api/v1/auth/register", json=payload)
        assert r1.status_code == 200
        r2 = await app_client.post("/api/v1/auth/register", json=payload)
        assert r2.status_code in (400, 409, 422)

    async def test_register_invalid_email_raises(self, app_client):
        response = await app_client.post(
            "/api/v1/auth/register",
            json={"email": "not-an-email", "password": "Pass123!"},
        )
        assert response.status_code == 422


class TestLoginEndpoint:
    async def test_login_success_returns_token(self, app_client):
        # Primeiro registra
        await app_client.post(
            "/api/v1/auth/register",
            json={"email": "login@example.com", "password": "MyPass123!"},
        )
        # Depois loga
        response = await app_client.post(
            "/api/v1/auth/login",
            json={"email": "login@example.com", "password": "MyPass123!"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert len(data["access_token"]) > 10

    async def test_login_wrong_password_raises(self, app_client):
        await app_client.post(
            "/api/v1/auth/register",
            json={"email": "wrongpass@example.com", "password": "Correct123!"},
        )
        response = await app_client.post(
            "/api/v1/auth/login",
            json={"email": "wrongpass@example.com", "password": "WrongPass!"},
        )
        assert response.status_code in (400, 401, 403)

    async def test_login_nonexistent_user_raises(self, app_client):
        response = await app_client.post(
            "/api/v1/auth/login",
            json={"email": "ghost@example.com", "password": "Anything123!"},
        )
        assert response.status_code in (400, 401, 404)


class TestAuthenticatedEndpoints:
    async def _get_token(self, client, email: str = "auth@example.com", password: str = "Pass123!") -> str:
        await client.post("/api/v1/auth/register", json={"email": email, "password": password})
        resp = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
        return resp.json()["access_token"]

    async def test_profile_requires_auth(self, app_client):
        response = await app_client.get("/api/v1/profile")
        assert response.status_code == 401 or response.status_code == 403

    async def test_profile_with_valid_token(self, app_client):
        token = await self._get_token(app_client)
        response = await app_client.get(
            "/api/v1/profile",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "email" in data

    async def test_profile_with_invalid_token_raises(self, app_client):
        response = await app_client.get(
            "/api/v1/profile",
            headers={"Authorization": "Bearer invalid.token.here"},
        )
        assert response.status_code == 401
