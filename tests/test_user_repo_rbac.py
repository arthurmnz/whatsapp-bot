import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.crypto import hash_remote_jid
from app.db.models import Permission, Role, User
from app.db.repositories.user_repo import (
    create_registered_user,
    get_user_by_jid,
    user_has_permission,
)
from app.db.seed import parse_admin_remote_jids, seed_initial_data
from app.db.session import Base


@pytest.fixture()
def db_session(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ENCRYPTION_KEY", "chave-teste-criptografia-fernet")
    monkeypatch.setenv("HMAC_SECRET", "chave-teste-hmac-sha256")
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


def test_parse_admin_remote_jids():
    raw = "5511999999999@s.whatsapp.net:Arthur Muniz, 5511888888888:Maria Clara , 5511777777777@s.whatsapp.net"
    parsed = parse_admin_remote_jids(raw)
    assert parsed == [
        ("5511999999999@s.whatsapp.net", "Arthur Muniz"),
        ("5511888888888@s.whatsapp.net", "Maria Clara"),
        ("5511777777777@s.whatsapp.net", "Admin"),
    ]


def test_seed_initial_data_and_multiple_admins(db_session, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(
        "ADMIN_REMOTE_JIDS",
        "5511999999999@s.whatsapp.net:Arthur Muniz,5511888888888@s.whatsapp.net:Segundo Admin",
    )
    seed_initial_data(db_session)

    # Verifica roles e permissions
    roles = {r.name: r for r in db_session.query(Role).all()}
    assert "admin" in roles
    assert "user" in roles
    assert len(roles["admin"].permissions) == 12
    assert len(roles["user"].permissions) == 9

    # Verifica os dois admins criados
    admin1 = get_user_by_jid(db_session, "5511999999999@s.whatsapp.net")
    admin2 = get_user_by_jid(db_session, "5511888888888")

    assert admin1 is not None
    assert admin1.nome == "Arthur Muniz"
    assert admin1.role.name == "admin"
    assert admin1.decrypted_remote_jid == "5511999999999@s.whatsapp.net"
    assert "5511999999999" not in admin1.senha
    assert admin1.remote_jid_hash == hash_remote_jid("5511999999999@s.whatsapp.net")

    assert admin2 is not None
    assert admin2.nome == "Segundo Admin"
    assert admin2.role.name == "admin"
    assert user_has_permission(admin1, "cmd:shutdown_windows") is True
    assert user_has_permission(admin2, "cmd:wake_windows") is True
    assert user_has_permission(admin1, "jobs:cv_tailor") is True
    assert user_has_permission(admin1, "web:access") is True


def test_create_registered_user_and_permissions(db_session, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ADMIN_REMOTE_JIDS", "")
    seed_initial_data(db_session)

    user = create_registered_user(
        db_session,
        remote_jid="5521912345678@s.whatsapp.net",
        nome="João Pedro da Silva",
        role_name="user",
    )

    assert user.id is not None
    assert user.nome == "João Pedro da Silva"
    assert user.decrypted_remote_jid == "5521912345678@s.whatsapp.net"
    assert "5521912345678" not in user.senha

    # Permissões da role 'user'
    assert user_has_permission(user, "cmd:help") is True
    assert user_has_permission(user, "cmd:status_windows") is True
    assert user_has_permission(user, "agent:chat") is True
    assert user_has_permission(user, "jobs:profile") is True
    assert user_has_permission(user, "jobs:search") is True
    assert user_has_permission(user, "jobs:cv_tailor") is True
    assert user_has_permission(user, "jobs:applications") is True
    assert user_has_permission(user, "jobs:interview") is True
    assert user_has_permission(user, "web:access") is True

    # Comandos delicados negados para 'user'
    assert user_has_permission(user, "cmd:wake_windows") is False
    assert user_has_permission(user, "cmd:shutdown_windows") is False
    assert user_has_permission(user, "cmd:restart_windows") is False
