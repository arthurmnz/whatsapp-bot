from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import threading
import time
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.crypto import _DEFAULT_DEV_SECRET, _is_production, normalize_remote_jid
from app.core.memory import _get_redis, kv_delete, kv_get, kv_set
from app.db.models import User
from app.db.repositories.user_repo import get_user_by_jid, user_has_permission
from app.db.session import get_db

logger = logging.getLogger(__name__)

_bearer_scheme = HTTPBearer(auto_error=False)

OTP_TTL_SECONDS = 300
OTP_MAX_ATTEMPTS = 5
DEFAULT_JWT_EXPIRES_MINUTES = 60 * 24 * 7  # 7 dias

_otp_lock = threading.Lock()
_rate_lock = threading.Lock()
_rate_buckets: dict[str, tuple[int, float]] = {}


def _get_jwt_secret() -> str:
    jwt_secret = os.environ.get("JWT_SECRET", "").strip()
    if jwt_secret:
        if len(jwt_secret.encode("utf-8")) < 32:
            return hmac.new(
                jwt_secret.encode("utf-8"),
                b"jwt-signing-key-v1",
                hashlib.sha256,
            ).hexdigest()
        return jwt_secret

    hmac_secret = os.environ.get("HMAC_SECRET", "").strip()
    if hmac_secret:
        return hmac.new(
            hmac_secret.encode("utf-8"),
            b"jwt-signing-key-v1",
            hashlib.sha256,
        ).hexdigest()

    if _is_production():
        raise RuntimeError("JWT_SECRET ou HMAC_SECRET é obrigatório quando APP_ENV=production.")

    logger.warning(
        "JWT_SECRET/HMAC_SECRET não configurado; utilizando chave derivada de desenvolvimento."
    )
    return hmac.new(
        _DEFAULT_DEV_SECRET.encode("utf-8"),
        b"jwt-signing-key-v1",
        hashlib.sha256,
    ).hexdigest()


def _get_jwt_expires_minutes() -> int:
    raw = os.environ.get("JWT_EXPIRES_MINUTES", str(DEFAULT_JWT_EXPIRES_MINUTES)).strip()
    try:
        val = int(raw)
        return val if val > 0 else DEFAULT_JWT_EXPIRES_MINUTES
    except ValueError:
        return DEFAULT_JWT_EXPIRES_MINUTES


def check_auth_rate_limit(bucket_key: str, max_requests: int = 10, window_seconds: int = 300) -> None:
    """Aplica rate limiting por janela fixa em Redis (com fallback atômico em memória)."""
    redis_key = f"c3po_bot:rl:{bucket_key}"
    client = _get_redis()
    if client is not None:
        try:
            count = int(client.incr(redis_key))
            if count == 1:
                client.expire(redis_key, window_seconds)
            if count > max_requests:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Muitas tentativas de autenticação. Aguarde alguns minutos e tente novamente.",
                )
            return
        except HTTPException:
            raise
        except Exception as exc:
            logger.debug("Redis indisponível em rate limit (%s); usando fallback em memória.", exc)

    now = time.time()
    with _rate_lock:
        count, expires_at = _rate_buckets.get(redis_key, (0, 0.0))
        if now >= expires_at:
            count = 1
            expires_at = now + window_seconds
        else:
            count += 1
        _rate_buckets[redis_key] = (count, expires_at)
        if count > max_requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Muitas tentativas de autenticação. Aguarde alguns minutos e tente novamente.",
            )


def hash_web_password(password: str) -> str:
    """Gera hash seguro scrypt com salt aleatório para senha web."""
    if not password or len(password) < 6:
        raise ValueError("A senha web deve ter pelo menos 6 caracteres.")
    salt = secrets.token_bytes(16)
    derived = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=16384,
        r=8,
        p=1,
        dklen=32,
    )
    return f"scrypt${salt.hex()}${derived.hex()}"


def verify_web_password(password: str, stored_hash: str | None) -> bool:
    """Verifica senha web contra o hash armazenado em tempo constante."""
    if not password or not stored_hash:
        return False
    parts = stored_hash.split("$")
    if len(parts) != 3 or parts[0] != "scrypt":
        return False
    try:
        salt = bytes.fromhex(parts[1])
        expected = bytes.fromhex(parts[2])
    except ValueError:
        return False

    candidate = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=16384,
        r=8,
        p=1,
        dklen=32,
    )
    return hmac.compare_digest(candidate, expected)


def normalize_phone_or_jid(raw_input: str) -> str:
    """Aceita dígitos, telefone formatado ou remoteJid e normaliza para lookup."""
    cleaned = (raw_input or "").strip()
    if not cleaned:
        return ""
    if "@" in cleaned:
        return normalize_remote_jid(cleaned)
    digits = re.sub(r"\D", "", cleaned)
    if digits:
        return normalize_remote_jid(digits)
    return ""


def find_user_by_phone_or_jid(db: Session, phone_or_jid: str) -> User | None:
    """Localiza usuário ativo pelo JID exato ou variação do 9º dígito brasileiro."""
    normalized = normalize_phone_or_jid(phone_or_jid)
    if not normalized:
        return None
    user = get_user_by_jid(db, normalized)
    if user is not None:
        return user

    digits = re.sub(r"\D", "", normalized.split("@")[0])
    if digits.startswith("55"):
        alt: str | None = None
        if len(digits) == 13 and digits[4] == "9":
            alt = f"55{digits[2:4]}{digits[5:]}@s.whatsapp.net"
        elif len(digits) == 12:
            alt = f"55{digits[2:4]}9{digits[4:]}@s.whatsapp.net"
        if alt:
            return get_user_by_jid(db, alt)
    return None


def _otp_key(jid_hash: str) -> str:
    return f"c3po_bot:web_otp:{jid_hash}"


def _hash_otp_code(jid_hash: str, code: str) -> str:
    secret = _get_jwt_secret().encode("utf-8")
    return hmac.new(secret, f"{jid_hash}:{code.strip()}".encode("utf-8"), hashlib.sha256).hexdigest()


def issue_otp_for_user(user: User) -> str:
    """Gera código OTP de 6 dígitos e armazena hash com TTL fixo de 5 minutos."""
    code = f"{secrets.randbelow(1_000_000):06d}"
    expires_at = time.time() + OTP_TTL_SECONDS
    payload = {
        "otp_hash": _hash_otp_code(user.remote_jid_hash, code),
        "attempts": 0,
        "expires_at": expires_at,
    }
    with _otp_lock:
        kv_set(_otp_key(user.remote_jid_hash), json.dumps(payload), OTP_TTL_SECONDS)
    return code


def invalidate_otp_for_user(user: User) -> None:
    """Remove qualquer OTP pendente do usuário."""
    with _otp_lock:
        kv_delete(_otp_key(user.remote_jid_hash))


def verify_otp_for_user(user: User, code: str) -> tuple[bool, str]:
    """Valida código OTP de forma atômica, preservando o expires_at original."""
    key = _otp_key(user.remote_jid_hash)
    with _otp_lock:
        raw = kv_get(key)
        if not raw:
            return False, "Código expirado ou não solicitado."

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            kv_delete(key)
            return False, "Código inválido."

        now = time.time()
        expires_at = float(data.get("expires_at", 0.0))
        if expires_at and now > expires_at:
            kv_delete(key)
            return False, "Código expirado ou não solicitado."

        attempts = int(data.get("attempts", 0))
        if attempts >= OTP_MAX_ATTEMPTS:
            kv_delete(key)
            return False, "Limite de tentativas excedido. Solicite um novo código."

        expected_hash = str(data.get("otp_hash", ""))
        candidate_hash = _hash_otp_code(user.remote_jid_hash, (code or "").strip())

        if hmac.compare_digest(candidate_hash, expected_hash):
            kv_delete(key)
            return True, "ok"

        attempts += 1
        if attempts >= OTP_MAX_ATTEMPTS:
            kv_delete(key)
            return False, "Limite de tentativas excedido. Solicite um novo código."

        data["attempts"] = attempts
        remaining_ttl = max(1, int(expires_at - now)) if expires_at else OTP_TTL_SECONDS
        kv_set(key, json.dumps(data), remaining_ttl)
        return False, "Código inválido."


def create_access_token(user: User) -> str:
    """Emite JWT HS256 com claims do usuário autenticado."""
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=_get_jwt_expires_minutes())
    payload = {
        "sub": str(user.id),
        "nome": user.nome,
        "role": user.role.name if user.role else "user",
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    return jwt.encode(payload, _get_jwt_secret(), algorithm="HS256")


def decode_access_token(token: str) -> dict[str, Any]:
    """Decodifica e valida token JWT HS256."""
    try:
        payload = jwt.decode(token, _get_jwt_secret(), algorithms=["HS256"])
        return dict(payload)
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sessão expirada. Faça login novamente.",
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de autenticação inválido.",
        ) from exc


def get_user_from_token(db: Session, token: str) -> User:
    """Obtém usuário ativo no banco a partir de um JWT válido."""
    payload = decode_access_token(token)
    sub = payload.get("sub")
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token sem identificador de usuário.",
        )
    try:
        user_id = int(sub)
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Identificador de usuário inválido no token.",
        ) from exc

    user = db.query(User).filter(User.id == user_id, User.is_active.is_(True)).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário não encontrado ou inativo.",
        )
    if not user_has_permission(user, "web:access"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuário sem permissão para acessar a interface web.",
        )
    return user


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Dependency FastAPI que valida Bearer JWT e retorna o usuário autenticado."""
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Autenticação necessária.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return get_user_from_token(db, credentials.credentials)


def require_permission(permission_code: str):
    """Factory de dependency FastAPI que exige uma permissão RBAC específica."""

    def _checker(user: User = Depends(get_current_user)) -> User:
        if not user_has_permission(user, permission_code):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permissão necessária: {permission_code}",
            )
        return user

    return _checker


def serialize_user_summary(user: User) -> dict[str, Any]:
    """Serializa usuário autenticado sem expor hashes ou remoteJid bruto."""
    perms = [p.code for p in (user.role.permissions if user.role else [])]
    return {
        "id": user.id,
        "nome": user.nome,
        "role": user.role.name if user.role else "user",
        "permissions": sorted(perms),
        "has_web_password": bool(user.web_password_hash),
        "is_active": bool(user.is_active),
    }


def lookup_user_by_identifier(db: Session, identifier: str) -> User | None:
    """Busca usuário por telefone/JID ou comparação exata case-insensitive do nome."""
    cleaned = (identifier or "").strip()
    if not cleaned:
        return None
    if "@" in cleaned or sum(c.isdigit() for c in cleaned) >= 8:
        user = find_user_by_phone_or_jid(db, cleaned)
        if user is not None:
            return user
    matches = (
        db.query(User)
        .filter(User.is_active.is_(True), func.lower(User.nome) == cleaned.lower())
        .all()
    )
    if len(matches) == 1:
        return matches[0]
    return None
