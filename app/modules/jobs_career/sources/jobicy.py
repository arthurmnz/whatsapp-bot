import logging
import re
from typing import Any

import httpx

from app.modules.jobs_career.skills_taxonomy import infer_seniority
from app.modules.jobs_career.sources.base import (
    JobSourceAdapter,
    NormalizedJob,
    parse_iso_datetime,
    strip_html,
)

logger = logging.getLogger(__name__)


class JobicyAdapter(JobSourceAdapter):
    """Adapter para API pública gratuita do Jobicy (vagas remotas)."""

    source_name = "jobicy"
    endpoint = "https://jobicy.com/api/v2/remote-jobs"

    async def fetch_jobs(self, query: str = "", limit: int = 20, **kwargs: Any) -> list[NormalizedJob]:
        params: dict[str, Any] = {"count": max(1, min(int(limit), 50))}
        query_terms = [t.lower() for t in re.split(r"[\s,]+", query or "") if len(t) >= 2]
        if query_terms and len(query_terms) == 1 and re.fullmatch(r"[a-z0-9_+-]+", query_terms[0]):
            params["tag"] = query_terms[0]

        headers = {
            "User-Agent": "C3PO-CareerAgent/1.0",
            "Accept": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=12.0) as client:
                resp = await client.get(self.endpoint, params=params, headers=headers)
                if resp.is_error:
                    return []
                payload = resp.json()
        except Exception as exc:
            logger.warning("Falha ao consultar Jobicy API: %s", exc)
            return []

        raw_jobs = payload.get("jobs") if isinstance(payload, dict) else None
        if not isinstance(raw_jobs, list):
            return []

        results: list[NormalizedJob] = []
        for item in raw_jobs:
            if not isinstance(item, dict):
                continue
            title = str(item.get("jobTitle") or "").strip()
            if not title:
                continue

            company = str(item.get("companyName") or "").strip() or None
            industries = item.get("jobIndustry") or []
            ind_str = ", ".join(str(x) for x in industries) if isinstance(industries, list) else str(industries)
            desc = strip_html(str(item.get("jobDescription") or item.get("jobExcerpt") or ""))
            if ind_str:
                desc = f"Industry: {ind_str}\n\n{desc}".strip()

            haystack = f"{title} {company or ''} {ind_str} {desc}".lower()
            if query_terms and not any(t in haystack for t in query_terms):
                continue

            raw_type = item.get("jobType")
            contract = (
                ", ".join(str(x).lower() for x in raw_type)
                if isinstance(raw_type, list)
                else str(raw_type or "unknown").lower()
            )
            job_level = str(item.get("jobLevel") or "")
            seniority = infer_seniority(f"{title} {job_level}")

            smin = float(item["annualSalaryMin"]) if item.get("annualSalaryMin") else None
            smax = float(item["annualSalaryMax"]) if item.get("annualSalaryMax") else None
            curr = str(item.get("salaryCurrency") or "USD").upper() if (smin or smax) else None

            results.append(
                NormalizedJob(
                    source=self.source_name,
                    external_id=str(item.get("id") or ""),
                    source_url=str(item.get("url") or ""),
                    title=title[:300],
                    company_name=company[:255] if company else None,
                    location=str(item.get("jobGeo") or "Remote").strip()[:255] or "Remote",
                    work_model="remote",
                    contract_type=contract[:50] or "unknown",
                    seniority=seniority,
                    salary_min=smin,
                    salary_max=smax,
                    salary_currency=curr,
                    language="en",
                    description_raw=desc or title,
                    posted_at=parse_iso_datetime(item.get("pubDate")),
                ).finalize()
            )
            if len(results) >= limit:
                break

        return results
