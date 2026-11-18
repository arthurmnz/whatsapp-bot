import logging
import os

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.auth import (
    check_auth_rate_limit,
    create_access_token,
    find_user_by_phone_or_jid,
    get_current_user,
    hash_web_password,
    invalidate_otp_for_user,
    issue_otp_for_user,
    lookup_user_by_identifier,
    normalize_phone_or_jid,
    serialize_user_summary,
    verify_otp_for_user,
    verify_web_password,
)
from app.db.models import User
from app.db.repositories.user_repo import user_has_permission
from app.db.session import get_db
from app.integrations.evolution import send_text

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
logger = logging.getLogger(__name__)


class RequestOtpBody(BaseModel):
    phone_or_jid: str = Field(..., min_length=6, max_length=120)


class VerifyOtpBody(BaseModel):
    phone_or_jid: str = Field(..., min_length=6, max_length=120)
    code: str = Field(..., min_length=4, max_length=12)


class LoginPasswordBody(BaseModel):
    identifier: str = Field(..., min_length=1, max_length=150)
    password: str = Field(..., min_length=1, max_length=200)


class SetPasswordBody(BaseModel):
    password: str = Field(..., min_length=6, max_length=200)
    current_password: str | None = Field(default=None, max_length=200)


def _client_ip(request: Request) -> str:
    return (request.client.host if request.client else "unknown") or "unknown"


@router.post("/request-otp")
async def request_otp(body: RequestOtpBody, request: Request, db: Session = Depends(get_db)):
    """Gera OTP de 6 dígitos (TTL 5 min) e envia pelo WhatsApp via Evolution API."""
    norm_phone = normalize_phone_or_jid(body.phone_or_jid) or body.phone_or_jid.strip()
    check_auth_rate_limit(f"req_otp:{_client_ip(request)}:{norm_phone}", max_requests=5, window_seconds=300)

    user = find_user_by_phone_or_jid(db, body.phone_or_jid)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Número não encontrado. Cadastre-se primeiro enviando /registrar <senha> <nome> no WhatsApp.",
        )

    if not user_has_permission(user, "web:access"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuário sem permissão para acessar a interface web.",
        )

    evo_url = os.environ.get("EVOLUTION_API_URL", "").strip()
    evo_instance = os.environ.get("EVOLUTION_INSTANCE", "").strip()
    if not evo_url or not evo_instance:
        logger.warning("Evolution API não configurada; envio de OTP via WhatsApp indisponível.")
        return {
            "status": "unavailable",
            "delivery": "unconfigured",
            "expires_in_seconds": 300,
            "message": "Evolution API não configurada; envio de OTP via WhatsApp indisponível.",
        }

    otp_code = issue_otp_for_user(user)
    try:
        jid = user.decrypted_remote_jid
        await send_text(
            to=jid,
            text=(
                f"🔐 Seu código de login para o painel C3PO é: *{otp_code}*\n"
                "Ele expira em 5 minutos. Não compartilhe este código."
            ),
        )
    except Exception as exc:
        invalidate_otp_for_user(user)
        logger.error("Falha ao enviar OTP via Evolution API para usuário id=%s: %s", user.id, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Falha ao entregar código OTP via WhatsApp.",
        ) from exc

    return {
        "status": "sent",
        "delivery": "whatsapp",
        "expires_in_seconds": 300,
        "message": "Código OTP enviado no seu WhatsApp!",
    }


@router.post("/verify-otp")
async def verify_otp(body: VerifyOtpBody, request: Request, db: Session = Depends(get_db)):
    """Valida o código OTP e emite token JWT de sessão."""
    norm_phone = normalize_phone_or_jid(body.phone_or_jid) or body.phone_or_jid.strip()
    check_auth_rate_limit(f"ver_otp:{_client_ip(request)}:{norm_phone}", max_requests=10, window_seconds=300)

    user = find_user_by_phone_or_jid(db, body.phone_or_jid)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais ou código OTP inválidos.",
        )

    if not user_has_permission(user, "web:access"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuário sem permissão para acessar a interface web.",
        )

    ok, msg = verify_otp_for_user(user, body.code)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=msg,
        )

    token = create_access_token(user)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": serialize_user_summary(user),
    }


@router.post("/login-password")
async def login_with_password(body: LoginPasswordBody, request: Request, db: Session = Depends(get_db)):
    """Login via telefone/nome + senha web configurada."""
    ident_key = body.identifier.strip().lower()
    check_auth_rate_limit(f"login_pwd:{_client_ip(request)}:{ident_key}", max_requests=10, window_seconds=300)

    user = lookup_user_by_identifier(db, body.identifier)
    if user is None or not verify_web_password(body.password, user.web_password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Identificador ou senha inválidos.",
        )

    if not user_has_permission(user, "web:access"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuário sem permissão para acessar a interface web.",
        )

    token = create_access_token(user)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": serialize_user_summary(user),
    }


@router.post("/set-password")
async def set_web_password(
    body: SetPasswordBody,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Define ou altera a senha web local (exige current_password se já houver senha configurada)."""
    if user.web_password_hash:
        if not body.current_password or not verify_web_password(body.current_password, user.web_password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Senha atual obrigatória e deve ser válida para alterar a senha existente.",
            )

    try:
        user.web_password_hash = hash_web_password(body.password)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    db.commit()
    db.refresh(user)
    return {
        "status": "ok",
        "message": "Senha web atualizada com sucesso.",
        "user": serialize_user_summary(user),
    }


@router.get("/me")
async def auth_me(user: User = Depends(get_current_user)):
    """Retorna os dados e permissões do usuário autenticado."""
    return {"user": serialize_user_summary(user)}
