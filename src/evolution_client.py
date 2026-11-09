import logging
import os
import re
from typing import Any

import httpx

logger = logging.getLogger(__name__)


def _get_evolution_config() -> tuple[str, str, str]:
    """Obtém as variáveis de ambiente necessárias para comunicação com a Evolution API.

    Retorna:
        tuple[str, str, str]: (base_url normalizada, api_key, instance)
    """
    base_url = os.environ.get("EVOLUTION_API_URL", "").rstrip("/")
    api_key = os.environ.get("EVOLUTION_API_KEY", "")
    instance = os.environ.get("EVOLUTION_INSTANCE", "")
    return base_url, api_key, instance


def _mask_sensitive(text: str, secret: str) -> str:
    """Substitui ocorrências de `secret` no texto por '***REDACTED***'.

    Se `secret` for vazio, retorna o texto sem modificações.
    """
    if not secret:
        return text
    return text.replace(secret, "***REDACTED***")


def _validate_recipient(to: str) -> None:
    """Valida se o destinatário não contém caracteres de controle inválidos."""
    if any(char in to for char in ("\r", "\n", "\0")):
        raise ValueError(f"Destinatário contém caracteres de controle inválidos: {to!r}")


def _build_payloads(to: str, text: str) -> list[dict[str, Any]]:
    """Gera payloads para envio de mensagem de texto nos formatos v2 e compatibilidade v1.

    Retorna:
        list[dict]: [payload_v2, payload_v1]
    """
    _validate_recipient(to)
    v2_payload = {
        "number": to,
        "text": text,
    }
    v1_payload = {
        "number": to,
        "textMessage": {"text": text},
        "options": {"delay": 1200, "presence": "composing"},
    }
    return [v2_payload, v1_payload]


def _get_alternative_recipients(to: str) -> list[str]:
    """Gera destinatários alternativos para números brasileiros tratando o nono dígito.

    Regra:
    - 55 + DDD (2 dígitos) + 9 dígitos (iniciado em 9) -> alterna para 8 dígitos
    - 55 + DDD (2 dígitos) + 8 dígitos -> alterna para 9 dígitos (inserindo 9 após DDD)
    """
    if "@g.us" in to:
        return []

    # Extrai a parte numérica antes do sufixo @
    base_part = to.split("@")[0]
    digits = re.sub(r"\D", "", base_part)

    if not digits.startswith("55"):
        return []

    if len(digits) == 13:
        # DDI 55 (2) + DDD (2) + 9 dígitos (9)
        ddd = digits[2:4]
        number = digits[4:]
        if number.startswith("9"):
            alt_number = f"55{ddd}{number[1:]}@s.whatsapp.net"
            return [alt_number]
    elif len(digits) == 12:
        # DDI 55 (2) + DDD (2) + 8 dígitos (8)
        ddd = digits[2:4]
        number = digits[4:]
        alt_number = f"55{ddd}9{number}@s.whatsapp.net"
        return [alt_number]

    return []


def _is_format_error(resp: httpx.Response) -> bool:
    """Verifica se o erro 400 é decorrente do formato do payload (schema/property)."""
    text = resp.text.lower()
    return "textmessage" in text or "property" in text or "schema" in text


def _raise_masked_error(resp: httpx.Response, api_key: str, fallback_url: str) -> None:
    """Levanta `httpx.HTTPStatusError` mascarando a api key na mensagem, headers e response."""
    masked_message = _mask_sensitive(
        f"HTTP error {resp.status_code}: {resp.text}",
        api_key,
    )
    request = getattr(resp, "request", None)
    if request is not None and hasattr(request, "headers") and "apikey" in request.headers:
        request.headers["apikey"] = "***REDACTED***"

    if api_key:
        if hasattr(resp, "_text") and isinstance(resp._text, str) and api_key in resp._text:
            resp._text = _mask_sensitive(resp._text, api_key)
        if hasattr(resp, "_content") and isinstance(resp._content, bytes):
            resp._content = resp._content.replace(api_key.encode("utf-8"), b"***REDACTED***")

    if request is None:
        request = httpx.Request("POST", fallback_url)

    raise httpx.HTTPStatusError(
        message=masked_message,
        request=request,
        response=resp,
    )


async def send_text(to: str, text: str) -> dict[str, Any]:
    """Envia mensagem de texto via Evolution API de forma assíncrona.

    Suporta fallback de payload v2 -> v1 e fallback para variação de 8/9 dígitos.
    """
    _validate_recipient(to)
    base_url, api_key, instance = _get_evolution_config()
    url = f"{base_url}/message/sendText/{instance}"
    headers = {
        "apikey": api_key,
        "Content-Type": "application/json",
    }

    recipients_to_try = [to]
    last_resp: httpx.Response | None = None

    async with httpx.AsyncClient(timeout=15.0) as client:
        idx = 0
        while idx < len(recipients_to_try):
            current_to = recipients_to_try[idx]
            idx += 1

            payloads = _build_payloads(current_to, text)
            # 1. Tenta formato v2
            resp = await client.post(url, headers=headers, json=payloads[0])
            last_resp = resp

            if not resp.is_error:
                try:
                    return resp.json()
                except Exception:
                    return {"status": "SUCCESS"}

            # Tratamento de status 400
            if resp.status_code == 400:
                if _is_format_error(resp):
                    # Tenta formato v1
                    resp_v1 = await client.post(url, headers=headers, json=payloads[1])
                    last_resp = resp_v1
                    if not resp_v1.is_error:
                        try:
                            return resp_v1.json()
                        except Exception:
                            return {"status": "SUCCESS"}
                else:
                    # Falha de destinatário: adiciona alternativas à fila
                    for alt in _get_alternative_recipients(current_to):
                        if alt not in recipients_to_try:
                            recipients_to_try.append(alt)
            else:
                # Erros não 400 (ex: 500) não acionam fallbacks
                break

    if last_resp is not None and last_resp.is_error:
        _raise_masked_error(last_resp, api_key, url)

    return {}


def send_text_sync(to: str, text: str) -> dict[str, Any]:
    """Envia mensagem de texto via Evolution API de forma síncrona.

    Suporta fallback de payload v2 -> v1 e fallback para variação de 8/9 dígitos.
    """
    _validate_recipient(to)
    base_url, api_key, instance = _get_evolution_config()
    url = f"{base_url}/message/sendText/{instance}"
    headers = {
        "apikey": api_key,
        "Content-Type": "application/json",
    }

    recipients_to_try = [to]
    last_resp: httpx.Response | None = None

    with httpx.Client(timeout=15.0) as client:
        idx = 0
        while idx < len(recipients_to_try):
            current_to = recipients_to_try[idx]
            idx += 1

            payloads = _build_payloads(current_to, text)
            # 1. Tenta formato v2
            resp = client.post(url, headers=headers, json=payloads[0])
            last_resp = resp

            if not resp.is_error:
                try:
                    return resp.json()
                except Exception:
                    return {"status": "SUCCESS"}

            # Tratamento de status 400
            if resp.status_code == 400:
                if _is_format_error(resp):
                    # Tenta formato v1
                    resp_v1 = client.post(url, headers=headers, json=payloads[1])
                    last_resp = resp_v1
                    if not resp_v1.is_error:
                        try:
                            return resp_v1.json()
                        except Exception:
                            return {"status": "SUCCESS"}
                else:
                    # Falha de destinatário: adiciona alternativas à fila
                    for alt in _get_alternative_recipients(current_to):
                        if alt not in recipients_to_try:
                            recipients_to_try.append(alt)
            else:
                # Erros não 400 (ex: 500) não acionam fallbacks
                break

    if last_resp is not None and last_resp.is_error:
        _raise_masked_error(last_resp, api_key, url)

    return {}
