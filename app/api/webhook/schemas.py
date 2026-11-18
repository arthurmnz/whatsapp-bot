from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class ActionType(str, Enum):
    IGNORE = "ignore"
    REGISTER = "register"
    UNAUTHORIZED = "unauthorized"
    COMMAND = "command"
    AGENT = "agent"


class WebhookEvent(BaseModel):
    """DTO padronizado representando um evento recebido da Evolution API."""

    event_type: str | None = None
    remote_jid: str = ""
    push_name: str = ""
    from_me: bool = False
    message_text: str = ""
    attachment: dict[str, Any] | None = None
    raw_payload: dict[str, Any] = Field(default_factory=dict)

    @property
    def normalized_command(self) -> str:
        text = self.message_text.strip()
        if not text:
            return ""
        first_token = text.split(maxsplit=1)[0].lower()
        return first_token if first_token.startswith("/") else text.lower()


class TriageDecision(BaseModel):
    """Resultado da camada de triagem sobre como processar o evento."""

    action: ActionType
    reason: str | None = None
    command_key: str | None = None
    user: Any = None
    required_permission: str | None = None


class ExecutionResult(BaseModel):
    """Resultado da camada de lógica selecionada (command, register, unauthorized ou agent handler)."""

    status: Literal[
        "success",
        "error",
        "ignored",
        "registered",
        "already_registered",
        "unauthorized",
    ] = "success"
    reply_text: str | None = None
    response_code: str | None = None
    use_http_exception_envelope: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)
