from app.api.webhook.handlers.base import BaseHandler
from app.api.webhook.schemas import ExecutionResult, TriageDecision, WebhookEvent

UNAUTHORIZED_REPLY = "⛔ Acesso negado. Seu perfil não possui permissão para executar esta função."


class UnauthorizedHandler(BaseHandler):
    """Camada 3 (Autorização): Retorna resposta padronizada quando falta permissão RBAC."""

    async def handle(self, event: WebhookEvent, decision: TriageDecision) -> ExecutionResult:
        return ExecutionResult(
            status="unauthorized",
            reply_text=UNAUTHORIZED_REPLY,
            response_code="permission_denied",
            use_http_exception_envelope=False,
            metadata={
                "status": "unauthorized",
                "reply": "permission_denied",
                "required_permission": decision.required_permission,
            },
        )
