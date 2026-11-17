import logging
import os

from sqlalchemy.orm import Session

from app.core.crypto import encrypt_remote_jid, hash_remote_jid, normalize_remote_jid
from app.db.models import Permission, Role, User
from app.db.session import Base, engine, SessionLocal

logger = logging.getLogger(__name__)

DEFAULT_PERMISSIONS: dict[str, str] = {
    "cmd:help": "Exibir comandos disponíveis",
    "cmd:status_windows": "Consultar status do PC Windows",
    "cmd:wake_windows": "Ligar o PC Windows via Wake-on-LAN",
    "cmd:shutdown_windows": "Desligar o PC Windows via SSH",
    "cmd:restart_windows": "Reiniciar o PC Windows via SSH",
    "agent:chat": "Conversar com o agente IA C3PO",
}

DEFAULT_ROLES: dict[str, dict[str, object]] = {
    "admin": {
        "description": "Administrador com acesso total a todos os comandos e funções delicadas",
        "permissions": list(DEFAULT_PERMISSIONS.keys()),
    },
    "user": {
        "description": "Usuário padrão com acesso básico a consultas e conversação",
        "permissions": [
            "cmd:help",
            "cmd:status_windows",
            "agent:chat",
        ],
    },
}


def parse_admin_remote_jids(raw_env: str) -> list[tuple[str, str]]:
    """Analisa a string ADMIN_REMOTE_JIDS em pares (normalized_jid, nome)."""
    if not raw_env or not raw_env.strip():
        return []

    admins: list[tuple[str, str]] = []
    for entry in raw_env.split(","):
        item = entry.strip()
        if not item:
            continue
        if ":" in item:
            jid_part, name_part = item.split(":", 1)
            jid = normalize_remote_jid(jid_part)
            nome = name_part.strip() or "Admin"
        else:
            jid = normalize_remote_jid(item)
            nome = "Admin"

        if jid:
            admins.append((jid, nome))
    return admins


def seed_initial_data(db: Session) -> None:
    """Garante que permissões, roles e administradores definidos no .env existam no banco."""
    perm_map: dict[str, Permission] = {}
    for code, description in DEFAULT_PERMISSIONS.items():
        perm = db.query(Permission).filter(Permission.code == code).first()
        if perm is None:
            perm = Permission(code=code, description=description)
            db.add(perm)
            db.flush()
        else:
            perm.description = description
        perm_map[code] = perm

    role_map: dict[str, Role] = {}
    for role_name, cfg in DEFAULT_ROLES.items():
        role = db.query(Role).filter(Role.name == role_name).first()
        if role is None:
            role = Role(name=role_name, description=str(cfg["description"]))
            db.add(role)
            db.flush()
        else:
            role.description = str(cfg["description"])

        desired_codes: list[str] = list(cfg["permissions"])  # type: ignore[arg-type]
        role.permissions = [perm_map[c] for c in desired_codes if c in perm_map]
        role_map[role_name] = role

    db.flush()

    raw_admins = os.environ.get("ADMIN_REMOTE_JIDS", "")
    admin_entries = parse_admin_remote_jids(raw_admins)
    admin_role = role_map["admin"]

    for jid, nome in admin_entries:
        jid_hash = hash_remote_jid(jid)
        encrypted_senha = encrypt_remote_jid(jid)
        existing = db.query(User).filter(User.remote_jid_hash == jid_hash).first()
        if existing is None:
            user = User(
                nome=nome,
                senha=encrypted_senha,
                remote_jid_hash=jid_hash,
                role_id=admin_role.id,
                is_active=True,
            )
            db.add(user)
            logger.info("Admin semeado no banco: %s", nome)
        else:
            existing.role_id = admin_role.id
            existing.is_active = True
            if nome and nome != "Admin":
                existing.nome = nome

    db.commit()


def init_db(bind_engine=None) -> None:
    """Cria as tabelas caso não existam e executa o seed inicial."""
    target_engine = bind_engine or engine
    Base.metadata.create_all(bind=target_engine)
    with SessionLocal() as db:
        seed_initial_data(db)
