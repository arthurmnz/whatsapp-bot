from datetime import datetime, timezone
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


class HimalayasAdapter(JobSourceAdapter):
    """Adapter para API pública gratuita da Himalayas (vagas remotas tech)."""

    source_name = "himalayas"
    endpoint = "https://himalayas.app/jobs/api"

    async def fetch_jobs(self, query: str = "", limit: int = 20, **kwargs: Any) -> list[NormalizedJob]:
        params = {"limit": max(5, min(50, limit)), "offset": 0}
        try:
            async with httpx.AsyncClient(timeout=12.0, follow_redirects=True) as client:
                resp = await client.get(self.endpoint, params=params)
                if resp.is_error:
                    return []
                payload = resp.json()
        except Exception as exc:
            logger.warning("Falha ao consultar Himalayas API: %s", exc)
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
            desc = strip_html(str(item.get("description") or item.get("excerpt") or ""))
            categories = [str(c) for c in (item.get("categories") or []) if c]
            if categories:
                desc = f"Categories: {', '.join(categories)}\n\n{desc}"
            haystack = f"{title} {desc}".lower()
            if query_terms and not any(t in haystack for t in query_terms):
                continue

            locs = item.get("locationRestrictions") or []
            location_str = ", ".join(str(x) for x in locs[:4]) if isinstance(locs, list) and locs else "Remote (Global)"

            pub_date = item.get("pubDate")
            posted_at = None
            if isinstance(pub_date, (int, float)):
                posted_at = datetime.fromtimestamp(pub_date, tz=timezone.utc)
            elif isinstance(pub_date, str):
                posted_at = parse_iso_datetime(pub_date)

            results.append(
                NormalizedJob(
                    source=self.source_name,
                    external_id=str(item.get("guid") or item.get("slug") or ""),
                    source_url=str(item.get("applicationLink") or item.get("guid") or ""),
                    title=title[:300],
                    company_name=str(item.get("companyName") or "").strip() or None,
                    location=location_str[:255],
                    work_model="remote",
                    salary_min=float(item["minSalary"]) if item.get("minSalary") else None,
                    salary_max=float(item["maxSalary"]) if item.get("maxSalary") else None,
                    salary_currency=str(item.get("currency") or "USD").upper() if item.get("minSalary") else None,
                    language="en",
                    description_raw=desc or title,
                    posted_at=posted_at,
                ).finalize()
            )
            if len(results) >= limit:
                break
        return results
