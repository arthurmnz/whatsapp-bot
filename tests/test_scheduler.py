import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import ValidationError

from src.scheduler.config import ScheduledJob, SchedulerConfig, load_scheduler_config
from src.scheduler.service import (
    CronScheduler,
    dispatch_job,
    render_message,
)


# ─── 1. Testes de validação de expressão Cron ─────────────────────────────────

def test_scheduled_job_valid_cron():
    job = ScheduledJob(
        id="test_job",
        name="Job de Teste",
        enabled=True,
        cron="0 9 * * 1-5",
        recipients=["5511999999999"],
        message="Olá mundo!",
    )
    assert job.cron == "0 9 * * 1-5"


@pytest.mark.parametrize(
    "invalid_cron",
    [
        "invalid_cron",
        "99 * * * *",       # minuto inválido
        "* * * *",          # crontab requer 5 campos
        "* * * * * * *",    # campos em excesso
    ],
)
def test_scheduled_job_invalid_cron(invalid_cron):
    with pytest.raises(ValidationError):
        ScheduledJob(
            id="test_job",
            name="Job de Teste",
            enabled=True,
            cron=invalid_cron,
            recipients=["5511999999999"],
            message="Olá!",
        )


# ─── 2. Testes de validação e sanitização de Destinatários ────────────────────

def test_scheduled_job_recipients_sanitization():
    job = ScheduledJob(
        id="test_job",
        name="Job de Teste",
        cron="0 9 * * *",
        recipients=[
            "5511999999999",
            "+5511888888888",
            "5511777777777@s.whatsapp.net",
            "120363000000000000@g.us",
        ],
        message="Teste",
    )
    assert job.recipients == [
        "5511999999999@s.whatsapp.net",
        "5511888888888@s.whatsapp.net",
        "5511777777777@s.whatsapp.net",
        "120363000000000000@g.us",
    ]


@pytest.mark.parametrize(
    "invalid_recipient",
    [
        "destinatario_invalido",
        "contato@dominio.com",
        "123",              # menos de 8 dígitos
        "abc12345678",      # letras misturadas no número
    ],
)
def test_scheduled_job_invalid_recipients(invalid_recipient):
    with pytest.raises(ValidationError):
        ScheduledJob(
            id="test_job",
            name="Job de Teste",
            cron="0 9 * * *",
            recipients=[invalid_recipient],
            message="Teste",
        )


def test_scheduled_job_empty_recipients():
    with pytest.raises(ValidationError):
        ScheduledJob(
            id="test_job",
            name="Job de Teste",
            cron="0 9 * * *",
            recipients=[],
            message="Teste",
        )


# ─── 3. Testes de Carregamento da Configuração ────────────────────────────────

def test_load_scheduler_config_existing_file():
    config = load_scheduler_config("config/scheduled_messages.json")
    assert config.timezone == "America/Sao_Paulo"
    assert len(config.jobs) >= 1
    assert any(j.id for j in config.jobs)


def test_load_scheduler_config_fallback_non_existent(tmp_path: Path):
    non_existent = tmp_path / "nao_existe.json"
    config = load_scheduler_config(non_existent)
    assert config.jobs == []
    assert isinstance(config.timezone, str)


def test_load_scheduler_config_invalid_json(tmp_path: Path):
    invalid_file = tmp_path / "broken.json"
    invalid_file.write_text("{ json invalido...", encoding="utf-8")
    with pytest.raises(Exception):
        load_scheduler_config(invalid_file)


# ─── 4. Testes de Renderização de Mensagens e Variáveis ───────────────────────

def test_render_message_interpolation():
    template = "Olá! Hoje é {dia_semana}, dia {data} e agora são {hora}."
    rendered = render_message(template, timezone="America/Sao_Paulo")

    assert "{dia_semana}" not in rendered
    assert "{data}" not in rendered
    assert "{hora}" not in rendered
    import re
    assert re.search(r"\d{2}/\d{2}/\d{4}", rendered) is not None
    assert re.search(r"\d{2}:\d{2}", rendered) is not None


def test_render_message_with_arbitrary_braces():
    template = "Mensagem normal com {chave_desconhecida} e {'json': true}."
    rendered = render_message(template, timezone="America/Sao_Paulo")
    assert rendered == template


# ─── 5. Testes de Despacho (dispatch_job) Apenas Texto ────────────────────────

@pytest.mark.asyncio
async def test_dispatch_job_success_text_only():
    job = ScheduledJob(
        id="job_text_only",
        name="Teste Dispatch Texto",
        cron="0 9 * * *",
        recipients=["5511999999999", "5511888888888"],
        message="Mensagem teste às {hora}",
        delay_seconds=0.01,
    )

    with patch("src.scheduler.service.send_text", new_callable=AsyncMock) as mock_send_text:
        await dispatch_job(job)
        assert mock_send_text.call_count == 2
        calls = [c.kwargs for c in mock_send_text.call_args_list]
        assert calls[0]["to"] == "5511999999999@s.whatsapp.net"
        assert calls[1]["to"] == "5511888888888@s.whatsapp.net"
        assert "Mensagem teste às " in calls[0]["text"]


# ─── 6. Testes do CronScheduler (Jobs ativos vs inativos) ──────────────────────

@pytest.mark.asyncio
async def test_cron_scheduler_register_jobs():
    scheduler = CronScheduler()
    config = SchedulerConfig(
        timezone="America/Sao_Paulo",
        jobs=[
            ScheduledJob(
                id="ativo",
                name="Job Ativo",
                enabled=True,
                cron="0 8 * * *",
                recipients=["5511999999999"],
                message="Ativo",
            ),
            ScheduledJob(
                id="inativo",
                name="Job Inativo",
                enabled=False,
                cron="0 10 * * *",
                recipients=["5511999999999"],
                message="Inativo",
            ),
        ],
    )

    scheduler.start()
    scheduler.register_jobs(config)

    jobs = scheduler._scheduler.get_jobs()
    job_ids = [j.id for j in jobs]

    assert "ativo" in job_ids
    assert "inativo" not in job_ids
    assert scheduler.is_running is True

    scheduler.shutdown()
    await asyncio.sleep(0.01)
    assert scheduler.is_running is False
