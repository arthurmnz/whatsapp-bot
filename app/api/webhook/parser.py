from typing import Any

from app.api.webhook.schemas import WebhookEvent


class EvolutionWebhookParser:
    """Camada 1: Captação e extração resiliente de dados do payload da Evolution API."""

    @staticmethod
    def parse(payload: Any) -> WebhookEvent:
        if not isinstance(payload, dict):
            return WebhookEvent(raw_payload={})

        event_type = payload.get("event")
        if event_type is not None and not isinstance(event_type, str):
            event_type = str(event_type)

        data = payload.get("data")
        message_info: dict[str, Any] = data if isinstance(data, dict) else {}

        key_raw = message_info.get("key")
        key_info: dict[str, Any] = key_raw if isinstance(key_raw, dict) else {}

        from_me = bool(key_info.get("fromMe", False))
        remote_jid = str(key_info.get("remoteJid") or "")
        push_name = str(message_info.get("pushName") or "")

        msg_raw = message_info.get("message")
        message_obj: dict[str, Any] = msg_raw if isinstance(msg_raw, dict) else {}

        ext_raw = message_obj.get("extendedTextMessage")
        ext_obj: dict[str, Any] = ext_raw if isinstance(ext_raw, dict) else {}

        conversation = message_obj.get("conversation")
        ext_text = ext_obj.get("text")

        raw_text = conversation if isinstance(conversation, str) and conversation else (
            ext_text if isinstance(ext_text, str) and ext_text else ""
        )

        return WebhookEvent(
            event_type=event_type,
            remote_jid=remote_jid,
            push_name=push_name,
            from_me=from_me,
            message_text=raw_text,
            raw_payload=payload,
        )
