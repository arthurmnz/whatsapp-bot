from cryptography.fernet import Fernet
import pytest

from app.core.crypto import (
    decrypt_remote_jid,
    encrypt_remote_jid,
    hash_remote_jid,
    normalize_remote_jid,
    verify_registration_password,
)


def test_normalize_remote_jid():
    assert normalize_remote_jid("  5511999999999@S.WHATSAPP.NET ") == "5511999999999@s.whatsapp.net"
    assert normalize_remote_jid("5511999999999") == "5511999999999@s.whatsapp.net"
    assert normalize_remote_jid("") == ""
    assert normalize_remote_jid("   ") == ""


def test_encrypt_and_decrypt_remote_jid_roundtrip_with_valid_fernet_key(monkeypatch: pytest.MonkeyPatch):
    valid_key = Fernet.generate_key().decode("utf-8")
    monkeypatch.setenv("ENCRYPTION_KEY", valid_key)

    original = "5511999999999"
    token1 = encrypt_remote_jid(original)
    token2 = encrypt_remote_jid(original)

    # Fernet é probabilístico (usa IV aleatório), então dois ciphertexts são diferentes
    assert token1 != token2
    assert "5511999999999" not in token1

    assert decrypt_remote_jid(token1) == "5511999999999@s.whatsapp.net"
    assert decrypt_remote_jid(token2) == "5511999999999@s.whatsapp.net"


def test_encrypt_and_decrypt_with_arbitrary_passphrase_key(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ENCRYPTION_KEY", "minha-chave-customizada-nao-base64")
    token = encrypt_remote_jid("5511888888888@s.whatsapp.net")
    assert decrypt_remote_jid(token) == "5511888888888@s.whatsapp.net"


def test_hash_remote_jid_is_deterministic_64_hex_chars(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("HMAC_SECRET", "super-hmac-secret")
    h1 = hash_remote_jid("5511999999999")
    h2 = hash_remote_jid("  5511999999999@s.whatsapp.net  ")
    h3 = hash_remote_jid("5511888888888@s.whatsapp.net")

    assert len(h1) == 64
    assert h1 == h2
    assert h1 != h3


def test_verify_registration_password(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SYSTEM_REGISTRATION_PASSWORD", "SenhaSecreta123")

    assert verify_registration_password("SenhaSecreta123") is True
    assert verify_registration_password("  SenhaSecreta123  ") is True
    assert verify_registration_password("SenhaErrada") is False
    assert verify_registration_password("") is False

    monkeypatch.delenv("SYSTEM_REGISTRATION_PASSWORD", raising=False)
    assert verify_registration_password("SenhaSecreta123") is False
