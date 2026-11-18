from collections.abc import Generator
import importlib.util
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, Session, sessionmaker

DEFAULT_DATABASE_URL = "postgresql://postgres:postgres@127.0.0.1:5432/whatsapp_bot"


def normalize_database_url(url: str) -> str:
    """Ajusta o driver PostgreSQL da URL conforme o pacote instalado (psycopg vs psycopg2)."""
    cleaned = (url or "").strip() or DEFAULT_DATABASE_URL
    has_psycopg = importlib.util.find_spec("psycopg") is not None
    has_psycopg2 = importlib.util.find_spec("psycopg2") is not None

    if cleaned.startswith("postgresql+psycopg://") and not has_psycopg and has_psycopg2:
        return "postgresql+psycopg2://" + cleaned[len("postgresql+psycopg://") :]
    if cleaned.startswith("postgresql+psycopg2://") and not has_psycopg2 and has_psycopg:
        return "postgresql+psycopg://" + cleaned[len("postgresql+psycopg2://") :]
    if cleaned.startswith("postgresql://") and not has_psycopg2 and has_psycopg:
        return "postgresql+psycopg://" + cleaned[len("postgresql://") :]
    return cleaned


_RAW_DATABASE_URL = os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL).strip() or DEFAULT_DATABASE_URL
DATABASE_URL = normalize_database_url(_RAW_DATABASE_URL)

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    connect_args=connect_args,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """Dependency generator que fornece uma sessão SQLAlchemy e garante o fechamento."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
