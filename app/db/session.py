from collections.abc import Generator
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, Session, sessionmaker

DEFAULT_DATABASE_URL = "postgresql://postgres:postgres@127.0.0.1:5432/whatsapp_bot"

DATABASE_URL = os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL).strip() or DEFAULT_DATABASE_URL

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
