import datetime
import logging

from fastapi import APIRouter, HTTPException, Request

from app.api.webhook.handlers.agent_handler import AgentHandler
from app.api.webhook.handlers.command_handler import CommandHandler
from app.api.webhook.parser import EvolutionWebhookParser
from app.api.webhook.responder import WebhookResponder
from app.api.webhook.schemas import ActionType
from app.api.webhook.triage import WebhookTriageEngine

router = APIRouter()
logger = logging.getLogger(__name__)

_parser = EvolutionWebhookParser()
_triage = WebhookTriageEngine()
_command_handler = CommandHandler()
_agent_handler = AgentHandler()
_responder = WebhookResponder()


@router.post("/webhook")
async def evolution_webhook(request: Request):
    """Recebe eventos do Evolution API via webhook e coordena o fluxo em 4 camadas."""
    try:
        raw_payload = await request.json()
        event = _parser.parse(raw_payload)
        decision = _triage.evaluate(event)

        if decision.action == ActionType.IGNORE:
            _responder.respond_ignored(decision)

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logger.info(
            "Mensagem recebida de %s (%s): %s - %s",
            event.remote_jid,
            event.push_name,
            event.message_text,
            timestamp,
        )

        if decision.action == ActionType.COMMAND:
            result = await _command_handler.handle(event, decision)
        else:
            result = await _agent_handler.handle(event, decision)

        return await _responder.dispatch_and_respond(event, result)

    except HTTPException:
        raise
    except Exception:
        logger.exception("Erro inesperado ao processar webhook da Evolution API")
        return {"status": "error", "message": "Internal server error"}
