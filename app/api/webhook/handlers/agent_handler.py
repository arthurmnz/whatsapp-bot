import logging

from sqlalchemy.orm import Session

from app.agent.orchestrator import AgentOrchestrator
from app.api.webhook.handlers.base import BaseHandler
from app.api.webhook.schemas import ExecutionResult, TriageDecision, WebhookEvent
import app.api.webhook as webhook_pkg

logger = logging.getLogger(__name__)

DEFAULT_FALLBACK_REPLY = "Desculpe, não consegui gerar uma resposta no momento."

_orchestrator = AgentOrchestrator()


class AgentHandler(BaseHandler):
    """Camada 3 (Agente): Processa mensagens conversacionais via AgentOrchestrator e persiste histórico."""

    async def handle(
        self,
        event: WebhookEvent,
        decision: TriageDecision,
        db: Session | None = None,
    ) -> ExecutionResult:
        current_msg = f"{event.remote_jid} | {event.push_name} : {event.message_text}"

        try:
            agent_resp = await _orchestrator.process_message(
                db=db,
                user=decision.user,
                message=event.message_text,
                channel="whatsapp",
                attachment=event.attachment,
                remote_jid=event.remote_jid,
            )
            reply = agent_resp.reply_text or DEFAULT_FALLBACK_REPLY
            generated_file_path = agent_resp.generated_file_path
            generated_filename = agent_resp.generated_filename
            thread_id = agent_resp.thread_id
        except Exception as exc:
            logger.exception("Erro no AgentOrchestrator via WhatsApp: %s", exc)
            reply = DEFAULT_FALLBACK_REPLY
            generated_file_path = None
            generated_filename = None
            thread_id = None

        # Persiste o turno no Redis via append_messages
        webhook_pkg.append_messages(event.remote_jid, current_msg, reply)

        metadata: dict = {
            "status": "success",
            "reply": reply,
        }
        if thread_id is not None:
            metadata["thread_id"] = thread_id
        if generated_file_path:
            metadata["generated_file_path"] = generated_file_path
            metadata["generated_filename"] = generated_filename or "curriculo.pdf"

        return ExecutionResult(
            status="success",
            reply_text=reply,
            response_code=reply,
            use_http_exception_envelope=False,
            metadata=metadata,
        )
