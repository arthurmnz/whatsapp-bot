from typing import Any

from sqlalchemy.orm import Session

from app.core.crypto import encrypt_remote_jid, hash_remote_jid, normalize_remote_jid
from app.db.models import Role, User


def get_user_by_jid(db: Session, remote_jid: str) -> User | None:
    """Busca usuário ativo pelo hash determinístico HMAC-SHA256 do remoteJid."""
    normalized = normalize_remote_jid(remote_jid)
    if not normalized:
        return None
    jid_hash = hash_remote_jid(normalized)
    return (
        db.query(User)
        .filter(User.remote_jid_hash == jid_hash, User.is_active.is_(True))
        .first()
    )


def create_registered_user(
    db: Session,
    remote_jid: str,
    nome: str,
    role_name: str = "user",
) -> User:
    """Cria ou atualiza um usuário cadastrado com remoteJid criptografado na coluna `senha`."""
    normalized = normalize_remote_jid(remote_jid)
    jid_hash = hash_remote_jid(normalized)
    encrypted_senha = encrypt_remote_jid(normalized)

    role = db.query(Role).filter(Role.name == role_name).first()
    if role is None:
        role = Role(name=role_name, description=f"Role {role_name}")
        db.add(role)
        db.flush()

    existing = db.query(User).filter(User.remote_jid_hash == jid_hash).first()
    if existing is not None:
        existing.nome = nome.strip()
        existing.senha = encrypted_senha
        existing.role_id = role.id
        existing.is_active = True
        db.commit()
        db.refresh(existing)
        return existing

    user = User(
        nome=nome.strip(),
        senha=encrypted_senha,
        remote_jid_hash=jid_hash,
        role_id=role.id,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def user_has_permission(user: Any, permission_code: str) -> bool:
    """Verifica se o usuário está ativo e se a sua role possui a permissão solicitada."""
    if user is None:
        return False
    if not getattr(user, "is_active", False):
        return False
    role = getattr(user, "role", None)
    if role is None:
        return False
    permissions = getattr(role, "permissions", None) or []
    return any(getattr(perm, "code", None) == permission_code for perm in permissions)
