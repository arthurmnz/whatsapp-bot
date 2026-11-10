import asyncio
from datetime import datetime
import os
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient
import httpx
import pytest

from src.evolution_client import _get_evolution_config
from src.scheduler.config import load_scheduler_config
from src.scheduler.service import CronScheduler, render_message
from src.webhook import app


def test_fastapi_lifespan_starts_scheduler():
    """Valida que o lifespan do FastAPI inicializa e encerra o CronScheduler corretamente."""
    with TestClient(app) as client:
        response = client.post("/webhook", json={"event": "other"})
        # Evento ignorado retorna 400
        assert response.status_code == 400


def test_scheduled_messages_config_and_next_run():
    """Valida a integridade do scheduled_messages.json real e calcula o próximo disparo."""
    config = load_scheduler_config("config/scheduled_messages.json")
    assert config.timezone == "America/Sao_Paulo"
    assert len(config.jobs) >= 2

    scheduler = CronScheduler()
    scheduler.start()
    scheduler.register_jobs(config)

    jobs = scheduler._scheduler.get_jobs()
    assert len(jobs) == len([j for j in config.jobs if j.enabled])

    tz = ZoneInfo(config.timezone)
    now = datetime.now(tz)

    for job in jobs:
        assert job.next_run_time is not None
        assert job.next_run_time > now

    scheduler.shutdown()


@pytest.mark.asyncio
async def test_evolution_api_connectivity_diagnostic():
    """Verifica se as variáveis da Evolution API estão carregadas e testa o endpoint."""
    base_url, api_key, instance = _get_evolution_config()
    assert base_url.startswith("http"), f"EVOLUTION_API_URL inválida: {base_url}"
    assert api_key, "EVOLUTION_API_KEY ausente"
    assert instance, "EVOLUTION_INSTANCE ausente"

    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            url = f"{base_url}/instance/connectionState/{instance}"
            resp = await client.get(url, headers={"apikey": api_key})
            print(f"\n[DIAGNÓSTICO EVOLUTION API] GET {url} -> Status {resp.status_code}: {resp.text}")
        except Exception as exc:
            print(f"\n[DIAGNÓSTICO EVOLUTION API] Conexão externa: {exc}")
