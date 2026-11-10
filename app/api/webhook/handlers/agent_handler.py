from app.api.webhook.handlers.base import BaseHandler
from app.api.webhook.schemas import ExecutionResult, TriageDecision, WebhookEvent
import app.api.webhook as webhook_pkg

DEFAULT_FALLBACK_REPLY = "Desculpe, o agente não está implementado no momento."


class AgentHandler(BaseHandler):
    """Camada 3 (Agente): Processa mensagens conversacionais e persiste histórico no Redis."""

    async def handle(self, event: WebhookEvent, decision: TriageDecision) -> ExecutionResult:
        current_msg = f"{event.remote_jid} | {event.push_name} : {event.message_text}"

        response = {
            "messages": [
                {"role": "assistant", "content": DEFAULT_FALLBACK_REPLY}
            ]
        }
        reply = response["messages"][0].get("content", "Desculpe, não consegui gerar uma resposta.")

        # Persiste o turno no Redis via append_messages
        webhook_pkg.append_messages(event.remote_jid, current_msg, reply)

        return ExecutionResult(
            status="success",
            reply_text=reply,
            response_code=reply,
            use_http_exception_envelope=False,
            metadata={
                "status": "success",
                "reply": reply,
            },
        )
