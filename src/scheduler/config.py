import json
from pathlib import Path
import re
from typing import Any
from zoneinfo import ZoneInfo

from apscheduler.triggers.cron import CronTrigger
from pydantic import BaseModel, Field, field_validator


class ScheduledJob(BaseModel):
    id: str
    name: str
    enabled: bool = True
    cron: str
    recipients: list[str]
    message: str
    delay_seconds: float = 0.5

    @field_validator("cron")
    @classmethod
    def validate_cron(cls, v: str) -> str:
        parts = v.strip().split()
        if len(parts) != 5:
            raise ValueError(f"Expressão cron deve ter exatamente 5 campos (encontrado {len(parts)}): '{v}'")

        try:
            CronTrigger.from_crontab(v)
        except Exception as exc:
            raise ValueError(f"Expressão cron inválida '{v}': {exc}") from exc

        return v

    @field_validator("recipients")
    @classmethod
    def validate_and_sanitize_recipients(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("A lista de 'recipients' não pode estar vazia.")

        sanitized: list[str] = []
        for item in v:
            recipient = str(item).strip()

            if "@g.us" in recipient:
                prefix = recipient.split("@g.us")[0]
                if not re.fullmatch(r"[0-9]{8,22}(-[0-9]{8,15})?", prefix):
                    raise ValueError(f"Destinatário de grupo inválido: '{recipient}'")
                sanitized.append(f"{prefix}@g.us")
            elif "@s.whatsapp.net" in recipient:
                prefix = recipient.split("@s.whatsapp.net")[0].lstrip("+")
                if not re.fullmatch(r"[0-9]{8,22}", prefix):
                    raise ValueError(f"Destinatário individual inválido: '{recipient}'")
                sanitized.append(f"{prefix}@s.whatsapp.net")
            else:
                if "@" in recipient:
                    raise ValueError(f"Destinatário com domínio inválido: '{recipient}'")
                cleaned = recipient.lstrip("+")
                if not re.fullmatch(r"[0-9]{8,22}", cleaned):
                    raise ValueError(f"Número de telefone inválido (mínimo 8 dígitos numéricos): '{recipient}'")
                sanitized.append(f"{cleaned}@s.whatsapp.net")

        return sanitized


class SchedulerConfig(BaseModel):
    timezone: str = "America/Sao_Paulo"
    jobs: list[ScheduledJob] = Field(default_factory=list)

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, v: str) -> str:
        try:
            ZoneInfo(v)
        except Exception as exc:
            raise ValueError(f"Fuso horário inválido '{v}': {exc}") from exc
        return v


def load_scheduler_config(filepath: str | Path) -> SchedulerConfig:
    """Carrega configuração do agendador a partir de um arquivo JSON.

    - Se o arquivo não existir, retorna um SchedulerConfig vazio com fuso horário padrão.
    - Se o arquivo contiver JSON inválido ou schema incompatível, propaga a exceção.
    """
    path = Path(filepath)
    if not path.exists():
        return SchedulerConfig(timezone="America/Sao_Paulo", jobs=[])

    content = path.read_text(encoding="utf-8")
    data = json.loads(content)
    return SchedulerConfig.model_validate(data)
