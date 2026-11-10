from app.core.memory import append_messages
from app.integrations.evolution import send_text
from app.modules.devices_control import (
    get_windows_status,
    restart_windows,
    shutdown_windows,
    wake_windows,
)

from app.api.webhook.parser import EvolutionWebhookParser
from app.api.webhook.responder import WebhookResponder
from app.api.webhook.router import evolution_webhook, router
from app.api.webhook.schemas import ActionType, ExecutionResult, TriageDecision, WebhookEvent
from app.api.webhook.triage import COMMAND_ALIASES, KNOWN_COMMANDS, WebhookTriageEngine

commands = KNOWN_COMMANDS

__all__ = [
    "router",
    "evolution_webhook",
    "commands",
    "KNOWN_COMMANDS",
    "COMMAND_ALIASES",
    "ActionType",
    "WebhookEvent",
    "TriageDecision",
    "ExecutionResult",
    "EvolutionWebhookParser",
    "WebhookTriageEngine",
    "WebhookResponder",
    "send_text",
    "append_messages",
    "wake_windows",
    "shutdown_windows",
    "restart_windows",
    "get_windows_status",
]
