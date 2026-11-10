import asyncio
import ipaddress
import logging
import os
import socket
from typing import Any
import wakeonlan
import paramiko

from app.modules.devices_control.config import (
    WindowsSSHConfig,
    get_windows_ssh_config,
    get_windows_wol_config,
)

logger = logging.getLogger(__name__)

SHUTDOWN_COMMAND = "shutdown /s /f /t 0"
RESTART_COMMAND = "shutdown /r /f /t 0"
STATUS_COMMAND = "hostname"


def _mask_secret(text: str, secret: str) -> str:
    """Remove qualquer ocorrência acidental da senha em mensagens de erro ou logs."""
    if not secret or not text:
        return text
    return text.replace(secret, "***REDACTED***")


def _decode_output(raw: bytes | str) -> str:
    """Decodifica bytes retornados pelo terminal do Windows (cp850/utf-8) com fallback seguro."""
    if isinstance(raw, str):
        return raw
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp850", errors="replace")


def _derive_subnet_broadcast(ip_str: str) -> str | None:
    """Deriva o endereço de broadcast /24 a partir de um IPv4 válido (ex: 192.168.0.200 -> 192.168.0.255)."""
    if not ip_str:
        return None
    try:
        ip_obj = ipaddress.IPv4Address(ip_str.strip())
        network = ipaddress.IPv4Network(f"{ip_obj}/24", strict=False)
        return str(network.broadcast_address)
    except ValueError:
        return None


def wake_windows_sync() -> dict[str, Any]:
    """Envia um Magic Packet Wake-on-LAN (102 bytes) via UDP broadcast para ligar o PC Windows."""
    try:
        config = get_windows_wol_config()
    except ValueError as exc:
        logger.error("Configuração Wake-on-LAN inválida ao ligar Windows: %s", exc)
        return {
            "success": False,
            "action": "wake",
            "reason": "invalid_mac",
            "message": f"⚠️ Configuração Wake-on-LAN inválida: {exc}",
        }

    try:
        wakeonlan.wake(config.mac)

        logger.info("Magic Packet WOL enviado para MAC %s (%s:%d)", config.mac, config.broadcast, config.port)
        return {
            "success": True,
            "action": "wake",
            "reason": "ok",
            "mac": config.mac,
            "broadcast": config.broadcast,
            "port": config.port,
            "message": f"⚡ Pacote Wake-on-LAN enviado com sucesso para o PC com Windows (MAC: {config.mac})!",
        }
    except OSError as exc:
        logger.error("Erro de rede ao enviar pacote Wake-on-LAN (%s): %s", config.mac, exc)
        return {
            "success": False,
            "action": "wake",
            "reason": "network_error",
            "mac": config.mac,
            "message": "🔴 Não foi possível enviar o pacote Wake-on-LAN na rede.",
        }


def _run_ssh_command(command: str, config: WindowsSSHConfig) -> tuple[str, str]:
    """Executa um comando no Windows via SSH usando Paramiko e garante fechamento do cliente."""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        client.connect(
            hostname=config.ip,
            port=config.port,
            username=config.user,
            password=config.password,
            timeout=config.timeout,
            banner_timeout=config.timeout,
            auth_timeout=config.timeout,
            look_for_keys=False,
            allow_agent=False,
        )
        stdin, stdout, stderr = client.exec_command(command, timeout=config.timeout)
        out_str = _decode_output(stdout.read()).strip()
        err_str = _decode_output(stderr.read()).strip()
        return out_str, err_str
    finally:
        client.close()


def shutdown_windows_sync() -> dict[str, Any]:
    """Envia o comando literal de desligamento (`shutdown /s /f /t 0`) via SSH de forma síncrona."""
    try:
        config = get_windows_ssh_config()
    except ValueError as exc:
        logger.error("Configuração SSH inválida ao desligar Windows: %s", exc)
        return {
            "success": False,
            "action": "shutdown",
            "reason": "missing_credentials",
            "message": "⚠️ Configuração SSH do PC Windows incompleta ou inválida.",
        }

    try:
        out_str, err_str = _run_ssh_command(SHUTDOWN_COMMAND, config)
        return {
            "success": True,
            "action": "shutdown",
            "reason": "ok",
            "stdout": out_str,
            "stderr": err_str,
            "message": "💻 Comando para desligar o PC com Windows enviado com sucesso!",
        }
    except paramiko.AuthenticationException:
        logger.error("Falha de autenticação SSH no host %s com usuário %s", config.ip, config.user)
        return {
            "success": False,
            "action": "shutdown",
            "reason": "authentication_failed",
            "message": "🔒 Falha de autenticação SSH ao tentar desligar o PC com Windows.",
        }
    except (TimeoutError, socket.timeout):
        logger.warning("Timeout SSH ao tentar desligar o PC Windows (%s)", config.ip)
        return {
            "success": False,
            "action": "shutdown",
            "reason": "timeout",
            "message": "🔴 Não foi possível desligar o PC com Windows: host offline ou tempo limite esgotado.",
        }
    except (paramiko.SSHException, OSError) as exc:
        safe_err = _mask_secret(str(exc), config.password)
        logger.error("Erro SSH/rede ao desligar PC Windows (%s): %s", config.ip, safe_err)
        return {
            "success": False,
            "action": "shutdown",
            "reason": "unreachable",
            "message": "🔴 Não foi possível desligar o PC com Windows: falha na conexão SSH.",
        }


def restart_windows_sync() -> dict[str, Any]:
    """Envia o comando literal de reinicialização (`shutdown /r /f /t 0`) via SSH de forma síncrona."""
    try:
        config = get_windows_ssh_config()
    except ValueError as exc:
        logger.error("Configuração SSH inválida ao reiniciar Windows: %s", exc)
        return {
            "success": False,
            "action": "restart",
            "reason": "missing_credentials",
            "message": "⚠️ Configuração SSH do PC Windows incompleta ou inválida.",
        }

    try:
        out_str, err_str = _run_ssh_command(RESTART_COMMAND, config)
        return {
            "success": True,
            "action": "restart",
            "reason": "ok",
            "stdout": out_str,
            "stderr": err_str,
            "message": "💻 Comando para reiniciar o PC com Windows enviado com sucesso!",
        }
    except paramiko.AuthenticationException:
        logger.error("Falha de autenticação SSH no host %s com usuário %s", config.ip, config.user)
        return {
            "success": False,
            "action": "restart",
            "reason": "authentication_failed",
            "message": "🔒 Falha de autenticação SSH ao tentar reiniciar o PC com Windows.",
        }
    except (TimeoutError, socket.timeout):
        logger.warning("Timeout SSH ao tentar reiniciar o PC Windows (%s)", config.ip)
        return {
            "success": False,
            "action": "restart",
            "reason": "timeout",
            "message": "🔴 Não foi possível reiniciar o PC com Windows: host offline ou tempo limite esgotado.",
        }
    except (paramiko.SSHException, OSError) as exc:
        safe_err = _mask_secret(str(exc), config.password)
        logger.error("Erro SSH/rede ao reiniciar PC Windows (%s): %s", config.ip, safe_err)
        return {
            "success": False,
            "action": "restart",
            "reason": "unreachable",
            "message": "🔴 Não foi possível reiniciar o PC com Windows: falha na conexão SSH.",
        }


def get_windows_status_sync() -> dict[str, Any]:
    """Verifica o status do PC Windows executando `hostname` via SSH de forma síncrona."""
    try:
        config = get_windows_ssh_config()
    except ValueError as exc:
        logger.error("Configuração SSH inválida ao consultar status do Windows: %s", exc)
        return {
            "online": False,
            "hostname": None,
            "reason": "missing_credentials",
            "message": "⚠️ Configuração SSH do PC Windows incompleta ou inválida.",
        }

    try:
        out_str, _ = _run_ssh_command(STATUS_COMMAND, config)
        hostname = out_str.splitlines()[0].strip() if out_str else config.ip
        return {
            "online": True,
            "hostname": hostname,
            "reason": "ok",
            "message": f"🟢 PC com Windows está ONLINE (Host: {hostname}).",
        }
    except paramiko.AuthenticationException:
        logger.error("Falha de autenticação SSH ao consultar status em %s", config.ip)
        return {
            "online": False,
            "hostname": None,
            "reason": "authentication_failed",
            "message": "🔒 PC com Windows respondeu na rede, mas houve falha de autenticação SSH.",
        }
    except (TimeoutError, socket.timeout):
        logger.info("Timeout ao verificar status do PC Windows (%s): host offline.", config.ip)
        return {
            "online": False,
            "hostname": None,
            "reason": "timeout",
            "message": "🔴 PC com Windows está OFFLINE (tempo limite de conexão esgotado).",
        }
    except (paramiko.SSHException, OSError) as exc:
        safe_err = _mask_secret(str(exc), config.password)
        logger.info("PC Windows (%s) inacessível via SSH: %s", config.ip, safe_err)
        return {
            "online": False,
            "hostname": None,
            "reason": "unreachable",
            "message": "🔴 PC com Windows está OFFLINE ou inacessível na rede.",
        }


async def wake_windows() -> dict[str, Any]:
    """Wrapper assíncrono não bloqueante para ligar o PC Windows via Wake-on-LAN."""
    return await asyncio.to_thread(wake_windows_sync)


async def shutdown_windows() -> dict[str, Any]:
    """Wrapper assíncrono não bloqueante para desligar o PC Windows via SSH."""
    return await asyncio.to_thread(shutdown_windows_sync)


async def restart_windows() -> dict[str, Any]:
    """Wrapper assíncrono não bloqueante para reiniciar o PC Windows via SSH."""
    return await asyncio.to_thread(restart_windows_sync)


async def get_windows_status() -> dict[str, Any]:
    """Wrapper assíncrono não bloqueante para verificar o status do PC Windows via SSH."""
    return await asyncio.to_thread(get_windows_status_sync)
