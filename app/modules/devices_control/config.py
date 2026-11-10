from dataclasses import dataclass, field
import os
import re

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class WindowsSSHConfig:
    ip: str
    user: str
    password: str = field(repr=False)
    port: int = 22
    timeout: float = 5.0

    def __repr__(self) -> str:
        return (
            f"WindowsSSHConfig(ip={self.ip!r}, user={self.user!r}, "
            f"password='***REDACTED***', port={self.port}, timeout={self.timeout})"
        )

    def __str__(self) -> str:
        return self.__repr__()


@dataclass(frozen=True)
class WindowsWOLConfig:
    mac: str
    mac_bytes: bytes = field(repr=False)
    broadcast: str = "255.255.255.255"
    port: int = 9


def parse_mac_address(raw_mac: str) -> tuple[str, bytes]:
    """Valida e normaliza um endereço MAC nos formatos AA:BB:CC:DD:EE:FF, AA-BB-CC-DD-EE-FF ou AABBCCDDEEFF.

    Retorna:
        tuple[str, bytes]: (canonical_mac ex: '10:FF:E0:01:AA:D1', bytes de 6 octetos)
    """
    if not raw_mac or not raw_mac.strip():
        raise ValueError("Endereço MAC (WIN_MNZ_MAC) não configurado ou vazio.")

    cleaned = re.sub(r"[:\-\.\s]", "", raw_mac.strip())
    if not re.fullmatch(r"[0-9a-fA-F]{12}", cleaned):
        raise ValueError(
            f"Endereço MAC inválido ({raw_mac!r}): deve conter exatamente 12 caracteres hexadecimais."
        )

    upper_hex = cleaned.upper()
    canonical_mac = ":".join(upper_hex[i : i + 2] for i in range(0, 12, 2))
    mac_bytes = bytes.fromhex(upper_hex)
    return canonical_mac, mac_bytes


def get_windows_wol_config() -> WindowsWOLConfig:
    """Lê e valida as variáveis de ambiente para Wake-on-LAN (WOL) do PC Windows."""
    raw_mac = (
        os.getenv("WIN_MNZ_MAC")
        or os.getenv("WIN_MNZ_MAC_ADDRESS")
        or os.getenv("WIN_MAC")
        or ""
    ).strip()

    canonical_mac, mac_bytes = parse_mac_address(raw_mac)

    broadcast = os.getenv("WIN_MNZ_BROADCAST", "255.255.255.255").strip() or "255.255.255.255"

    raw_port = os.getenv("WIN_MNZ_WOL_PORT", "9").strip()
    try:
        port = int(raw_port)
        if not (1 <= port <= 65535):
            raise ValueError("Porta fora do intervalo permitido (1-65535).")
    except ValueError as exc:
        raise ValueError(f"WIN_MNZ_WOL_PORT inválido ({raw_port!r}): deve ser um inteiro entre 1 e 65535.") from exc

    return WindowsWOLConfig(
        mac=canonical_mac,
        mac_bytes=mac_bytes,
        broadcast=broadcast,
        port=port,
    )


def get_windows_ssh_config() -> WindowsSSHConfig:
    """Lê e valida as variáveis de ambiente para conexão SSH com o PC Windows.

    Nunca inclui o valor de `WIN_MNZ_PASSWORD` em logs ou mensagens de erro.
    """
    ip = os.getenv("WIN_MNZ_IP", "").strip()
    user = os.getenv("WIN_MNZ_USER", "").strip()
    password = os.getenv("WIN_MNZ_PASSWORD", "")

    missing = []
    if not ip:
        missing.append("WIN_MNZ_IP")
    if not user:
        missing.append("WIN_MNZ_USER")
    if not password:
        missing.append("WIN_MNZ_PASSWORD")

    if missing:
        raise ValueError(
            f"Variáveis de ambiente obrigatórias ausentes para SSH do Windows: {', '.join(missing)}"
        )

    raw_port = os.getenv("WIN_MNZ_PORT", "22").strip()
    try:
        port = int(raw_port)
        if not (1 <= port <= 65535):
            raise ValueError("Porta fora do intervalo permitido (1-65535).")
    except ValueError as exc:
        raise ValueError(f"WIN_MNZ_PORT inválido ({raw_port!r}): deve ser um inteiro entre 1 e 65535.") from exc

    raw_timeout = os.getenv("WIN_MNZ_TIMEOUT", "5").strip()
    try:
        timeout = float(raw_timeout)
        if timeout <= 0:
            raise ValueError("Timeout deve ser maior que zero.")
    except ValueError as exc:
        raise ValueError(f"WIN_MNZ_TIMEOUT inválido ({raw_timeout!r}): deve ser um número positivo.") from exc

    return WindowsSSHConfig(
        ip=ip,
        user=user,
        password=password,
        port=port,
        timeout=timeout,
    )
