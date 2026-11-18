import logging
from typing import Any

import httpx

from app.modules.jobs_career.sources.base import (
    JobSourceAdapter,
    NormalizedJob,
    parse_iso_datetime,
    strip_html,
)

logger = logging.getLogger(__name__)

_SENIORITY_PT_MAP = {
    "intern": "estágio",
    "junior": "júnior",
    "mid": "pleno",
    "senior": "sênior",
    "lead": "tech lead",
}


class GupyAdapter(JobSourceAdapter):
    """Adapter para API pública de vagas do portal Gupy."""

    source_name = "gupy"
    endpoint = "https://portal.api.gupy.io/api/v1/jobs"

    async def fetch_jobs(self, query: str = "", limit: int = 20, **kwargs: Any) -> list[NormalizedJob]:
        seniority = (kwargs.get("seniority") or "").strip().lower()
        work_model = (kwargs.get("work_model") or "").strip().lower()

        base_query = (query or "").strip() or "desenvolvedor"
        sen_term = _SENIORITY_PT_MAP.get(seniority, seniority)
        job_name = base_query
        if sen_term and sen_term.lower() not in base_query.lower():
            job_name = f"{base_query} {sen_term}".strip()

        params: dict[str, Any] = {
            "jobName": job_name,
            "limit": max(5, min(50, int(limit))),
            "offset": 0,
        }
        if work_model == "remote":
            params["workplaceType"] = "remote"

        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; C3PO-CareerAgent/1.0)",
            "Accept": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=12.0) as client:
                resp = await client.get(self.endpoint, params=params, headers=headers)
                if resp.is_error:
                    return []
                payload = resp.json()
        except Exception as exc:
            logger.warning("Falha ao consultar Gupy API: %s", exc)
            return []

        raw_jobs = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(raw_jobs, list):
            return []

        results: list[NormalizedJob] = []
        for item in raw_jobs:
            if not isinstance(item, dict):
                continue
            title = str(item.get("name") or "").strip()
            if not title:
                continue

            desc = strip_html(str(item.get("description") or "")) or title
            company = str(item.get("companyName") or "").strip() or None
            loc_parts = [
                str(item.get("city") or "").strip(),
                str(item.get("state") or "").strip(),
                str(item.get("country") or "").strip(),
            ]
            location = ", ".join(p for p in loc_parts if p) or None

            is_remote = bool(item.get("isRemoteWork", False))
            workplace = str(item.get("workplaceType") or "").lower()
            if is_remote or "remote" in workplace:
                inferred_wm = "remote"
            elif "hybrid" in workplace:
                inferred_wm = "hybrid"
            elif "on-site" in workplace or "onsite" in workplace:
                inferred_wm = "onsite"
            else:
                inferred_wm = "unknown"

            results.append(
                NormalizedJob(
                    source=self.source_name,
                    external_id=str(item.get("id") or ""),
                    source_url=str(item.get("jobUrl") or ""),
                    title=title[:300],
                    company_name=company[:255] if company else None,
                    location=location[:255] if location else None,
                    work_model=inferred_wm,
                    description_raw=desc,
                    posted_at=parse_iso_datetime(item.get("publishedDate")),
                ).finalize()
            )
            if len(results) >= limit:
                break

        return results
