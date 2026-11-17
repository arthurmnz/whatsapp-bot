from typing import Any

from app.api.webhook.schemas import ActionType, TriageDecision, WebhookEvent
from app.core.crypto import verify_registration_password
from app.db.repositories.user_repo import user_has_permission

KNOWN_COMMANDS: dict[str, str] = {
    "/help": "Exibe os comandos disponíveis.",
    "/ligar-win": "Liga o PC Windows.",
    "/desligar-win": "Desliga o PC Windows.",
    "/reiniciar-win": "Reinicia o PC Windows.",
    "/status-win": "Verifica se o PC com Windows está Online.",
}

COMMAND_ALIASES: dict[str, str] = {
    "/help": "/help",
    "/ligar-win": "/ligar-win",
    "/desligar-win": "/desligar-win",
    "/reiniciar-win": "/reiniciar-win",
    "/reniciar-win": "/reiniciar-win",
    "/status-win": "/status-win",
    "/status": "/status-win",
}

COMMAND_PERMISSIONS: dict[str, str] = {
    "/help": "cmd:help",
    "/status-win": "cmd:status_windows",
    "/ligar-win": "cmd:wake_windows",
    "/desligar-win": "cmd:shutdown_windows",
    "/reiniciar-win": "cmd:restart_windows",
}

_UNSET = object()


class WebhookTriageEngine:
    """Camada 2: Triagem de eventos, validação de cadastro e controle de acesso (RBAC)."""

    @staticmethod
    def evaluate(event: WebhookEvent, user: Any = _UNSET) -> TriageDecision:
        if event.event_type != "messages.upsert":
            return TriageDecision(action=ActionType.IGNORE, reason="event_not_handled")

        if event.from_me:
            return TriageDecision(action=ActionType.IGNORE, reason="fromMe")

        if not event.message_text or not event.message_text.strip():
            return TriageDecision(action=ActionType.IGNORE, reason="empty_message")

        raw_text = event.message_text.strip()
        cmd = event.normalized_command

        # Caso `user` tenha sido explicitamente passado como None (usuário não cadastrado no banco):
        if user is None:
            if cmd == "/registrar":
                parts = raw_text.split(maxsplit=2)
                if len(parts) < 3 or not parts[2].strip():
                    return TriageDecision(
                        action=ActionType.IGNORE,
                        reason="invalid_registration_attempt",
                    )
                candidate_password = parts[1]
                if not verify_registration_password(candidate_password):
                    return TriageDecision(
                        action=ActionType.IGNORE,
                        reason="invalid_registration_attempt",
                    )
                return TriageDecision(
                    action=ActionType.REGISTER,
                    command_key="/registrar",
                )
            return TriageDecision(
                action=ActionType.IGNORE,
                reason="unregistered_user",
            )

        # Se o usuário já está cadastrado (ou em chamada legada sem `user` informado):
        actual_user = None if user is _UNSET else user

        if cmd == "/registrar":
            return TriageDecision(
                action=ActionType.REGISTER,
                command_key="/registrar",
                user=actual_user,
            )

        # Verifica se a mensagem inteira (normalizada) é um comando conhecido
        full_lower = raw_text.lower()
        canonical_cmd = COMMAND_ALIASES.get(full_lower) or COMMAND_ALIASES.get(cmd)
        if canonical_cmd is not None and full_lower in COMMAND_ALIASES:
            required_perm = COMMAND_PERMISSIONS.get(canonical_cmd)
            if actual_user is not None and required_perm is not None:
                if not user_has_permission(actual_user, required_perm):
                    return TriageDecision(
                        action=ActionType.UNAUTHORIZED,
                        command_key=canonical_cmd,
                        reason="permission_denied",
                        user=actual_user,
                        required_permission=required_perm,
                    )
            return TriageDecision(
                action=ActionType.COMMAND,
                command_key=canonical_cmd,
                user=actual_user,
                required_permission=required_perm,
            )

        # Mensagem conversacional livre -> Agente
        required_agent_perm = "agent:chat"
        if actual_user is not None and not user_has_permission(actual_user, required_agent_perm):
            return TriageDecision(
                action=ActionType.UNAUTHORIZED,
                reason="permission_denied",
                user=actual_user,
                required_permission=required_agent_perm,
            )

        return TriageDecision(
            action=ActionType.AGENT,
            user=actual_user,
            required_permission=required_agent_perm,
        )
