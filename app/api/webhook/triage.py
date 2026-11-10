from app.api.webhook.schemas import ActionType, TriageDecision, WebhookEvent

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


class WebhookTriageEngine:
    """Camada 2: Triagem de eventos e classificação da rota de execução."""

    @staticmethod
    def evaluate(event: WebhookEvent) -> TriageDecision:
        if event.event_type != "messages.upsert":
            return TriageDecision(action=ActionType.IGNORE, reason="event_not_handled")

        if event.from_me:
            return TriageDecision(action=ActionType.IGNORE, reason="fromMe")

        if not event.message_text or not event.message_text.strip():
            return TriageDecision(action=ActionType.IGNORE, reason="empty_message")

        cmd = event.normalized_command
        canonical_cmd = COMMAND_ALIASES.get(cmd)
        if canonical_cmd is not None:
            return TriageDecision(
                action=ActionType.COMMAND,
                command_key=canonical_cmd,
            )

        return TriageDecision(action=ActionType.AGENT)
