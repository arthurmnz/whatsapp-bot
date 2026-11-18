import logging
import re
from typing import Any

import httpx

from app.modules.jobs_career.sources.base import (
    JobSourceAdapter,
    NormalizedJob,
    parse_iso_datetime,
    strip_html,
)

logger = logging.getLogger(__name__)


class RemoteOKAdapter(JobSourceAdapter):
    """Adapter para API pública gratuita do RemoteOK."""

    source_name = "remoteok"
    endpoint = "https://remoteok.com/api"

    async def fetch_jobs(self, query: str = "", limit: int = 20, **kwargs: Any) -> list[NormalizedJob]:
        headers = {
            "User-Agent": "C3PO-CareerAgent/1.0",
            "Accept": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=12.0) as client:
                resp = await client.get(self.endpoint, headers=headers)
                if resp.is_error:
                    return []
                payload = resp.json()
        except Exception as exc:
            logger.warning("Falha ao consultar RemoteOK API: %s", exc)
            return []

        if not isinstance(payload, list):
            return []

        query_terms = [t.lower() for t in re.split(r"[\s,]+", query or "") if len(t) >= 2]
        results: list[NormalizedJob] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            title = str(item.get("position") or item.get("title") or "").strip()
            if not title:
                continue  # Ignora o legal notice inicial sem position/title

            company = str(item.get("company") or "").strip() or None
            tags = [str(t) for t in (item.get("tags") or []) if t]
            desc = strip_html(str(item.get("description") or ""))
            if tags:
                desc = f"Tags: {', '.join(tags)}\n\n{desc}".strip()

            haystack = f"{title} {company or ''} {' '.join(tags)} {desc}".lower()
            if query_terms and not any(t in haystack for t in query_terms):
                continue

            smin = float(item["salary_min"]) if item.get("salary_min") else None
            smax = float(item["salary_max"]) if item.get("salary_max") else None

            results.append(
                NormalizedJob(
                    source=self.source_name,
                    external_id=str(item.get("id") or item.get("slug") or ""),
                    source_url=str(item.get("url") or item.get("apply_url") or ""),
                    title=title[:300],
                    company_name=company[:255] if company else None,
                    location=str(item.get("location") or "Remote").strip()[:255] or "Remote",
                    work_model="remote",
                    salary_min=smin,
                    salary_max=smax,
                    salary_currency="USD" if (smin or smax) else None,
                    language="en",
                    description_raw=desc or title,
                    posted_at=parse_iso_datetime(item.get("date")),
                ).finalize()
            )
            if len(results) >= limit:
                break

        return results
