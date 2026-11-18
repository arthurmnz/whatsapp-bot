import json
import logging
import os

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.agent.orchestrator import AgentOrchestrator
from app.core.auth import get_user_from_token
from app.db.repositories.user_repo import user_has_permission
from app.db.session import get_db

router = APIRouter()
logger = logging.getLogger(__name__)

_orchestrator = AgentOrchestrator()


def _extract_ws_token(websocket: WebSocket) -> str | None:
    """Extrai JWT do header Authorization ou da query string apenas se ALLOW_WS_QUERY_TOKEN=true."""
    auth_header = websocket.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip()
    if os.environ.get("ALLOW_WS_QUERY_TOKEN", "").strip().lower() == "true":
        query_token = websocket.query_params.get("token")
        if query_token and query_token.strip():
            return query_token.strip()
    return None


@router.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket, db: Session = Depends(get_db)):
    """WebSocket em tempo real para chat omnichannel sincronizado com o agente C3PO."""
    await websocket.accept()

    token = _extract_ws_token(websocket)
    user = None

    try:
        if not token:
            raw_init = await websocket.receive_text()
            try:
                init_data = json.loads(raw_init)
            except json.JSONDecodeError:
                init_data = {}
            if isinstance(init_data, dict) and init_data.get("type") == "auth":
                token = str(init_data.get("token") or "").strip()

        if not token:
            await websocket.send_json({"type": "error", "detail": "Token JWT obrigatório via frame auth ou header Authorization."})
            await websocket.close(code=4401)
            return

        try:
            user = get_user_from_token(db, token)
        except HTTPException as exc:
            await websocket.send_json({"type": "error", "detail": exc.detail})
            await websocket.close(code=4401)
            return

        if not user_has_permission(user, "agent:chat"):
            await websocket.send_json({"type": "error", "detail": "Permissão agent:chat necessária."})
            await websocket.close(code=4403)
            return

        await websocket.send_json({"type": "connected", "user_id": user.id, "nome": user.nome})

        while True:
            raw = await websocket.receive_text()
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                payload = {"type": "message", "content": raw}

            if not isinstance(payload, dict):
                continue

            msg_type = payload.get("type", "message")
            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})
                continue

            content = str(payload.get("content") or "").strip()
            if not content:
                await websocket.send_json({"type": "error", "detail": "Mensagem vazia."})
                continue

            thread_id = payload.get("thread_id")
            if thread_id is not None:
                try:
                    thread_id = int(thread_id)
                except (TypeError, ValueError):
                    thread_id = None

            await websocket.send_json({"type": "status", "status": "thinking"})
            resp = await _orchestrator.process_message(
                db=db,
                user=user,
                message=content,
                channel="web",
                thread_id=thread_id,
            )
            await websocket.send_json(
                {
                    "type": "assistant_message",
                    "thread_id": resp.thread_id,
                    "content": resp.reply_text,
                    "rich_payload": resp.rich_payload,
                    "generated_filename": resp.generated_filename,
                }
            )
    except WebSocketDisconnect:
        logger.debug("WebSocket /ws/chat desconectado pelo cliente.")
    except Exception as exc:
        logger.warning("Erro no WebSocket /ws/chat: %s", exc)
        try:
            await websocket.close(code=1011)
        except Exception:
            pass
