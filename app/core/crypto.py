import base64
import hashlib
import hmac
import logging
import os

from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)

_DEFAULT_DEV_SECRET = "c3po-default-dev-secret-change-in-production"


def _is_production() -> bool:
    return os.environ.get("APP_ENV", "").strip().lower() in {"production", "prod"}


def normalize_remote_jid(jid: str) -> str:
    """Normaliza o remoteJid (remove espaços, aplica lowercase e garante domínio WhatsApp se apenas números)."""
    if not jid:
        return ""
    cleaned = str(jid).strip().lower()
    if not cleaned:
        return ""
    if "@" not in cleaned and cleaned.isdigit():
        return f"{cleaned}@s.whatsapp.net"
    return cleaned


def _get_fernet() -> Fernet:
    """Obtém instância Fernet a partir de ENCRYPTION_KEY (exigida em produção)."""
    raw_key = os.environ.get("ENCRYPTION_KEY", "").strip()
    if not raw_key:
        if _is_production():
            raise RuntimeError("ENCRYPTION_KEY é obrigatória quando APP_ENV=production.")
        logger.warning(
            "ENCRYPTION_KEY não configurada no ambiente; utilizando chave derivada de desenvolvimento."
        )
        raw_key = _DEFAULT_DEV_SECRET

    try:
        return Fernet(raw_key.encode("utf-8"))
    except Exception:
        derived = base64.urlsafe_b64encode(hashlib.sha256(raw_key.encode("utf-8")).digest())
        return Fernet(derived)


def encrypt_remote_jid(jid: str) -> str:
    """Criptografa reversivelmente o remoteJid normalizado usando Fernet (AES-128-CBC + HMAC-SHA256)."""
    normalized = normalize_remote_jid(jid)
    fernet = _get_fernet()
    return fernet.encrypt(normalized.encode("utf-8")).decode("utf-8")


def decrypt_remote_jid(token: str) -> str:
    """Descriptografa o token Fernet da coluna `senha` de volta ao remoteJid original."""
    fernet = _get_fernet()
    return fernet.decrypt(token.encode("utf-8")).decode("utf-8")


def hash_remote_jid(jid: str) -> str:
    """Gera digest HMAC-SHA256 determinístico (64 chars hex) do remoteJid normalizado para busca indexada O(1)."""
    normalized = normalize_remote_jid(jid)
    hmac_secret = os.environ.get("HMAC_SECRET", "").strip()
    enc_secret = os.environ.get("ENCRYPTION_KEY", "").strip()

    if _is_production() and (not hmac_secret or not enc_secret):
        raise RuntimeError("ENCRYPTION_KEY e HMAC_SECRET são obrigatórias quando APP_ENV=production.")

    secret = hmac_secret or enc_secret or _DEFAULT_DEV_SECRET
    return hmac.new(
        secret.encode("utf-8"),
        normalized.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def verify_registration_password(candidate: str) -> bool:
    """Compara a senha informada com SYSTEM_REGISTRATION_PASSWORD em tempo constante."""
    expected = os.environ.get("SYSTEM_REGISTRATION_PASSWORD", "").strip()
    if not expected or not candidate:
        return False
    return hmac.compare_digest(
        candidate.strip().encode("utf-8"),
        expected.encode("utf-8"),
    )
