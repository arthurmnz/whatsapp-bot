from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.webhook import sanitize_message_for_log
from app.api.webhook.handlers.unauthorized_handler import UNAUTHORIZED_REPLY
from app.db.repositories.user_repo import get_user_by_jid
from app.db.seed import seed_initial_data
from app.db.session import Base, get_db
from app.main import app


def _make_payload(
    text: str,
    remote_jid: str = "5511911112222@s.whatsapp.net",
    push_name: str = "Visitante",
) -> dict:
    return {
        "event": "messages.upsert",
        "data": {
            "key": {
                "remoteJid": remote_jid,
                "fromMe": False,
            },
            "pushName": push_name,
            "message": {
                "conversation": text,
            },
        },
    }


@pytest.fixture()
def sqlite_client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ENCRYPTION_KEY", "test-encryption-key-32-bytes-seed")
    monkeypatch.setenv("HMAC_SECRET", "test-hmac-secret-key")
    monkeypatch.setenv("SYSTEM_REGISTRATION_PASSWORD", "SenhaMestre2026")
    monkeypatch.setenv(
        "ADMIN_REMOTE_JIDS",
        "5511999999999@s.whatsapp.net:Arthur Admin,5511888888888@s.whatsapp.net:CoAdmin",
    )

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    with TestingSessionLocal() as db:
        seed_initial_data(db)

    def _override_get_db():
        with TestingSessionLocal() as db:
            yield db

    app.dependency_overrides[get_db] = _override_get_db
    client = TestClient(app)
    try:
        yield client, TestingSessionLocal
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_sanitize_message_for_log_masks_password():
    assert (
        sanitize_message_for_log("/registrar SenhaSuperSecreta Arthur Muniz")
        == "/registrar *** Arthur Muniz"
    )
    assert sanitize_message_for_log("/REGISTRAR SenhaSecreta") == "/REGISTRAR ***"
    assert sanitize_message_for_log("/registrar") == "/registrar"
    assert sanitize_message_for_log("Olá mundo") == "Olá mundo"


def test_unregistered_user_is_silently_ignored_for_normal_messages_and_commands(sqlite_client):
    client, _ = sqlite_client
    unregistered_jid = "5511900000000@s.whatsapp.net"

    with patch("app.api.webhook.send_text", new_callable=AsyncMock) as mock_send:
        for msg in ["Olá, tudo bem?", "/help", "/status-win", "/desligar-win"]:
            resp = client.post("/webhook", json=_make_payload(msg, remote_jid=unregistered_jid))
            assert resp.status_code == 400
            assert resp.json()["detail"] == {"status": "ignored", "reason": "unregistered_user"}

        # Garante silêncio total na Evolution API
        mock_send.assert_not_called()


def test_unregistered_user_invalid_registration_password_or_format_is_silently_ignored(sqlite_client):
    client, _ = sqlite_client
    unregistered_jid = "5511900000001@s.whatsapp.net"

    with patch("app.api.webhook.send_text", new_callable=AsyncMock) as mock_send:
        for invalid_cmd in [
            "/registrar",
            "/registrar SenhaMestre2026",
            "/registrar SenhaErrada João da Silva",
            "/registrar SenhaMestre2026    ",
        ]:
            resp = client.post("/webhook", json=_make_payload(invalid_cmd, remote_jid=unregistered_jid))
            assert resp.status_code == 400
            assert resp.json()["detail"] == {
                "status": "ignored",
                "reason": "invalid_registration_attempt",
            }

        mock_send.assert_not_called()


def test_registration_flow_with_compound_name_and_rbac_enforcement(sqlite_client):
    client, session_factory = sqlite_client
    new_jid = "5511944445555@s.whatsapp.net"

    with patch("app.api.webhook.send_text", new_callable=AsyncMock) as mock_send:
        # 1. Faz o registro com nome composto
        resp = client.post(
            "/webhook",
            json=_make_payload("/registrar SenhaMestre2026 Maria Clara de Souza", remote_jid=new_jid),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "registered"
        assert body["nome"] == "Maria Clara de Souza"
        mock_send.assert_awaited_once()
        sent_welcome = mock_send.await_args.kwargs["text"]
        assert "Maria Clara de Souza" in sent_welcome

    # Verifica que o banco salvou o remoteJid criptografado em `senha`
    with session_factory() as db:
        saved_user = get_user_by_jid(db, new_jid)
        assert saved_user is not None
        assert saved_user.nome == "Maria Clara de Souza"
        assert saved_user.decrypted_remote_jid == new_jid
        assert new_jid not in saved_user.senha
        assert saved_user.role.name == "user"

    # 2. Tentar registrar novamente avisa que já está cadastrado
    with patch("app.api.webhook.send_text", new_callable=AsyncMock) as mock_send:
        resp_dup = client.post(
            "/webhook",
            json=_make_payload("/registrar SenhaMestre2026 Outro Nome", remote_jid=new_jid),
        )
        assert resp_dup.status_code == 200
        assert resp_dup.json()["status"] == "already_registered"
        mock_send.assert_awaited_once()
        assert "já está cadastrado, Maria Clara de Souza" in mock_send.await_args.kwargs["text"]

    # 3. Usuário comum pode usar /status-win, mas NÃO pode usar /desligar-win, /ligar-win ou /reiniciar-win
    with patch(
        "app.api.webhook.get_windows_status",
        new_callable=AsyncMock,
        return_value={"online": True, "hostname": "PC", "reason": "ok", "message": "Online"},
    ):
        with patch("app.api.webhook.send_text", new_callable=AsyncMock):
            resp_status = client.post("/webhook", json=_make_payload("/status-win", remote_jid=new_jid))
            assert resp_status.status_code == 200
            assert resp_status.json()["detail"]["reply"] == "pc_status_command_received"

    for delicate_cmd in ["/ligar-win", "/desligar-win", "/reiniciar-win"]:
        with patch("app.api.webhook.send_text", new_callable=AsyncMock) as mock_send:
            resp_denied = client.post("/webhook", json=_make_payload(delicate_cmd, remote_jid=new_jid))
            assert resp_denied.status_code == 200
            body_denied = resp_denied.json()
            assert body_denied["status"] == "unauthorized"
            assert body_denied["reply"] == "permission_denied"
            mock_send.assert_awaited_once_with(to=new_jid, text=UNAUTHORIZED_REPLY)


def test_seeded_admins_can_execute_delicate_commands_without_manual_registration(sqlite_client):
    client, _ = sqlite_client
    admin_jid = "5511999999999@s.whatsapp.net"

    mock_shutdown_res = {
        "success": True,
        "action": "shutdown",
        "reason": "ok",
        "message": "Desligando...",
    }
    with patch("app.api.webhook.shutdown_windows", new_callable=AsyncMock, return_value=mock_shutdown_res) as mock_sh:
        with patch("app.api.webhook.send_text", new_callable=AsyncMock) as mock_send:
            resp = client.post("/webhook", json=_make_payload("/desligar-win", remote_jid=admin_jid))
            assert resp.status_code == 200
            assert resp.json()["detail"]["reply"] == "pc_desligar_command_received"
            mock_sh.assert_awaited_once()
            mock_send.assert_awaited_once_with(to=admin_jid, text="Desligando...")
