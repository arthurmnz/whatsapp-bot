import json
import logging
import os
import threading
import time
from typing import Any

from dotenv import load_dotenv
import redis

load_dotenv()

logger = logging.getLogger(__name__)

# Máximo de mensagens mantidas por conversa (user + assistant = 1 turno)
MAX_MESSAGES = 20
# Tempo de expiração da conversa sem atividade (segundos) — 24 horas
TTL_SECONDS = 60 * 60 * 24

_redis_client: redis.Redis | None = None
_redis_uri_cached: str | None = None
_lock = threading.Lock()
_fallback_store: dict[str, tuple[float, list[dict[str, Any]]]] = {}
_fallback_kv: dict[str, tuple[float, str]] = {}


def _get_redis() -> redis.Redis | None:
    """Obtém cliente Redis de forma lazy; retorna None se URI não configurada."""
    global _redis_client, _redis_uri_cached
    uri = os.environ.get("CACHE_REDIS_URI", "").strip()
    if not uri:
        return None
    if _redis_client is not None and _redis_uri_cached == uri:
        return _redis_client
    with _lock:
        if _redis_client is None or _redis_uri_cached != uri:
            _redis_client = redis.from_url(
                uri,
                socket_connect_timeout=1.5,
                socket_timeout=1.5,
            )
            _redis_uri_cached = uri
    return _redis_client


def _key(jid: str) -> str:
    return f"c3po_bot:history:{jid}"


def get_history(jid: str) -> list[tuple[str, str]]:
    """Retorna o histórico de mensagens de um usuário como lista de tuplas (role, content)."""
    client = _get_redis()
    if client is not None:
        try:
            raw = client.get(_key(jid))
            if raw:
                return [(m["role"], m["content"]) for m in json.loads(raw)]
            return []
        except Exception as exc:
            logger.debug("Redis indisponível em get_history (%s); usando fallback em memória.", exc)

    with _lock:
        entry = _fallback_store.get(_key(jid))
        if not entry:
            return []
        expires_at, history = entry
        if time.time() > expires_at:
            _fallback_store.pop(_key(jid), None)
            return []
        return [(m["role"], m["content"]) for m in history]


def append_messages(jid: str, user_msg: str, assistant_msg: str) -> None:
    """Adiciona um turno (user + assistant) ao histórico e renova o TTL."""
    client = _get_redis()
    if client is not None:
        try:
            raw = client.get(_key(jid))
            history: list[dict[str, Any]] = json.loads(raw) if raw else []
            history.append({"role": "user", "content": user_msg})
            history.append({"role": "assistant", "content": assistant_msg})
            if len(history) > MAX_MESSAGES:
                history = history[-MAX_MESSAGES:]
            client.setex(_key(jid), TTL_SECONDS, json.dumps(history, ensure_ascii=False))
            return
        except Exception as exc:
            logger.debug("Redis indisponível em append_messages (%s); usando fallback em memória.", exc)

    with _lock:
        entry = _fallback_store.get(_key(jid))
        history = list(entry[1]) if entry and time.time() <= entry[0] else []
        history.append({"role": "user", "content": user_msg})
        history.append({"role": "assistant", "content": assistant_msg})
        if len(history) > MAX_MESSAGES:
            history = history[-MAX_MESSAGES:]
        _fallback_store[_key(jid)] = (time.time() + TTL_SECONDS, history)


def clear_history(jid: str) -> None:
    """Apaga o histórico de um usuário."""
    client = _get_redis()
    if client is not None:
        try:
            client.delete(_key(jid))
        except Exception as exc:
            logger.debug("Redis indisponível em clear_history (%s).", exc)
    with _lock:
        _fallback_store.pop(_key(jid), None)


def kv_set(key: str, value: str, ttl_seconds: int) -> None:
    """Armazena chave/valor temporária com TTL no Redis ou em memória (ex.: OTP)."""
    client = _get_redis()
    if client is not None:
        try:
            client.setex(key, ttl_seconds, value)
            return
        except Exception as exc:
            logger.debug("Redis indisponível em kv_set (%s); usando fallback em memória.", exc)
    with _lock:
        _fallback_kv[key] = (time.time() + ttl_seconds, value)


def kv_get(key: str) -> str | None:
    """Recupera valor temporário do Redis ou fallback em memória."""
    client = _get_redis()
    if client is not None:
        try:
            raw = client.get(key)
            if raw is None:
                return None
            return raw.decode("utf-8") if isinstance(raw, bytes) else str(raw)
        except Exception as exc:
            logger.debug("Redis indisponível em kv_get (%s); usando fallback em memória.", exc)
    with _lock:
        entry = _fallback_kv.get(key)
        if not entry:
            return None
        expires_at, val = entry
        if time.time() > expires_at:
            _fallback_kv.pop(key, None)
            return None
        return val


def kv_delete(key: str) -> None:
    """Remove chave temporária do Redis e do fallback em memória."""
    client = _get_redis()
    if client is not None:
        try:
            client.delete(key)
        except Exception as exc:
            logger.debug("Redis indisponível em kv_delete (%s).", exc)
    with _lock:
        _fallback_kv.pop(key, None)
