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


class RemotiveAdapter(JobSourceAdapter):
    """Adapter para API pública gratuita da Remotive."""

    source_name = "remotive"
    endpoint = "https://remotive.com/api/remote-jobs"

    async def fetch_jobs(self, query: str = "", limit: int = 20, **kwargs: Any) -> list[NormalizedJob]:
        params: dict[str, Any] = {"limit": max(5, min(50, limit))}
        if query and query.strip():
            params["search"] = query.strip()

        try:
            async with httpx.AsyncClient(timeout=12.0) as client:
                resp = await client.get(self.endpoint, params=params)
                if resp.is_error:
                    return []
                payload = resp.json()
        except Exception as exc:
            logger.warning("Falha ao consultar Remotive API: %s", exc)
            return []

        raw_jobs = payload.get("jobs") if isinstance(payload, dict) else None
        if not isinstance(raw_jobs, list):
            return []

        query_terms = [t.lower() for t in re.split(r"[\s,]+", query or "") if len(t) >= 2]
        results: list[NormalizedJob] = []
        for item in raw_jobs:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").strip()
            if not title:
                continue
            desc = strip_html(str(item.get("description") or ""))
            tags = [str(t) for t in (item.get("tags") or []) if t]
            if tags:
                desc = f"Tags: {', '.join(tags)}\n\n{desc}"
            haystack = f"{title} {desc}".lower()
            if query_terms and not any(t in haystack for t in query_terms):
                continue

            results.append(
                NormalizedJob(
                    source=self.source_name,
                    external_id=str(item.get("id") or ""),
                    source_url=str(item.get("url") or ""),
                    title=title[:300],
                    company_name=str(item.get("company_name") or "").strip() or None,
                    location=str(item.get("candidate_required_location") or "Remote").strip(),
                    work_model="remote",
                    contract_type=str(item.get("job_type") or "unknown").lower(),
                    language="en",
                    description_raw=desc or title,
                    posted_at=parse_iso_datetime(item.get("publication_date")),
                ).finalize()
            )
            if len(results) >= limit:
                break
        return results
