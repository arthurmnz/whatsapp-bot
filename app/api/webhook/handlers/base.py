from abc import ABC, abstractmethod

from app.api.webhook.schemas import ExecutionResult, TriageDecision, WebhookEvent


class BaseHandler(ABC):
    """Interface abstrata para os handlers da camada de lógica selecionada."""

    @abstractmethod
    async def handle(self, event: WebhookEvent, decision: TriageDecision) -> ExecutionResult:
        """Processa o evento triado e retorna um ExecutionResult."""
        raise NotImplementedError
