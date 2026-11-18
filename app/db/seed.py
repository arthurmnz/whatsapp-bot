import logging
import os

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session, sessionmaker

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
    "jobs:profile": "Gerenciar perfil profissional, skills e preferências de vagas",
    "jobs:search": "Buscar, ingerir e avaliar vagas compatíveis",
    "jobs:cv_tailor": "Analisar, otimizar e gerar currículos sob medida",
    "jobs:applications": "Gerenciar candidaturas e funil de entrevistas",
    "jobs:interview": "Gerar roteiros e simular entrevistas técnicas",
    "web:access": "Acessar a interface web e chat em tempo real",
}

DEFAULT_ROLES: dict[str, dict[str, object]] = {
    "admin": {
        "description": "Administrador com acesso total a todos os comandos e funções delicadas",
        "permissions": list(DEFAULT_PERMISSIONS.keys()),
    },
    "user": {
        "description": "Usuário padrão com acesso básico a consultas, carreira e conversação",
        "permissions": [
            "cmd:help",
            "cmd:status_windows",
            "agent:chat",
            "jobs:profile",
            "jobs:search",
            "jobs:cv_tailor",
            "jobs:applications",
            "jobs:interview",
            "web:access",
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


def ensure_schema_migrations(target_engine) -> None:
    """Aplica migrações leves idempotentes para bancos já existentes sem Alembic."""
    inspector = inspect(target_engine)
    if not inspector.has_table("users"):
        return

    existing_cols = {col["name"] for col in inspector.get_columns("users")}
    dialect = target_engine.dialect.name
    stmts: list[str] = []
    if "web_password_hash" not in existing_cols:
        if dialect == "postgresql":
            stmts.append("ALTER TABLE users ADD COLUMN IF NOT EXISTS web_password_hash TEXT")
        else:
            stmts.append("ALTER TABLE users ADD COLUMN web_password_hash TEXT")
    if "updated_at" not in existing_cols:
        if dialect == "postgresql":
            stmts.append("ALTER TABLE users ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP")
        else:
            stmts.append("ALTER TABLE users ADD COLUMN updated_at DATETIME")

    if stmts:
        with target_engine.begin() as conn:
            for stmt in stmts:
                conn.execute(text(stmt))
                logger.info("Auto-migração aplicada: %s", stmt)


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
    """Cria as tabelas caso não existam, aplica auto-migrações e executa o seed inicial."""
    import app.modules.jobs_career.models  # noqa: F401 - garante criação de todas as tabelas

    target_engine = bind_engine or engine
    Base.metadata.create_all(bind=target_engine)
    ensure_schema_migrations(target_engine)
    session_factory = (
        sessionmaker(autocommit=False, autoflush=False, bind=target_engine)
        if bind_engine is not None
        else SessionLocal
    )
    with session_factory() as db:
        seed_initial_data(db)
