import datetime
import hmac
import logging
import os

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.webhook.handlers.agent_handler import AgentHandler
from app.api.webhook.handlers.command_handler import CommandHandler
from app.api.webhook.handlers.register_handler import RegisterHandler
from app.api.webhook.handlers.unauthorized_handler import UnauthorizedHandler
from app.api.webhook.parser import EvolutionWebhookParser
from app.api.webhook.responder import WebhookResponder
from app.api.webhook.schemas import ActionType
from app.api.webhook.triage import WebhookTriageEngine
from app.db.repositories.user_repo import get_user_by_jid
from app.db.session import get_db

router = APIRouter()
logger = logging.getLogger(__name__)

_parser = EvolutionWebhookParser()
_triage = WebhookTriageEngine()
_command_handler = CommandHandler()
_agent_handler = AgentHandler()
_register_handler = RegisterHandler()
_unauthorized_handler = UnauthorizedHandler()
_responder = WebhookResponder()


def _strip_log_newlines(value: str) -> str:
    return (value or "").replace("\r", " ").replace("\n", " ")


def sanitize_message_for_log(message_text: str) -> str:
    """Mascara a senha quando a mensagem é um comando `/registrar` e previne log injection."""
    stripped = (message_text or "").strip()
    if not stripped:
        return ""
    parts = stripped.split(maxsplit=2)
    if parts[0].lower() == "/registrar":
        if len(parts) == 1:
            return parts[0]
        if len(parts) == 2:
            return f"{parts[0]} ***"
        return _strip_log_newlines(f"{parts[0]} *** {parts[2]}")
    return _strip_log_newlines(message_text)



def _verify_webhook_token_if_configured(request: Request) -> None:
    expected = (
        os.environ.get("WEBHOOK_SECRET_TOKEN", "").strip()
        or os.environ.get("EVOLUTION_WEBHOOK_TOKEN", "").strip()
    )
    if not expected:
        return
    auth_hdr = request.headers.get("authorization", "")
    bearer = auth_hdr[7:].strip() if auth_hdr.lower().startswith("bearer ") else ""
    candidates = [
        request.headers.get("apikey", "").strip(),
        request.headers.get("x-webhook-token", "").strip(),
        bearer,
    ]
    if not any(c and hmac.compare_digest(c, expected) for c in candidates):
        raise HTTPException(status_code=401, detail="Token de webhook inválido ou ausente.")


@router.post("/webhook")
async def evolution_webhook(request: Request, db: Session = Depends(get_db)):
    """Recebe eventos do Evolution API via webhook e coordena o fluxo em 4 camadas."""
    try:
        _verify_webhook_token_if_configured(request)
        raw_payload = await request.json()
        event = _parser.parse(raw_payload)

        user = None
        if (
            event.event_type == "messages.upsert"
            and not event.from_me
            and event.remote_jid
            and ((event.message_text and event.message_text.strip()) or event.attachment)
        ):
            user = get_user_by_jid(db, event.remote_jid)

        decision = _triage.evaluate(event, user=user)

        if decision.action == ActionType.IGNORE:
            _responder.respond_ignored(decision)

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        safe_text = sanitize_message_for_log(event.message_text)
        safe_jid = _strip_log_newlines(event.remote_jid)
        safe_push = _strip_log_newlines(event.push_name)
        logger.info(
            "Mensagem recebida de %s (%s): %s - %s",
            safe_jid,
            safe_push,
            safe_text,
            timestamp,
        )

        if decision.action == ActionType.REGISTER:
            result = await _register_handler.handle(event, decision, db=db)
        elif decision.action == ActionType.UNAUTHORIZED:
            result = await _unauthorized_handler.handle(event, decision)
        elif decision.action == ActionType.COMMAND:
            result = await _command_handler.handle(event, decision)
        else:
            result = await _agent_handler.handle(event, decision, db=db)

        return await _responder.dispatch_and_respond(event, result)

    except HTTPException:
        raise
    except Exception:
        logger.exception("Erro inesperado ao processar webhook da Evolution API")
        return {"status": "error", "message": "Internal server error"}
