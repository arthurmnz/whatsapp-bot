from dataclasses import dataclass, field
import json
import logging
import os
import re
from typing import Any, Literal
from urllib.parse import urlparse

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

load_dotenv()

logger = logging.getLogger(__name__)

_PROVIDER_DEFAULT_URLS: dict[str, str] = {
    "openrouter": "https://openrouter.ai/api/v1",
    "openai": "https://api.openai.com/v1",
    "ollama": "http://localhost:11434/v1",
    "openai_compatible": "http://localhost:11434/v1",
}

_PROVIDER_DEFAULT_MODELS: dict[str, str] = {
    "openrouter": "google/gemini-2.5-flash",
    "openai": "gpt-4o-mini",
    "ollama": "llama3.1",
    "openai_compatible": "llama3.1",
}


@dataclass(frozen=True)
class LLMConfig:
    provider: str
    base_url: str
    api_key: str = field(repr=False)
    chat_model: str
    cv_model: str
    temperature: float
    is_local: bool
    is_configured: bool

    def __repr__(self) -> str:
        return (
            f"LLMConfig(provider={self.provider!r}, base_url={self.base_url!r}, "
            f"api_key='***REDACTED***', chat_model={self.chat_model!r}, "
            f"cv_model={self.cv_model!r}, temperature={self.temperature}, "
            f"is_local={self.is_local}, is_configured={self.is_configured})"
        )


def _is_local_url(url: str) -> bool:
    try:
        host = (urlparse(url).hostname or "").lower()
    except Exception:
        return False
    return host in {"localhost", "127.0.0.1", "0.0.0.0", "ollama", "host.docker.internal"}


def get_llm_config() -> LLMConfig:
    """Resolve configuração agnóstica do provedor de IA via variáveis de ambiente."""
    raw_provider = os.environ.get("LLM_PROVIDER", "openrouter").strip().lower()
    provider = raw_provider if raw_provider in _PROVIDER_DEFAULT_URLS else "openai_compatible"

    default_url = _PROVIDER_DEFAULT_URLS[provider]
    base_url = os.environ.get("LLM_BASE_URL", "").strip() or default_url

    raw_key = (
        os.environ.get("LLM_API_KEY", "").strip()
        or os.environ.get("OPENROUTER_API_KEY", "").strip()
        or os.environ.get("OPEN_ROUTER_KEY", "").strip()
        or os.environ.get("OPENAI_API_KEY", "").strip()
    )

    local_endpoint = provider == "ollama" or _is_local_url(base_url)
    if local_endpoint and not raw_key:
        api_key = "local"
        is_configured = True
    else:
        api_key = raw_key
        is_configured = bool(raw_key)

    default_model = _PROVIDER_DEFAULT_MODELS.get(provider, "llama3.1")
    chat_model = os.environ.get("LLM_CHAT_MODEL", "").strip() or default_model
    cv_model = os.environ.get("LLM_CV_MODEL", "").strip() or chat_model

    raw_temp = os.environ.get("LLM_TEMPERATURE", "0.3").strip()
    try:
        temperature = max(0.0, min(1.5, float(raw_temp)))
    except ValueError:
        temperature = 0.3

    return LLMConfig(
        provider=provider,
        base_url=base_url,
        api_key=api_key,
        chat_model=chat_model,
        cv_model=cv_model,
        temperature=temperature,
        is_local=local_endpoint,
        is_configured=is_configured,
    )


def get_llm_status_summary() -> dict[str, Any]:
    """Retorna metadados seguros da configuração de LLM para dashboard e diagnóstico."""
    cfg = get_llm_config()
    return {
        "provider": cfg.provider,
        "base_url": cfg.base_url,
        "chat_model": cfg.chat_model,
        "cv_model": cfg.cv_model,
        "temperature": cfg.temperature,
        "is_local": cfg.is_local,
        "available": cfg.is_configured,
    }


def get_chat_llm(
    purpose: Literal["chat", "cv"] = "chat",
    temperature: float | None = None,
    timeout: float = 45.0,
) -> ChatOpenAI | None:
    """Instancia ChatOpenAI compatível com OpenRouter, OpenAI, Ollama, LM Studio ou vLLM."""
    cfg = get_llm_config()
    if not cfg.is_configured:
        return None

    model_name = cfg.cv_model if purpose == "cv" else cfg.chat_model
    temp = cfg.temperature if temperature is None else temperature

    kwargs: dict[str, Any] = {
        "model": model_name,
        "api_key": cfg.api_key or "local",
        "base_url": cfg.base_url,
        "temperature": temp,
        "timeout": timeout,
        "max_retries": 1,
    }
    if cfg.provider == "openrouter":
        kwargs["default_headers"] = {
            "X-Title": "C3PO Career & Assistant",
        }
    return ChatOpenAI(**kwargs)


async def invoke_llm_text(
    system_prompt: str,
    user_prompt: str,
    purpose: Literal["chat", "cv"] = "chat",
    temperature: float | None = None,
    timeout: float = 45.0,
) -> str | None:
    """Invoca o LLM de forma resiliente; retorna None caso indisponível para ativar fallback."""
    llm = get_chat_llm(purpose=purpose, temperature=temperature, timeout=timeout)
    if llm is None:
        return None

    try:
        response = await llm.ainvoke(
            [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ]
        )
        content = getattr(response, "content", None)
        if isinstance(content, list):
            parts = [
                p.get("text", "") if isinstance(p, dict) else str(p)
                for p in content
            ]
            content = "\n".join(parts)
        text = str(content or "").strip()
        return text or None
    except Exception as exc:
        cfg = get_llm_config()
        safe_msg = str(exc)
        if cfg.api_key and cfg.api_key != "local":
            safe_msg = safe_msg.replace(cfg.api_key, "***REDACTED***")
        logger.warning(
            "Chamada LLM (%s/%s) falhou; ativando fallback determinístico: %s",
            cfg.provider,
            cfg.cv_model if purpose == "cv" else cfg.chat_model,
            safe_msg,
        )
        return None


def _extract_json_object(raw: str) -> dict[str, Any] | None:
    cleaned = raw.strip()
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", cleaned, re.IGNORECASE)
    if fence_match:
        cleaned = fence_match.group(1).strip()

    try:
        parsed = json.loads(cleaned)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end > start:
            try:
                parsed = json.loads(cleaned[start : end + 1])
                return parsed if isinstance(parsed, dict) else None
            except json.JSONDecodeError:
                return None
        return None


async def invoke_llm_json(
    system_prompt: str,
    user_prompt: str,
    purpose: Literal["chat", "cv"] = "cv",
    temperature: float | None = 0.15,
    timeout: float = 60.0,
) -> dict[str, Any] | None:
    """Invoca o LLM esperando resposta em JSON estruturado, retornando None se falhar."""
    raw = await invoke_llm_text(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        purpose=purpose,
        temperature=temperature,
        timeout=timeout,
    )
    if not raw:
        return None
    return _extract_json_object(raw)
