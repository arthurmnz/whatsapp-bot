from datetime import datetime, timezone
import logging
import re
from typing import Any

import httpx

from app.modules.jobs_career.sources.base import (
    JobSourceAdapter,
    NormalizedJob,
    strip_html,
)

logger = logging.getLogger(__name__)


class ArbeitnowAdapter(JobSourceAdapter):
    """Adapter para API pública gratuita da Arbeitnow."""

    source_name = "arbeitnow"
    endpoint = "https://www.arbeitnow.com/api/job-board-api"

    async def fetch_jobs(self, query: str = "", limit: int = 20, **kwargs: Any) -> list[NormalizedJob]:
        try:
            async with httpx.AsyncClient(timeout=12.0) as client:
                resp = await client.get(self.endpoint)
                if resp.is_error:
                    return []
                payload = resp.json()
        except Exception as exc:
            logger.warning("Falha ao consultar Arbeitnow API: %s", exc)
            return []

        raw_jobs = payload.get("data") if isinstance(payload, dict) else None
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

            created_ts = item.get("created_at")
            posted_at = None
            if isinstance(created_ts, (int, float)):
                posted_at = datetime.fromtimestamp(created_ts, tz=timezone.utc)

            is_remote = bool(item.get("remote", False))
            results.append(
                NormalizedJob(
                    source=self.source_name,
                    external_id=str(item.get("slug") or ""),
                    source_url=str(item.get("url") or ""),
                    title=title[:300],
                    company_name=str(item.get("company_name") or "").strip() or None,
                    location=str(item.get("location") or ("Remote" if is_remote else "")).strip() or None,
                    work_model="remote" if is_remote else "unknown",
                    description_raw=desc or title,
                    posted_at=posted_at,
                ).finalize()
            )
            if len(results) >= limit:
                break
        return results
