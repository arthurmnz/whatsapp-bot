import json
import os

import redis
from dotenv import load_dotenv

load_dotenv()

_redis = redis.from_url(os.environ["CACHE_REDIS_URI"])

# Máximo de mensagens mantidas por conversa (user + assistant = 1 turno)
MAX_MESSAGES = 20
# Tempo de expiração da conversa sem atividade (segundos) — 24 horas
TTL_SECONDS = 60 * 60 * 24


def _key(jid: str) -> str:
    return f"finance_bot:history:{jid}"


def get_history(jid: str) -> list[tuple[str, str]]:
    """Retorna o histórico de mensagens de um usuário como lista de tuplas (role, content)."""
    raw = _redis.get(_key(jid))
    if not raw:
        return []
    return [(m["role"], m["content"]) for m in json.loads(raw)]


def append_messages(jid: str, user_msg: str, assistant_msg: str) -> None:
    """Adiciona um turno (user + assistant) ao histórico e renova o TTL."""
    raw = _redis.get(_key(jid))
    history: list[dict] = json.loads(raw) if raw else []

    history.append({"role": "user", "content": user_msg})
    history.append({"role": "assistant", "content": assistant_msg})

    # Mantém apenas as últimas MAX_MESSAGES mensagens
    if len(history) > MAX_MESSAGES:
        history = history[-MAX_MESSAGES:]

    _redis.setex(_key(jid), TTL_SECONDS, json.dumps(history, ensure_ascii=False))


def clear_history(jid: str) -> None:
    """Apaga o histórico de um usuário."""
    _redis.delete(_key(jid))
