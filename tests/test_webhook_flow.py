from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException
from fastapi.testclient import TestClient
import pytest

from app.api.webhook import (
    ActionType,
    EvolutionWebhookParser,
    ExecutionResult,
    TriageDecision,
    WebhookEvent,
    WebhookResponder,
    WebhookTriageEngine,
)
from app.api.webhook.handlers.agent_handler import AgentHandler, DEFAULT_FALLBACK_REPLY
from app.api.webhook.handlers.command_handler import CommandHandler
from app.main import app


def _make_payload(
    text: str | None = "Olá",
    *,
    event: str = "messages.upsert",
    from_me: bool = False,
    remote_jid: str = "5511999999999@s.whatsapp.net",
    push_name: str = "Arthur",
    use_extended: bool = False,
) -> dict:
    message_obj: dict = {}
    if text is not None:
        if use_extended:
            message_obj = {"extendedTextMessage": {"text": text}}
        else:
            message_obj = {"conversation": text}

    return {
        "event": event,
        "data": {
            "key": {
                "remoteJid": remote_jid,
                "fromMe": from_me,
            },
            "pushName": push_name,
            "message": message_obj,
        },
    }


# ─── Camada 1: Parser (EvolutionWebhookParser) ───────────────────────────────


def test_parser_extracts_conversation_message():
    payload = _make_payload("  /Status-Win  ")
    event = EvolutionWebhookParser.parse(payload)

    assert event.event_type == "messages.upsert"
    assert event.remote_jid == "5511999999999@s.whatsapp.net"
    assert event.push_name == "Arthur"
    assert event.from_me is False
    assert event.message_text == "  /Status-Win  "
    assert event.normalized_command == "/status-win"


def test_parser_extracts_extended_text_message():
    payload = _make_payload("Texto estendido", use_extended=True)
    event = EvolutionWebhookParser.parse(payload)

    assert event.message_text == "Texto estendido"


@pytest.mark.parametrize(
    "malformed_payload",
    [
        {},
        {"event": None, "data": None},
        {"event": "messages.upsert", "data": "invalid_str"},
        {"event": "messages.upsert", "data": {"key": None, "message": None}},
        {"event": "messages.upsert", "data": {"message": {"extendedTextMessage": None}}},
        None,
        ["not", "a", "dict"],
    ],
)
def test_parser_resilient_to_malformed_payloads(malformed_payload):
    event = EvolutionWebhookParser.parse(malformed_payload)
    assert isinstance(event, WebhookEvent)
    assert event.message_text == ""
    assert event.from_me is False


# ─── Camada 2: Triagem (WebhookTriageEngine) ─────────────────────────────────


def test_triage_ignores_unhandled_event():
    event = EvolutionWebhookParser.parse(_make_payload("oi", event="connection.update"))
    decision = WebhookTriageEngine.evaluate(event)

    assert decision.action == ActionType.IGNORE
    assert decision.reason == "event_not_handled"


def test_triage_ignores_from_me():
    event = EvolutionWebhookParser.parse(_make_payload("oi", from_me=True))
    decision = WebhookTriageEngine.evaluate(event)

    assert decision.action == ActionType.IGNORE
    assert decision.reason == "fromMe"


@pytest.mark.parametrize("empty_text", ["", "   ", None])
def test_triage_ignores_empty_message(empty_text):
    event = EvolutionWebhookParser.parse(_make_payload(empty_text))
    decision = WebhookTriageEngine.evaluate(event)

    assert decision.action == ActionType.IGNORE
    assert decision.reason == "empty_message"


@pytest.mark.parametrize(
    "raw_cmd,expected_canonical",
    [
        ("/help", "/help"),
        (" /HELP ", "/help"),
        ("/ligar-win", "/ligar-win"),
        ("/desligar-win", "/desligar-win"),
        ("/reiniciar-win", "/reiniciar-win"),
        ("/reniciar-win", "/reiniciar-win"),
        ("/status-win", "/status-win"),
        ("/status", "/status-win"),
    ],
)
def test_triage_routes_known_commands_and_aliases(raw_cmd: str, expected_canonical: str):
    event = EvolutionWebhookParser.parse(_make_payload(raw_cmd))
    decision = WebhookTriageEngine.evaluate(event)

    assert decision.action == ActionType.COMMAND
    assert decision.command_key == expected_canonical


def test_triage_routes_regular_message_to_agent():
    event = EvolutionWebhookParser.parse(_make_payload("Comprei 20 reais de pão"))
    decision = WebhookTriageEngine.evaluate(event)

    assert decision.action == ActionType.AGENT
    assert decision.command_key is None


# ─── Camada 3: Handlers (CommandHandler e AgentHandler) ──────────────────────


@pytest.mark.asyncio
async def test_command_handler_help():
    handler = CommandHandler()
    event = EvolutionWebhookParser.parse(_make_payload("/help"))
    decision = TriageDecision(action=ActionType.COMMAND, command_key="/help")

    result = await handler.handle(event, decision)

    assert result.status == "success"
    assert result.response_code == "help_command_received"
    assert result.use_http_exception_envelope is True
    assert "Comandos disponíveis:" in (result.reply_text or "")
    assert "/ligar-win" in (result.reply_text or "")


@pytest.mark.asyncio
async def test_agent_handler_persists_memory_and_returns_reply():
    handler = AgentHandler()
    event = EvolutionWebhookParser.parse(_make_payload("Gastei 50 no mercado"))
    decision = TriageDecision(action=ActionType.AGENT)

    with patch("app.api.webhook.append_messages") as mock_append:
        result = await handler.handle(event, decision)

    assert result.status == "success"
    assert result.reply_text == DEFAULT_FALLBACK_REPLY
    assert result.use_http_exception_envelope is False
    mock_append.assert_called_once_with(
        "5511999999999@s.whatsapp.net",
        "5511999999999@s.whatsapp.net | Arthur : Gastei 50 no mercado",
        DEFAULT_FALLBACK_REPLY,
    )


# ─── Camada 4: Responder (WebhookResponder) ──────────────────────────────────


def test_responder_respond_ignored_raises_400():
    decision = TriageDecision(action=ActionType.IGNORE, reason="fromMe")
    with pytest.raises(HTTPException) as exc_info:
        WebhookResponder.respond_ignored(decision)

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == {"status": "ignored", "reason": "fromMe"}


@pytest.mark.asyncio
async def test_responder_supports_sync_and_async_send_text():
    event = EvolutionWebhookParser.parse(_make_payload("oi"))
    result = ExecutionResult(
        status="success",
        reply_text="Resposta teste",
        response_code="Resposta teste",
        use_http_exception_envelope=False,
        metadata={"status": "success", "reply": "Resposta teste"},
    )

    # Mock síncrono (não awaitable)
    with patch("app.api.webhook.send_text", new=MagicMock(return_value=None)) as mock_sync:
        out = await WebhookResponder.dispatch_and_respond(event, result)
        assert out == {"status": "success", "reply": "Resposta teste"}
        mock_sync.assert_called_once_with(to=event.remote_jid, text="Resposta teste")


# ─── Integração Ponta a Ponta na Rota POST /webhook ──────────────────────────


def test_webhook_endpoint_help_command():
    with patch("app.api.webhook.send_text", new_callable=AsyncMock) as mock_send:
        client = TestClient(app)
        resp = client.post("/webhook", json=_make_payload("/help"))

        assert resp.status_code == 200
        detail = resp.json()["detail"]
        assert detail["status"] == "success"
        assert detail["reply"] == "help_command_received"
        mock_send.assert_awaited_once()


def test_webhook_endpoint_agent_flow():
    with patch("app.api.webhook.append_messages") as mock_append:
        with patch("app.api.webhook.send_text", new_callable=AsyncMock) as mock_send:
            client = TestClient(app)
            resp = client.post("/webhook", json=_make_payload("Olá C3PO", use_extended=True))

            assert resp.status_code == 200
            body = resp.json()
            assert body["status"] == "success"
            assert body["reply"] == DEFAULT_FALLBACK_REPLY
            mock_append.assert_called_once()
            mock_send.assert_awaited_once_with(
                to="5511999999999@s.whatsapp.net",
                text=DEFAULT_FALLBACK_REPLY,
            )


@pytest.mark.parametrize(
    "payload,expected_reason",
    [
        (_make_payload("oi", event="other.event"), "event_not_handled"),
        (_make_payload("oi", from_me=True), "fromMe"),
        (_make_payload(""), "empty_message"),
    ],
)
def test_webhook_endpoint_ignored_events_return_400(payload: dict, expected_reason: str):
    client = TestClient(app)
    resp = client.post("/webhook", json=payload)

    assert resp.status_code == 400
    assert resp.json()["detail"] == {"status": "ignored", "reason": expected_reason}


def test_webhook_endpoint_handles_unexpected_exception_safely():
    with patch("app.api.webhook.send_text", new_callable=AsyncMock, side_effect=RuntimeError("db_secret_error")):
        with patch("app.api.webhook.append_messages"):
            client = TestClient(app)
            resp = client.post("/webhook", json=_make_payload("Olá"))

            assert resp.status_code == 200
            body = resp.json()
            assert body == {"status": "error", "message": "Internal server error"}
            assert "db_secret_error" not in resp.text
