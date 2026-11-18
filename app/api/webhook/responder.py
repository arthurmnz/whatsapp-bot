import inspect
import logging
import os
from typing import Any

from fastapi import HTTPException

from app.api.webhook.schemas import ExecutionResult, TriageDecision, WebhookEvent
import app.api.webhook as webhook_pkg

logger = logging.getLogger(__name__)


class WebhookResponder:
    """Camada 4: Disparo de mensagens via Evolution API e formatação de respostas HTTP."""

    @staticmethod
    def respond_ignored(decision: TriageDecision) -> None:
        raise HTTPException(
            status_code=400,
            detail={
                "status": "ignored",
                "reason": decision.reason or "ignored",
            },
        )

    @staticmethod
    async def dispatch_and_respond(event: WebhookEvent, result: ExecutionResult) -> dict[str, Any]:
        if result.reply_text:
            res = webhook_pkg.send_text(to=event.remote_jid, text=result.reply_text)
            if inspect.isawaitable(res):
                await res
            logger.info("Resposta enviada para %s", event.remote_jid)

        file_path = result.metadata.get("generated_file_path") if result.metadata else None
        if file_path and os.path.exists(str(file_path)):
            try:
                filename = str(result.metadata.get("generated_filename") or "curriculo.pdf")
                doc_res = webhook_pkg.send_document(
                    to=event.remote_jid,
                    file_path=str(file_path),
                    filename=filename,
                    caption="📄 Aqui está o seu currículo otimizado em PDF!",
                )
                if inspect.isawaitable(doc_res):
                    await doc_res
            except Exception as exc:
                logger.warning("Falha ao enviar documento PDF pelo WhatsApp para %s: %s", event.remote_jid, exc)

        if result.use_http_exception_envelope:
            raise HTTPException(
                status_code=200,
                detail=result.metadata,
            )

        return result.metadata or {
            "status": result.status,
            "reply": result.response_code or result.reply_text,
        }
