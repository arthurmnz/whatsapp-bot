from collections.abc import Awaitable, Callable

from app.api.webhook.handlers.base import BaseHandler
from app.api.webhook.schemas import ExecutionResult, TriageDecision, WebhookEvent
from app.api.webhook.triage import KNOWN_COMMANDS
import app.api.webhook as webhook_pkg


class CommandHandler(BaseHandler):
    """Camada 3 (Comandos): Processa comandos de sistema e controle de dispositivos."""

    def __init__(self) -> None:
        self._dispatch_table: dict[str, Callable[[WebhookEvent], Awaitable[ExecutionResult]]] = {
            "/help": self._handle_help,
            "/ligar-win": self._handle_wake_win,
            "/desligar-win": self._handle_shutdown_win,
            "/reiniciar-win": self._handle_restart_win,
            "/status-win": self._handle_status_win,
        }

    async def handle(self, event: WebhookEvent, decision: TriageDecision) -> ExecutionResult:
        cmd_key = decision.command_key or event.normalized_command
        handler_fn = self._dispatch_table.get(cmd_key)
        if handler_fn is None:
            return ExecutionResult(
                status="ignored",
                response_code="unknown_command",
            )
        return await handler_fn(event)

    async def _handle_help(self, event: WebhookEvent) -> ExecutionResult:
        help_lines = [f"- *{c}* - {desc}" for c, desc in KNOWN_COMMANDS.items()]
        reply_text = "💻 Comandos disponíveis:\n" + "\n".join(help_lines)
        return ExecutionResult(
            status="success",
            reply_text=reply_text,
            response_code="help_command_received",
            use_http_exception_envelope=True,
            metadata={
                "status": "success",
                "reply": "help_command_received",
            },
        )

    async def _handle_wake_win(self, event: WebhookEvent) -> ExecutionResult:
        result = await webhook_pkg.wake_windows()
        status_str = "success" if result.get("success") else "error"
        return ExecutionResult(
            status=status_str,
            reply_text=result.get("message", ""),
            response_code="pc_ligar_command_received",
            use_http_exception_envelope=True,
            metadata={
                "status": status_str,
                "reply": "pc_ligar_command_received",
                "result": result,
            },
        )

    async def _handle_shutdown_win(self, event: WebhookEvent) -> ExecutionResult:
        result = await webhook_pkg.shutdown_windows()
        status_str = "success" if result.get("success") else "error"
        return ExecutionResult(
            status=status_str,
            reply_text=result.get("message", ""),
            response_code="pc_desligar_command_received",
            use_http_exception_envelope=True,
            metadata={
                "status": status_str,
                "reply": "pc_desligar_command_received",
                "result": result,
            },
        )

    async def _handle_restart_win(self, event: WebhookEvent) -> ExecutionResult:
        result = await webhook_pkg.restart_windows()
        status_str = "success" if result.get("success") else "error"
        return ExecutionResult(
            status=status_str,
            reply_text=result.get("message", ""),
            response_code="pc_reiniciar_command_received",
            use_http_exception_envelope=True,
            metadata={
                "status": status_str,
                "reply": "pc_reiniciar_command_received",
                "result": result,
            },
        )

    async def _handle_status_win(self, event: WebhookEvent) -> ExecutionResult:
        result = await webhook_pkg.get_windows_status()
        return ExecutionResult(
            status="success",
            reply_text=result.get("message", ""),
            response_code="pc_status_command_received",
            use_http_exception_envelope=True,
            metadata={
                "status": "success",
                "reply": "pc_status_command_received",
                "online": result.get("online", False),
                "hostname": result.get("hostname"),
                "reason": result.get("reason"),
            },
        )
