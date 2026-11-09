import asyncio
from datetime import datetime
import logging
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from src.evolution_client import send_text
from src.scheduler.config import ScheduledJob, SchedulerConfig

logger = logging.getLogger(__name__)

DIAS_SEMANA = [
    "segunda-feira",
    "terça-feira",
    "quarta-feira",
    "quinta-feira",
    "sexta-feira",
    "sábado",
    "domingo",
]


def render_message(template: str, timezone: str = "America/Sao_Paulo") -> str:
    """Renderiza mensagens interpolando {dia_semana}, {data} e {hora} no fuso indicado.

    Preserva chaves arbitrárias (ex: {chave_desconhecida}) sem lançar exceções.
    """
    try:
        tz = ZoneInfo(timezone)
    except Exception:
        tz = ZoneInfo("America/Sao_Paulo")

    now = datetime.now(tz)
    dia_semana = DIAS_SEMANA[now.weekday()]
    data = now.strftime("%d/%m/%Y")
    hora = now.strftime("%H:%M")

    return (
        template.replace("{dia_semana}", dia_semana)
        .replace("{data}", data)
        .replace("{hora}", hora)
    )


async def dispatch_job(job: ScheduledJob, timezone: str = "America/Sao_Paulo") -> None:
    """Despacha as mensagens de um ScheduledJob para todos os destinatários."""
    rendered_text = render_message(job.message, timezone=timezone)

    for idx, recipient in enumerate(job.recipients):
        try:
            logger.info("Enviando mensagem agendada para %s (job: %s)", recipient, job.id)
            await send_text(to=recipient, text=rendered_text)
        except Exception as exc:
            logger.error("Erro ao enviar mensagem para %s (job %s): %s", recipient, job.id, exc)

        if job.delay_seconds > 0 and idx < len(job.recipients) - 1:
            await asyncio.sleep(job.delay_seconds)


class CronScheduler:
    """Gerenciador de agendamento de mensagens com APScheduler."""

    def __init__(self) -> None:
        self._scheduler = AsyncIOScheduler()

    @property
    def is_running(self) -> bool:
        """Indica se o agendador está em execução."""
        return self._scheduler.running

    def start(self) -> None:
        """Inicia o agendador em background se ainda não estiver em execução."""
        if not self._scheduler.running:
            self._scheduler.start()

    def shutdown(self, wait: bool = False) -> None:
        """Encerra o agendador."""
        if self._scheduler.running:
            self._scheduler.shutdown(wait=wait)

    def register_jobs(self, config: SchedulerConfig) -> None:
        """Registra os jobs habilitados da configuração no agendador."""
        for job in config.jobs:
            if not job.enabled:
                continue

            trigger = CronTrigger.from_crontab(job.cron, timezone=config.timezone)
            self._scheduler.add_job(
                dispatch_job,
                trigger=trigger,
                args=[job, config.timezone],
                id=job.id,
                name=job.name,
                replace_existing=True,
            )
            logger.info("Job '%s' (%s) registrado com cron '%s'.", job.name, job.id, job.cron)
