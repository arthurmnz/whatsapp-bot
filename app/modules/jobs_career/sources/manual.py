import ipaddress
import json
import logging
import socket
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
import httpx

from app.modules.jobs_career.sources.base import NormalizedJob, strip_html

logger = logging.getLogger(__name__)

MAX_URL_RESPONSE_BYTES = 2 * 1024 * 1024  # 2 MB
ALLOWED_URL_CONTENT_TYPES = {"text/html", "text/plain", "application/xhtml+xml"}
_BLOCKED_HOSTNAMES = {"localhost", "localhost.localdomain", "metadata.google.internal"}
_ANTI_BOT_MARKERS = (
    "cf-challenge",
    "cf-browser-verification",
    "g-recaptcha",
    "hcaptcha",
    "challenges.cloudflare.com",
    "turnstile",
    "captcha",
    "verify you are human",
    "just a moment...",
    "authwall",
    "sign in to view",
    "entrar no linkedin",
)


class JobUrlBlockedError(ValueError):
    """Indica que a URL exige login/anti-bot ou não é pública, orientando colar o texto."""


def _is_forbidden_ip(ip_str: str) -> bool:
    try:
        ip_obj = ipaddress.ip_address(ip_str)
    except ValueError:
        return True
    return (
        not ip_obj.is_global
        or ip_obj.is_private
        or ip_obj.is_loopback
        or ip_obj.is_link_local
        or ip_obj.is_multicast
        or ip_obj.is_reserved
        or ip_obj.is_unspecified
    )


def validate_public_url(url: str) -> str:
    """Valida URL contra SSRF (somente http/https públicos, bloqueando IPs privados/CGNAT/loopback)."""
    cleaned = (url or "").strip()
    if not cleaned:
        raise ValueError("URL vazia.")

    parsed = urlparse(cleaned)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Somente URLs http:// ou https:// são permitidas.")

    hostname = (parsed.hostname or "").strip().lower()
    if not hostname or hostname in _BLOCKED_HOSTNAMES or hostname.endswith((".local", ".internal")):
        raise ValueError("Hostname não permitido por política de segurança.")

    try:
        ipaddress.ip_address(hostname)
        if _is_forbidden_ip(hostname):
            raise ValueError("Endereços IP privados ou não-globais não são permitidos.")
    except ValueError as exc:
        if "não são permitidos" in str(exc):
            raise

    try:
        addr_info = socket.getaddrinfo(hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
    except socket.gaierror as exc:
        raise ValueError(f"Não foi possível resolver o domínio da URL informada ({hostname}).") from exc

    ips = {info[4][0] for info in addr_info if info and info[4]}
    if not ips:
        raise ValueError("Domínio sem endereço IP público válido.")

    for ip in ips:
        if _is_forbidden_ip(ip):
            raise ValueError("Destino resolvido para faixa de IP não-global/reservada (bloqueado por proteção SSRF).")

    return cleaned


async def fetch_url_text(url: str) -> tuple[str, str]:
    """Busca texto HTML/plain de URL pública com trust_env=False, validação Content-Type e limite 2 MB."""
    current_url = validate_public_url(url)
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; C3PO-CareerAgent/1.0)",
        "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    }

    async with httpx.AsyncClient(timeout=15.0, follow_redirects=False, trust_env=False) as client:
        for _ in range(4):
            async with client.stream("GET", current_url, headers=headers) as resp:
                if resp.status_code in {301, 302, 303, 307, 308} and resp.headers.get("location"):
                    next_url = urljoin(current_url, resp.headers["location"])
                    current_url = validate_public_url(next_url)
                    continue

                if resp.status_code in {401, 403, 429}:
                    raise JobUrlBlockedError(
                        "A página da vaga exige login ou possui proteção contra leitura automática "
                        f"(HTTP {resp.status_code}). Por favor, copie e cole o texto da descrição da vaga diretamente."
                    )

                if resp.is_error:
                    raise ValueError(f"Erro ao acessar a URL da vaga (HTTP {resp.status_code}).")

                raw_ct = (resp.headers.get("content-type") or "text/html").split(";", 1)[0].strip().lower()
                if raw_ct and raw_ct not in ALLOWED_URL_CONTENT_TYPES:
                    raise ValueError(
                        f"Tipo de conteúdo não suportado ({raw_ct}). Esperado HTML ou texto."
                    )

                raw_len = resp.headers.get("content-length")
                if raw_len and raw_len.isdigit() and int(raw_len) > MAX_URL_RESPONSE_BYTES:
                    raise ValueError("A página excede o limite máximo permitido de 2 MB.")

                chunks: list[bytes] = []
                total = 0
                async for chunk in resp.aiter_bytes():
                    total += len(chunk)
                    if total > MAX_URL_RESPONSE_BYTES:
                        raise ValueError("A página excede o limite máximo permitido de 2 MB.")
                    chunks.append(chunk)

                encoding = resp.encoding or "utf-8"
                body_text = b"".join(chunks).decode(encoding, errors="replace")
                return current_url, body_text

    raise ValueError("Limite de redirecionamentos excedido ao acessar a URL.")


def _extract_json_ld_job(soup: BeautifulSoup) -> dict[str, Any] | None:
    for script in soup.find_all("script", type="application/ld+json"):
        raw = script.string or script.get_text() or ""
        if not raw.strip():
            continue
        try:
            data = json.loads(raw)
        except Exception:
            continue
        candidates = data if isinstance(data, list) else [data]
        for item in candidates:
            if isinstance(item, dict) and str(item.get("@type", "")).lower() == "jobposting":
                return item
            if isinstance(item, dict) and isinstance(item.get("@graph"), list):
                for node in item["@graph"]:
                    if isinstance(node, dict) and str(node.get("@type", "")).lower() == "jobposting":
                        return node
    return None


async def ingest_job_from_url(
    url: str,
    title_override: str | None = None,
    company_override: str | None = None,
) -> NormalizedJob:
    """Extrai dados de uma vaga a partir de URL pública, respeitando SSRF e barreiras anti-bot."""
    current_url, html = await fetch_url_text(url)

    low_html = html.lower()
    if any(marker in low_html for marker in _ANTI_BOT_MARKERS):
        raise JobUrlBlockedError(
            "Esta página está protegida por desafio anti-bot/CAPTCHA ou parede de login. "
            "Não contornamos proteções de acesso — por favor, copie e cole o texto da vaga aqui."
        )

    soup = BeautifulSoup(html, "html.parser")
    ld_job = _extract_json_ld_job(soup)

    extracted_title = title_override or ""
    extracted_company = company_override or ""
    extracted_location = ""
    extracted_desc = ""

    if ld_job:
        extracted_title = extracted_title or str(ld_job.get("title") or "").strip()
        hiring_org = ld_job.get("hiringOrganization")
        if isinstance(hiring_org, dict) and not extracted_company:
            extracted_company = str(hiring_org.get("name") or "").strip()
        extracted_desc = strip_html(str(ld_job.get("description") or ""))
        job_loc = ld_job.get("jobLocation")
        if isinstance(job_loc, dict):
            addr = job_loc.get("address")
            if isinstance(addr, dict):
                extracted_location = ", ".join(
                    p for p in [addr.get("addressLocality"), addr.get("addressRegion"), addr.get("addressCountry")] if p
                )

    if not extracted_title:
        h1 = soup.find("h1")
        if h1 and h1.get_text(strip=True):
            extracted_title = h1.get_text(strip=True)
        elif soup.title and soup.title.get_text(strip=True):
            extracted_title = soup.title.get_text(strip=True)

    if not extracted_desc:
        main_el = soup.find("main") or soup.find("article") or soup.body
        if main_el:
            for tag in main_el(["nav", "header", "footer", "script", "style", "noscript"]):
                tag.decompose()
            lines = [ln.strip() for ln in main_el.get_text(separator="\n").splitlines() if ln.strip()]
            extracted_desc = "\n".join(lines[:200])

    if not extracted_desc or len(extracted_desc) < 40:
        raise JobUrlBlockedError(
            "Não foi possível extrair texto suficiente desta URL (pode exigir JavaScript/login). "
            "Cole o texto completo da descrição da vaga para analisarmos."
        )

    return NormalizedJob(
        source="manual",
        source_url=current_url,
        title=(extracted_title or "Vaga Importada")[:300],
        company_name=extracted_company[:255] if extracted_company else None,
        location=extracted_location[:255] if extracted_location else None,
        description_raw=extracted_desc,
    ).finalize()


def ingest_job_from_text(
    description_raw: str,
    title: str | None = None,
    company_name: str | None = None,
    source_url: str | None = None,
    location: str | None = None,
    work_model: str | None = None,
    contract_type: str | None = None,
) -> NormalizedJob:
    """Normaliza vaga cadastrada manualmente via texto colado."""
    cleaned_desc = (description_raw or "").strip()
    if not cleaned_desc:
        raise ValueError("A descrição da vaga não pode estar vazia.")

    inferred_title = (title or "").strip()
    if not inferred_title:
        first_line = next((ln.strip("#* -") for ln in cleaned_desc.splitlines() if ln.strip()), "")
        inferred_title = first_line[:120] if first_line else "Vaga Manual"

    return NormalizedJob(
        source="manual",
        source_url=source_url.strip() if source_url else None,
        title=inferred_title[:300],
        company_name=company_name.strip()[:255] if company_name else None,
        location=location.strip()[:255] if location else None,
        work_model=work_model,
        contract_type=contract_type,
        description_raw=cleaned_desc,
    ).finalize()
