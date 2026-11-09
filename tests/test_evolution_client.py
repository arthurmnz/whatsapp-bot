import os
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.evolution_client import (
    _build_payloads,
    _get_alternative_recipients,
    _mask_sensitive,
    send_text,
    send_text_sync,
)


# ─── 1. test_build_payloads ───────────────────────────────────────────────────

def test_build_payloads():
    to = "5511999999999@s.whatsapp.net"
    text = "Olá, tudo bem?"
    payloads = _build_payloads(to, text)

    assert isinstance(payloads, list)
    assert len(payloads) == 2

    # Formato v2
    assert payloads[0] == {"number": to, "text": text}

    # Formato de compatibilidade v1
    assert payloads[1] == {
        "number": to,
        "textMessage": {"text": text},
        "options": {"delay": 1200, "presence": "composing"},
    }


# ─── 2. test_get_alternative_recipients_9_to_8 ───────────────────────────────

def test_get_alternative_recipients_9_to_8():
    # Com + e 9 dígitos (ex: +5574999298992) -> converte para 8 dígitos
    alt = _get_alternative_recipients("+5574999298992")
    assert alt == ["557499298992@s.whatsapp.net"]

    # Com sufixo @s.whatsapp.net
    alt2 = _get_alternative_recipients("5574999298992@s.whatsapp.net")
    assert alt2 == ["557499298992@s.whatsapp.net"]

    # Sem +
    alt3 = _get_alternative_recipients("5574999298992")
    assert alt3 == ["557499298992@s.whatsapp.net"]


# ─── 3. test_get_alternative_recipients_8_to_9 ───────────────────────────────

def test_get_alternative_recipients_8_to_9():
    # Com 8 dígitos (ex: 557499298992@s.whatsapp.net) -> converte para 9 dígitos
    alt = _get_alternative_recipients("557499298992@s.whatsapp.net")
    assert alt == ["5574999298992@s.whatsapp.net"]

    # Com +
    alt2 = _get_alternative_recipients("+557499298992")
    assert alt2 == ["5574999298992@s.whatsapp.net"]

    # Sem + nem sufixo
    alt3 = _get_alternative_recipients("557499298992")
    assert alt3 == ["5574999298992@s.whatsapp.net"]


# ─── 4. test_mask_sensitive ───────────────────────────────────────────────────

def test_mask_sensitive():
    secret = "minha-chave-secreta-12345"
    text = f"Erro na requisição com apikey={secret} e url=http://example.com"
    masked = _mask_sensitive(text, secret)

    assert secret not in masked
    assert "***REDACTED***" in masked
    assert masked == "Erro na requisição com apikey=***REDACTED*** e url=http://example.com"

    # String vazia de segredo não deve alterar o texto
    assert _mask_sensitive("texto normal", "") == "texto normal"


# ─── 5. test_send_text_async_success ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_send_text_async_success():
    to = "5511999999999@s.whatsapp.net"
    text = "Mensagem assíncrona de teste"

    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.is_error = False
    mock_resp.status_code = 200
    mock_resp.text = '{"status": "SUCCESS"}'

    with patch.dict(os.environ, {
        "EVOLUTION_API_URL": "http://evolution-api:8080",
        "EVOLUTION_API_KEY": "test-key-123",
        "EVOLUTION_INSTANCE": "instancia_teste",
    }):
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp) as mock_post:
            await send_text(to=to, text=text)

            mock_post.assert_called_once()
            call_url = mock_post.call_args[0][0]
            call_kwargs = mock_post.call_args[1]

            assert call_url == "http://evolution-api:8080/message/sendText/instancia_teste"
            assert call_kwargs["headers"] == {"apikey": "test-key-123", "Content-Type": "application/json"}
            assert call_kwargs["json"] == {"number": to, "text": text}


# ─── 6. test_send_text_sync_success ───────────────────────────────────────────

def test_send_text_sync_success():
    to = "5511999999999@s.whatsapp.net"
    text = "Mensagem síncrona de teste"

    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.is_error = False
    mock_resp.status_code = 200
    mock_resp.text = '{"status": "SUCCESS"}'

    with patch.dict(os.environ, {
        "EVOLUTION_API_URL": "http://evolution-api:8080",
        "EVOLUTION_API_KEY": "test-key-123",
        "EVOLUTION_INSTANCE": "instancia_teste",
    }):
        with patch("httpx.Client.post", return_value=mock_resp) as mock_post:
            send_text_sync(to=to, text=text)

            mock_post.assert_called_once()
            call_url = mock_post.call_args[0][0]
            call_kwargs = mock_post.call_args[1]

            assert call_url == "http://evolution-api:8080/message/sendText/instancia_teste"
            assert call_kwargs["headers"] == {"apikey": "test-key-123", "Content-Type": "application/json"}
            assert call_kwargs["json"] == {"number": to, "text": text}


# ─── 7. test_send_text_fallback_v1_on_400 ─────────────────────────────────────

@pytest.mark.asyncio
async def test_send_text_fallback_v1_on_400():
    to = "5511999999999@s.whatsapp.net"
    text = "Teste fallback formato v1"

    resp_400 = MagicMock(spec=httpx.Response)
    resp_400.is_error = True
    resp_400.status_code = 400
    resp_400.text = '{"status": 400, "error": "Bad Request", "response": {"message": ["property textMessage should not exist"]}}'

    resp_200 = MagicMock(spec=httpx.Response)
    resp_200.is_error = False
    resp_200.status_code = 200
    resp_200.text = '{"status": "SUCCESS"}'

    with patch.dict(os.environ, {
        "EVOLUTION_API_URL": "http://evolution-api:8080",
        "EVOLUTION_API_KEY": "test-key-123",
        "EVOLUTION_INSTANCE": "minha_instancia",
    }):
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, side_effect=[resp_400, resp_200]) as mock_post:
            await send_text(to=to, text=text)

            assert mock_post.call_count == 2
            # 1ª tentativa: formato v2
            assert mock_post.call_args_list[0][1]["json"] == {"number": to, "text": text}
            # 2ª tentativa: formato v1
            assert mock_post.call_args_list[1][1]["json"] == {
                "number": to,
                "textMessage": {"text": text},
                "options": {"delay": 1200, "presence": "composing"},
            }


# ─── 8. test_send_text_alternative_recipient_fallback ─────────────────────────

@pytest.mark.asyncio
async def test_send_text_alternative_recipient_fallback():
    original = "+5574999298992"
    expected_alt = "557499298992@s.whatsapp.net"
    text = "Teste fallback 9º dígito"

    # Falha no número original (400 sem menção a textMessage)
    resp_fail = MagicMock(spec=httpx.Response)
    resp_fail.is_error = True
    resp_fail.status_code = 400
    resp_fail.text = '{"status": 400, "error": "Recipient number not registered"}'

    resp_success = MagicMock(spec=httpx.Response)
    resp_success.is_error = False
    resp_success.status_code = 200
    resp_success.text = '{"status": "SUCCESS"}'

    with patch.dict(os.environ, {
        "EVOLUTION_API_URL": "http://evolution-api:8080",
        "EVOLUTION_API_KEY": "test-key-123",
        "EVOLUTION_INSTANCE": "minha_instancia",
    }):
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, side_effect=[resp_fail, resp_success]) as mock_post:
            await send_text(to=original, text=text)

            assert mock_post.call_count == 2
            # 1ª tentativa com número original
            assert mock_post.call_args_list[0][1]["json"]["number"] == original
            # 2ª tentativa com número corrigido
            assert mock_post.call_args_list[1][1]["json"]["number"] == expected_alt


# ─── 9. test_send_text_error_does_not_leak_api_key ─────────────────────────────

@pytest.mark.asyncio
async def test_send_text_error_does_not_leak_api_key():
    to = "5511999999999@s.whatsapp.net"
    text = "Mensagem que deve falhar"
    secret_key = "super-secret-key-xyz"

    mock_req = httpx.Request("POST", "http://evolution-api:8080/message/sendText/instancia")
    resp_err = httpx.Response(
        status_code=500,
        text=f"Internal Server Error: apikey={secret_key} authorization failed",
        request=mock_req,
    )

    with patch.dict(os.environ, {
        "EVOLUTION_API_URL": "http://evolution-api:8080",
        "EVOLUTION_API_KEY": secret_key,
        "EVOLUTION_INSTANCE": "instancia",
    }):
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=resp_err):
            with pytest.raises(httpx.HTTPStatusError) as exc_info:
                await send_text(to=to, text=text)

            err_str = str(exc_info.value)
            assert secret_key not in err_str
            assert "***REDACTED***" in err_str
            assert exc_info.value.response.status_code == 500
