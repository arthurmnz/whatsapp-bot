from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
from typing import Any

from bs4 import BeautifulSoup

from app.modules.jobs_career.skills_taxonomy import (
    detect_language,
    extract_job_requirements,
    infer_contract_type,
    infer_seniority,
    infer_work_model,
)


def strip_html(raw_html: str) -> str:
    """Converte HTML de descrições de vagas em texto limpo preservando quebras básicas."""
    if not raw_html:
        return ""
    soup = BeautifulSoup(raw_html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    return "\n".join(lines)


def compute_dedupe_hash(source: str, external_id: str | None, source_url: str | None, title: str, company: str | None) -> str:
    """Gera hash determinístico SHA-256 para evitar duplicação de vagas."""
    if source_url and source_url.strip():
        base = f"url:{source_url.strip().lower()}"
    elif external_id and external_id.strip():
        base = f"{source}:{external_id.strip().lower()}"
    else:
        base = f"{source}:{(company or '').strip().lower()}:{title.strip().lower()}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


@dataclass
class NormalizedJob:
    source: str
    title: str
    description_raw: str
    external_id: str | None = None
    source_url: str | None = None
    company_name: str | None = None
    location: str | None = None
    work_model: str | None = None
    contract_type: str | None = None
    seniority: str | None = None
    salary_min: float | None = None
    salary_max: float | None = None
    salary_currency: str | None = None
    language: str | None = None
    posted_at: datetime | None = None
    extracted_requirements: dict[str, Any] = field(default_factory=dict)

    def finalize(self) -> "NormalizedJob":
        """Preenche metadados inferidos e requisitos extraídos se estiverem ausentes."""
        reqs = extract_job_requirements(self.description_raw, self.title)
        if not self.extracted_requirements:
            self.extracted_requirements = reqs
        if not self.work_model or self.work_model == "unknown":
            self.work_model = reqs.get("work_model") or infer_work_model(f"{self.title} {self.location or ''} {self.description_raw}")
        if not self.contract_type or self.contract_type == "unknown":
            self.contract_type = reqs.get("contract_type") or infer_contract_type(self.description_raw)
        if not self.seniority or self.seniority == "unknown":
            self.seniority = reqs.get("seniority") or infer_seniority(f"{self.title} {self.description_raw}")
        if self.salary_min is None:
            self.salary_min = reqs.get("salary_min")
        if self.salary_max is None:
            self.salary_max = reqs.get("salary_max")
        if not self.salary_currency:
            self.salary_currency = reqs.get("salary_currency")
        if not self.language:
            self.language = reqs.get("language") or detect_language(f"{self.title}\n{self.description_raw}")
        return self

    @property
    def dedupe_hash(self) -> str:
        return compute_dedupe_hash(
            self.source,
            self.external_id,
            self.source_url,
            self.title,
            self.company_name,
        )


def parse_iso_datetime(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        cleaned = raw.replace("Z", "+00:00")
        dt = datetime.fromisoformat(cleaned)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


class JobSourceAdapter(ABC):
    source_name: str

    @abstractmethod
    async def fetch_jobs(self, query: str = "", limit: int = 20, **kwargs: Any) -> list[NormalizedJob]:
        raise NotImplementedError
