from sqlalchemy.orm import Session

from app.api.webhook.handlers.base import BaseHandler
from app.api.webhook.schemas import ExecutionResult, TriageDecision, WebhookEvent
from app.core.crypto import verify_registration_password
from app.db.repositories.user_repo import create_registered_user


class RegisterHandler(BaseHandler):
    """Camada 3 (Registro): Processa o comando `/registrar <senha> <nome composto>`."""

    async def handle(
        self,
        event: WebhookEvent,
        decision: TriageDecision,
        db: Session | None = None,
    ) -> ExecutionResult:
        if decision.user is not None:
            reply_text = f"ℹ️ Você já está cadastrado, {decision.user.nome}!"
            return ExecutionResult(
                status="already_registered",
                reply_text=reply_text,
                response_code="already_registered",
                use_http_exception_envelope=False,
                metadata={
                    "status": "already_registered",
                    "reply": "already_registered",
                    "nome": decision.user.nome,
                },
            )

        parts = event.message_text.strip().split(maxsplit=2)
        if len(parts) < 3 or not parts[2].strip():
            return ExecutionResult(
                status="ignored",
                response_code="invalid_registration_attempt",
            )

        senha = parts[1]
        nome = parts[2].strip()

        if not verify_registration_password(senha):
            return ExecutionResult(
                status="ignored",
                response_code="invalid_registration_attempt",
            )

        if db is None:
            raise RuntimeError("Sessão do banco de dados é obrigatória para registrar novo usuário.")

        user = create_registered_user(db, event.remote_jid, nome, role_name="user")
        reply_text = (
            f"✅ Cadastro realizado com sucesso, {user.nome}! "
            "Bem-vindo ao C3PO. Digite /help para ver os comandos disponíveis."
        )
        return ExecutionResult(
            status="registered",
            reply_text=reply_text,
            response_code="user_registered",
            use_http_exception_envelope=False,
            metadata={
                "status": "registered",
                "reply": "user_registered",
                "nome": user.nome,
            },
        )
