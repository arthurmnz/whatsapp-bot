import os
import socket
from unittest.mock import MagicMock, patch

import paramiko
import pytest

from app.modules.devices_control import (
    get_windows_ssh_config,
    get_windows_status,
    get_windows_status_sync,
    get_windows_wol_config,
    parse_mac_address,
    restart_windows,
    restart_windows_sync,
    shutdown_windows,
    shutdown_windows_sync,
    wake_windows,
    wake_windows_sync,
)


def _make_mock_ssh_client(stdout_bytes: bytes = b"", stderr_bytes: bytes = b"") -> MagicMock:
    client = MagicMock(spec=paramiko.SSHClient)
    mock_stdout = MagicMock()
    mock_stdout.read.return_value = stdout_bytes
    mock_stderr = MagicMock()
    mock_stderr.read.return_value = stderr_bytes
    client.exec_command.return_value = (MagicMock(), mock_stdout, mock_stderr)
    return client


# ─── 1. Testes de Configuração SSH e WOL (config.py) ─────────────────────────


def test_get_windows_ssh_config_valid():
    with patch.dict(
        os.environ,
        {
            "WIN_MNZ_IP": "192.168.0.200",
            "WIN_MNZ_USER": "arthurmnz",
            "WIN_MNZ_PASSWORD": "super_secret_password_123",
            "WIN_MNZ_PORT": "2222",
            "WIN_MNZ_TIMEOUT": "3.5",
        },
        clear=False,
    ):
        cfg = get_windows_ssh_config()
        assert cfg.ip == "192.168.0.200"
        assert cfg.user == "arthurmnz"
        assert cfg.password == "super_secret_password_123"
        assert cfg.port == 2222
        assert cfg.timeout == 3.5
        # Garante que repr e str nunca vazam a senha
        assert "super_secret_password_123" not in repr(cfg)
        assert "super_secret_password_123" not in str(cfg)
        assert "***REDACTED***" in repr(cfg)


def test_get_windows_ssh_config_missing_credentials():
    with patch.dict(
        os.environ,
        {
            "WIN_MNZ_IP": "",
            "WIN_MNZ_USER": "",
            "WIN_MNZ_PASSWORD": "",
        },
        clear=False,
    ):
        with pytest.raises(ValueError) as exc_info:
            get_windows_ssh_config()
        msg = str(exc_info.value)
        assert "WIN_MNZ_IP" in msg
        assert "WIN_MNZ_USER" in msg
        assert "WIN_MNZ_PASSWORD" in msg


@pytest.mark.parametrize(
    "raw_mac,expected_canonical",
    [
        ("10-FF-E0-01-AA-D1", "10:FF:E0:01:AA:D1"),
        ("10:ff:e0:01:aa:d1", "10:FF:E0:01:AA:D1"),
        ("10FFE001AAD1", "10:FF:E0:01:AA:D1"),
        ("  10.ff.e0.01.aa.d1  ", "10:FF:E0:01:AA:D1"),
    ],
)
def test_parse_mac_address_valid_formats(raw_mac: str, expected_canonical: str):
    canonical, mac_bytes = parse_mac_address(raw_mac)
    assert canonical == expected_canonical
    assert len(mac_bytes) == 6
    assert mac_bytes == bytes.fromhex("10FFE001AAD1")


@pytest.mark.parametrize(
    "invalid_mac",
    [
        "",
        "   ",
        "10-FF-E0-01-AA",       # curto
        "10-FF-E0-01-AA-D1-00", # longo
        "GG-FF-E0-01-AA-D1",    # não hexadecimal
    ],
)
def test_parse_mac_address_invalid(invalid_mac: str):
    with pytest.raises(ValueError):
        parse_mac_address(invalid_mac)


def test_get_windows_wol_config_valid():
    with patch.dict(
        os.environ,
        {
            "WIN_MNZ_MAC": "10-FF-E0-01-AA-D1",
            "WIN_MNZ_BROADCAST": "192.168.0.255",
            "WIN_MNZ_WOL_PORT": "7",
        },
        clear=False,
    ):
        wol_cfg = get_windows_wol_config()
        assert wol_cfg.mac == "10:FF:E0:01:AA:D1"
        assert wol_cfg.mac_bytes == bytes.fromhex("10FFE001AAD1")
        assert wol_cfg.broadcast == "192.168.0.255"
        assert wol_cfg.port == 7


# ─── 2. Testes de Wake-on-LAN (wake_windows) ─────────────────────────────────


@pytest.mark.asyncio
async def test_wake_windows_success_magic_packet():
    mock_sock = MagicMock(spec=socket.socket)
    with patch.dict(
        os.environ,
        {
            "WIN_MNZ_MAC": "10-FF-E0-01-AA-D1",
            "WIN_MNZ_BROADCAST": "255.255.255.255",
            "WIN_MNZ_WOL_PORT": "9",
            "WIN_MNZ_IP": "192.168.0.200",
        },
        clear=False,
    ):
        with patch("socket.socket", return_value=mock_sock):
            res = await wake_windows()

    assert res["success"] is True
    assert res["action"] == "wake"
    assert res["mac"] == "10:FF:E0:01:AA:D1"
    assert "10:FF:E0:01:AA:D1" in res["message"]

    mock_sock.setsockopt.assert_called_once_with(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    assert mock_sock.sendto.call_count >= 1

    sent_packet, target_addr = mock_sock.sendto.call_args_list[0][0]
    assert len(sent_packet) == 102
    assert sent_packet == b"\xff" * 6 + bytes.fromhex("10FFE001AAD1") * 16
    assert target_addr == ("255.255.255.255", 9)
    mock_sock.close.assert_called_once()


def test_wake_windows_invalid_mac():
    with patch.dict(
        os.environ,
        {
            "WIN_MNZ_MAC": "MAC_INVALIDO",
        },
        clear=False,
    ):
        res = wake_windows_sync()

    assert res["success"] is False
    assert res["action"] == "wake"
    assert res["reason"] == "invalid_mac"


def test_wake_windows_network_oserror():
    mock_sock = MagicMock(spec=socket.socket)
    mock_sock.sendto.side_effect = OSError("Network is unreachable")
    with patch.dict(
        os.environ,
        {
            "WIN_MNZ_MAC": "10-FF-E0-01-AA-D1",
        },
        clear=False,
    ):
        with patch("socket.socket", return_value=mock_sock):
            res = wake_windows_sync()

    assert res["success"] is False
    assert res["action"] == "wake"
    assert res["reason"] == "network_error"
    mock_sock.close.assert_called_once()


# ─── 3. Testes de Desligamento e Reinicialização (service.py) ────────────────


@pytest.mark.asyncio
async def test_shutdown_windows_success():
    mock_client = _make_mock_ssh_client()
    with patch.dict(
        os.environ,
        {
            "WIN_MNZ_IP": "192.168.0.200",
            "WIN_MNZ_USER": "arthurmnz",
            "WIN_MNZ_PASSWORD": "secret",
        },
        clear=False,
    ):
        with patch("paramiko.SSHClient", return_value=mock_client):
            res = await shutdown_windows()

    assert res["success"] is True
    assert res["action"] == "shutdown"
    mock_client.connect.assert_called_once()
    mock_client.exec_command.assert_called_once_with("shutdown /s /f /t 0", timeout=5.0)
    mock_client.close.assert_called_once()


@pytest.mark.asyncio
async def test_restart_windows_success():
    mock_client = _make_mock_ssh_client()
    with patch.dict(
        os.environ,
        {
            "WIN_MNZ_IP": "192.168.0.200",
            "WIN_MNZ_USER": "arthurmnz",
            "WIN_MNZ_PASSWORD": "secret",
        },
        clear=False,
    ):
        with patch("paramiko.SSHClient", return_value=mock_client):
            res = await restart_windows()

    assert res["success"] is True
    assert res["action"] == "restart"
    mock_client.connect.assert_called_once()
    mock_client.exec_command.assert_called_once_with("shutdown /r /f /t 0", timeout=5.0)
    mock_client.close.assert_called_once()


# ─── 4. Testes de Status Online / Offline / Erros ────────────────────────────


@pytest.mark.asyncio
async def test_get_windows_status_online():
    mock_client = _make_mock_ssh_client(stdout_bytes=b"DESKTOP-ARTHUR\r\n")
    with patch.dict(
        os.environ,
        {
            "WIN_MNZ_IP": "192.168.0.200",
            "WIN_MNZ_USER": "arthurmnz",
            "WIN_MNZ_PASSWORD": "secret",
        },
        clear=False,
    ):
        with patch("paramiko.SSHClient", return_value=mock_client):
            res = await get_windows_status()

    assert res["online"] is True
    assert res["hostname"] == "DESKTOP-ARTHUR"
    assert res["reason"] == "ok"
    assert "ONLINE" in res["message"]
    assert "DESKTOP-ARTHUR" in res["message"]
    mock_client.exec_command.assert_called_once_with("hostname", timeout=5.0)
    mock_client.close.assert_called_once()


@pytest.mark.asyncio
async def test_get_windows_status_offline_timeout():
    mock_client = _make_mock_ssh_client()
    mock_client.connect.side_effect = socket.timeout("timed out")
    with patch.dict(
        os.environ,
        {
            "WIN_MNZ_IP": "192.168.0.200",
            "WIN_MNZ_USER": "arthurmnz",
            "WIN_MNZ_PASSWORD": "secret",
        },
        clear=False,
    ):
        with patch("paramiko.SSHClient", return_value=mock_client):
            res = await get_windows_status()

    assert res["online"] is False
    assert res["hostname"] is None
    assert res["reason"] == "timeout"
    assert "OFFLINE" in res["message"]
    mock_client.close.assert_called_once()


def test_get_windows_status_offline_oserror():
    mock_client = _make_mock_ssh_client()
    mock_client.connect.side_effect = OSError("No route to host")
    with patch.dict(
        os.environ,
        {
            "WIN_MNZ_IP": "192.168.0.200",
            "WIN_MNZ_USER": "arthurmnz",
            "WIN_MNZ_PASSWORD": "my_secret_pwd",
        },
        clear=False,
    ):
        with patch("paramiko.SSHClient", return_value=mock_client):
            res = get_windows_status_sync()

    assert res["online"] is False
    assert res["reason"] == "unreachable"
    assert "my_secret_pwd" not in res["message"]
    mock_client.close.assert_called_once()


def test_devices_control_authentication_error():
    mock_client = _make_mock_ssh_client()
    mock_client.connect.side_effect = paramiko.AuthenticationException("Authentication failed.")
    with patch.dict(
        os.environ,
        {
            "WIN_MNZ_IP": "192.168.0.200",
            "WIN_MNZ_USER": "arthurmnz",
            "WIN_MNZ_PASSWORD": "my_secret_pwd",
        },
        clear=False,
    ):
        with patch("paramiko.SSHClient", return_value=mock_client):
            res_shutdown = shutdown_windows_sync()
            res_restart = restart_windows_sync()
            res_status = get_windows_status_sync()

    assert res_shutdown["success"] is False
    assert res_shutdown["reason"] == "authentication_failed"
    assert "my_secret_pwd" not in res_shutdown["message"]

    assert res_restart["success"] is False
    assert res_restart["reason"] == "authentication_failed"

    assert res_status["online"] is False
    assert res_status["reason"] == "authentication_failed"


def test_devices_control_missing_credentials_graceful():
    with patch.dict(
        os.environ,
        {
            "WIN_MNZ_IP": "",
            "WIN_MNZ_USER": "",
            "WIN_MNZ_PASSWORD": "",
        },
        clear=False,
    ):
        res_shutdown = shutdown_windows_sync()
        res_restart = restart_windows_sync()
        res_status = get_windows_status_sync()

    assert res_shutdown["success"] is False
    assert res_shutdown["reason"] == "missing_credentials"
    assert res_restart["success"] is False
    assert res_restart["reason"] == "missing_credentials"
    assert res_status["online"] is False
    assert res_status["reason"] == "missing_credentials"
