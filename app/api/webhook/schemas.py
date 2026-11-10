from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class ActionType(str, Enum):
    IGNORE = "ignore"
    COMMAND = "command"
    AGENT = "agent"


class WebhookEvent(BaseModel):
    """DTO padronizado representando um evento recebido da Evolution API."""

    event_type: str | None = None
    remote_jid: str = ""
    push_name: str = ""
    from_me: bool = False
    message_text: str = ""
    raw_payload: dict[str, Any] = Field(default_factory=dict)

    @property
    def normalized_command(self) -> str:
        return self.message_text.strip().lower()


class TriageDecision(BaseModel):
    """Resultado da camada de triagem sobre como processar o evento."""

    action: ActionType
    reason: str | None = None
    command_key: str | None = None


class ExecutionResult(BaseModel):
    """Resultado da camada de lógica selecionada (command ou agent handler)."""

    status: Literal["success", "error", "ignored"] = "success"
    reply_text: str | None = None
    response_code: str | None = None
    use_http_exception_envelope: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)
