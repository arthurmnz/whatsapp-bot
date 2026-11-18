from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.agent.orchestrator import AgentOrchestrator
from app.core.auth import require_permission
from app.db.models import User
from app.db.session import get_db
from app.modules.jobs_career.models import ChatMessage, ChatThread

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])

_orchestrator = AgentOrchestrator()


class CreateThreadBody(BaseModel):
    title: str = Field(default="Nova conversa", min_length=1, max_length=255)
    context_type: str = "career"


class SendMessageBody(BaseModel):
    content: str = Field(..., min_length=1, max_length=12000)


def _serialize_thread(thread: ChatThread) -> dict[str, Any]:
    return {
        "id": thread.id,
        "user_id": thread.user_id,
        "title": thread.title,
        "channel_origin": thread.channel_origin,
        "context_type": thread.context_type,
        "created_at": thread.created_at.isoformat() if thread.created_at else None,
        "updated_at": thread.updated_at.isoformat() if thread.updated_at else None,
    }


def _serialize_message(msg: ChatMessage) -> dict[str, Any]:
    return {
        "id": msg.id,
        "thread_id": msg.thread_id,
        "role": msg.role,
        "channel": msg.channel,
        "content": msg.content,
        "rich_payload": msg.rich_payload,
        "created_at": msg.created_at.isoformat() if msg.created_at else None,
    }


@router.get("/threads")
async def list_threads(
    user: User = Depends(require_permission("agent:chat")),
    db: Session = Depends(get_db),
):
    threads = (
        db.query(ChatThread)
        .filter(ChatThread.user_id == user.id)
        .order_by(ChatThread.updated_at.desc())
        .all()
    )
    return {"items": [_serialize_thread(t) for t in threads]}


@router.post("/threads", status_code=status.HTTP_201_CREATED)
async def create_thread(
    body: CreateThreadBody,
    user: User = Depends(require_permission("agent:chat")),
    db: Session = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    thread = ChatThread(
        user_id=user.id,
        title=body.title.strip(),
        channel_origin="web",
        context_type=body.context_type,
        created_at=now,
        updated_at=now,
    )
    db.add(thread)
    db.commit()
    db.refresh(thread)
    return _serialize_thread(thread)


@router.get("/threads/{thread_id}/messages")
async def list_thread_messages(
    thread_id: int,
    user: User = Depends(require_permission("agent:chat")),
    db: Session = Depends(get_db),
):
    thread = (
        db.query(ChatThread)
        .filter(ChatThread.id == thread_id, ChatThread.user_id == user.id)
        .first()
    )
    if thread is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversa não encontrada.")
    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.thread_id == thread.id)
        .order_by(ChatMessage.id.asc())
        .all()
    )
    return {
        "thread": _serialize_thread(thread),
        "items": [_serialize_message(m) for m in messages],
    }


@router.post("/threads/{thread_id}/messages", status_code=status.HTTP_201_CREATED)
async def post_thread_message(
    thread_id: int,
    body: SendMessageBody,
    user: User = Depends(require_permission("agent:chat")),
    db: Session = Depends(get_db),
):
    thread = (
        db.query(ChatThread)
        .filter(ChatThread.id == thread_id, ChatThread.user_id == user.id)
        .first()
    )
    if thread is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversa não encontrada.")

    # Atualiza título se ainda for o padrão
    if thread.title in {"Nova conversa", "Assistente de Carreira C3PO"}:
        thread.title = body.content.strip()[:60]
        db.commit()

    resp = await _orchestrator.process_message(
        db=db,
        user=user,
        message=body.content,
        channel="web",
        thread_id=thread.id,
    )
    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.thread_id == thread.id)
        .order_by(ChatMessage.id.desc())
        .limit(2)
        .all()
    )
    messages.reverse()
    return {
        "thread_id": thread.id,
        "reply_text": resp.reply_text,
        "rich_payload": resp.rich_payload,
        "generated_filename": resp.generated_filename,
        "messages": [_serialize_message(m) for m in messages],
    }


@router.delete("/threads/{thread_id}")
async def delete_thread(
    thread_id: int,
    user: User = Depends(require_permission("agent:chat")),
    db: Session = Depends(get_db),
):
    thread = (
        db.query(ChatThread)
        .filter(ChatThread.id == thread_id, ChatThread.user_id == user.id)
        .first()
    )
    if thread is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversa não encontrada.")
    db.delete(thread)
    db.commit()
    return {"status": "deleted", "id": thread_id}
