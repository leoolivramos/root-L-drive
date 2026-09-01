"""
Testes unitários para ServerCryptoService (AES-256-GCM).
"""

import base64
import os
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# Helpers de fixture
# ---------------------------------------------------------------------------

def _make_key_b64(byte_len: int = 32) -> str:
    return base64.b64encode(os.urandom(byte_len)).decode("ascii")


def _build_service(key_b64: str):
    """Instancia ServerCryptoService com a chave fornecida (sem .env)."""
    with patch("app.core.config.settings") as mock_settings:
        mock_settings.file_encryption_key_base64 = key_b64
        from app.services.server_crypto_service import ServerCryptoService
        return ServerCryptoService()


# ---------------------------------------------------------------------------
# Testes
# ---------------------------------------------------------------------------

class TestServerCryptoServiceEncrypt:
    def test_encrypt_returns_three_values(self):
        svc = _build_service(_make_key_b64(32))
        result = svc.encrypt_bytes(b"hello world")
        assert isinstance(result, tuple)
        assert len(result) == 3

    def test_encrypted_differs_from_plaintext(self):
        svc = _build_service(_make_key_b64(32))
        plaintext = b"sensitive data 1234"
        ciphertext, algo, nonce_b64 = svc.encrypt_bytes(plaintext)
        assert ciphertext != plaintext

    def test_algorithm_label(self):
        svc = _build_service(_make_key_b64(32))
        _, algo, _ = svc.encrypt_bytes(b"test")
        assert algo == "AES-256-GCM"

    def test_nonce_is_valid_base64(self):
        svc = _build_service(_make_key_b64(32))
        _, _, nonce_b64 = svc.encrypt_bytes(b"test")
        decoded = base64.b64decode(nonce_b64)
        # AES-GCM nonce padrão é 12 bytes
        assert len(decoded) == 12

    def test_different_calls_produce_different_nonces(self):
        svc = _build_service(_make_key_b64(32))
        _, _, nonce1 = svc.encrypt_bytes(b"data")
        _, _, nonce2 = svc.encrypt_bytes(b"data")
        # Nonces devem ser únicos (aleatórios)
        assert nonce1 != nonce2


class TestServerCryptoServiceDecrypt:
    def test_roundtrip_32_byte_key(self):
        svc = _build_service(_make_key_b64(32))
        plaintext = b"round trip test"
        ciphertext, _, nonce_b64 = svc.encrypt_bytes(plaintext)
        recovered = svc.decrypt_bytes(ciphertext, nonce_b64)
        assert recovered == plaintext

    def test_roundtrip_16_byte_key(self):
        svc = _build_service(_make_key_b64(16))
        plaintext = b"AES-128"
        ciphertext, _, nonce_b64 = svc.encrypt_bytes(plaintext)
        recovered = svc.decrypt_bytes(ciphertext, nonce_b64)
        assert recovered == plaintext

    def test_roundtrip_24_byte_key(self):
        svc = _build_service(_make_key_b64(24))
        plaintext = b"AES-192"
        ciphertext, _, nonce_b64 = svc.encrypt_bytes(plaintext)
        recovered = svc.decrypt_bytes(ciphertext, nonce_b64)
        assert recovered == plaintext

    def test_roundtrip_empty_bytes(self):
        svc = _build_service(_make_key_b64(32))
        ciphertext, _, nonce_b64 = svc.encrypt_bytes(b"")
        recovered = svc.decrypt_bytes(ciphertext, nonce_b64)
        assert recovered == b""

    def test_roundtrip_large_payload(self):
        svc = _build_service(_make_key_b64(32))
        payload = os.urandom(10 * 1024 * 1024)  # 10 MB
        ciphertext, _, nonce_b64 = svc.encrypt_bytes(payload)
        recovered = svc.decrypt_bytes(ciphertext, nonce_b64)
        assert recovered == payload

    def test_wrong_nonce_raises(self):
        from cryptography.exceptions import InvalidTag
        svc = _build_service(_make_key_b64(32))
        ciphertext, _, _ = svc.encrypt_bytes(b"secret")
        bad_nonce = base64.b64encode(os.urandom(12)).decode("ascii")
        with pytest.raises(Exception):  # cryptography raises InvalidTag
            svc.decrypt_bytes(ciphertext, bad_nonce)

    def test_tampered_ciphertext_raises(self):
        svc = _build_service(_make_key_b64(32))
        ciphertext, _, nonce_b64 = svc.encrypt_bytes(b"secret")
        # Corrompe o primeiro byte do ciphertext
        tampered = bytes([ciphertext[0] ^ 0xFF]) + ciphertext[1:]
        with pytest.raises(Exception):
            svc.decrypt_bytes(tampered, nonce_b64)


class TestServerCryptoServiceInit:
    def test_invalid_key_length_raises_value_error(self):
        bad_key = base64.b64encode(os.urandom(15)).decode("ascii")  # 15 bytes — inválido
        with pytest.raises(ValueError, match="invalida"):
            _build_service(bad_key)

    def test_31_byte_key_raises_value_error(self):
        bad_key = base64.b64encode(os.urandom(31)).decode("ascii")
        with pytest.raises(ValueError):
            _build_service(bad_key)
