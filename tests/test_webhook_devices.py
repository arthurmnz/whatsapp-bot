from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
import pytest

from app.main import app


def _build_webhook_payload(text: str, remote_jid: str = "5511999999999@s.whatsapp.net") -> dict:
    return {
        "event": "messages.upsert",
        "data": {
            "key": {
                "remoteJid": remote_jid,
                "fromMe": False,
            },
            "pushName": "Arthur",
            "message": {
                "conversation": text,
            },
        },
    }


def test_webhook_desligar_win():
    mock_result = {
        "success": True,
        "action": "shutdown",
        "reason": "ok",
        "message": "💻 Comando para desligar o PC com Windows enviado com sucesso!",
    }
    with patch("app.api.webhook.shutdown_windows", new_callable=AsyncMock, return_value=mock_result) as mock_shutdown:
        with patch("app.api.webhook.send_text", new_callable=AsyncMock) as mock_send:
            client = TestClient(app)
            resp = client.post("/webhook", json=_build_webhook_payload("/desligar-win"))

            assert resp.status_code == 200
            detail = resp.json()["detail"]
            assert detail["reply"] == "pc_desligar_command_received"
            assert detail["status"] == "success"
            mock_shutdown.assert_awaited_once()
            mock_send.assert_awaited_once_with(
                to="5511999999999@s.whatsapp.net",
                text=mock_result["message"],
            )


@pytest.mark.parametrize("cmd_str", ["/reiniciar-win", "/reniciar-win", "  /REINICIAR-WIN  "])
def test_webhook_reiniciar_win_and_alias(cmd_str: str):
    mock_result = {
        "success": True,
        "action": "restart",
        "reason": "ok",
        "message": "💻 Comando para reiniciar o PC com Windows enviado com sucesso!",
    }
    with patch("app.api.webhook.restart_windows", new_callable=AsyncMock, return_value=mock_result) as mock_restart:
        with patch("app.api.webhook.send_text", new_callable=AsyncMock) as mock_send:
            client = TestClient(app)
            resp = client.post("/webhook", json=_build_webhook_payload(cmd_str))

            assert resp.status_code == 200
            detail = resp.json()["detail"]
            assert detail["reply"] == "pc_reiniciar_command_received"
            assert detail["status"] == "success"
            mock_restart.assert_awaited_once()
            mock_send.assert_awaited_once_with(
                to="5511999999999@s.whatsapp.net",
                text=mock_result["message"],
            )


@pytest.mark.parametrize("cmd_str", ["/status-win", "/status"])
def test_webhook_status_win_and_alias(cmd_str: str):
    mock_result = {
        "online": True,
        "hostname": "PC-ARTHUR",
        "reason": "ok",
        "message": "🟢 PC com Windows está ONLINE (Host: PC-ARTHUR).",
    }
    with patch("app.api.webhook.get_windows_status", new_callable=AsyncMock, return_value=mock_result) as mock_status:
        with patch("app.api.webhook.send_text", new_callable=AsyncMock) as mock_send:
            client = TestClient(app)
            resp = client.post("/webhook", json=_build_webhook_payload(cmd_str))

            assert resp.status_code == 200
            detail = resp.json()["detail"]
            assert detail["reply"] == "pc_status_command_received"
            assert detail["online"] is True
            assert detail["hostname"] == "PC-ARTHUR"
            mock_status.assert_awaited_once()
            mock_send.assert_awaited_once_with(
                to="5511999999999@s.whatsapp.net",
                text=mock_result["message"],
            )


def test_webhook_ligar_win_wol():
    mock_result = {
        "success": True,
        "action": "wake",
        "reason": "ok",
        "mac": "10:FF:E0:01:AA:D1",
        "message": "⚡ Pacote Wake-on-LAN enviado com sucesso para o PC com Windows (MAC: 10:FF:E0:01:AA:D1)!",
    }
    with patch("app.api.webhook.wake_windows", new_callable=AsyncMock, return_value=mock_result) as mock_wake:
        with patch("app.api.webhook.send_text", new_callable=AsyncMock) as mock_send:
            client = TestClient(app)
            resp = client.post("/webhook", json=_build_webhook_payload("/ligar-win"))

            assert resp.status_code == 200
            detail = resp.json()["detail"]
            assert detail["reply"] == "pc_ligar_command_received"
            assert detail["status"] == "success"
            assert detail["result"]["mac"] == "10:FF:E0:01:AA:D1"
            mock_wake.assert_awaited_once()
            mock_send.assert_awaited_once_with(
                to="5511999999999@s.whatsapp.net",
                text=mock_result["message"],
            )
