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

_SLUG_RE = re.compile(r"^[a-zA-Z0-9_-]{1,80}$")


def sanitize_company_slug(raw: str) -> str | None:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]", "", (raw or "").strip().lower())
    if _SLUG_RE.fullmatch(cleaned):
        return cleaned
    return None


class GreenhouseAdapter(JobSourceAdapter):
    """Adapter para boards públicos do Greenhouse ATS."""

    source_name = "greenhouse"

    def __init__(self, company_slugs: list[str] | None = None) -> None:
        self.company_slugs = [
            s for s in (sanitize_company_slug(x) for x in (company_slugs or [])) if s
        ]

    async def fetch_jobs(self, query: str = "", limit: int = 20, **kwargs: Any) -> list[NormalizedJob]:
        slugs = kwargs.get("company_slugs") or self.company_slugs
        valid_slugs = [s for s in (sanitize_company_slug(str(x)) for x in slugs) if s]
        if not valid_slugs:
            return []

        query_terms = [t.lower() for t in re.split(r"[\s,]+", query or "") if len(t) >= 2]
        results: list[NormalizedJob] = []

        async with httpx.AsyncClient(timeout=12.0, follow_redirects=True) as client:
            for slug in valid_slugs:
                url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
                try:
                    resp = await client.get(url, params={"content": "true"})
                    if resp.is_error:
                        continue
                    data = resp.json()
                except Exception as exc:
                    logger.warning("Falha ao consultar Greenhouse (%s): %s", slug, exc)
                    continue

                jobs = data.get("jobs") if isinstance(data, dict) else None
                if not isinstance(jobs, list):
                    continue

                for item in jobs:
                    if not isinstance(item, dict):
                        continue
                    title = str(item.get("title") or "").strip()
                    if not title:
                        continue
                    desc = strip_html(str(item.get("content") or ""))
                    loc_obj = item.get("location")
                    location = str(loc_obj.get("name") or "") if isinstance(loc_obj, dict) else ""
                    haystack = f"{title} {location} {desc}".lower()
                    if query_terms and not any(t in haystack for t in query_terms):
                        continue

                    results.append(
                        NormalizedJob(
                            source=self.source_name,
                            external_id=f"{slug}:{item.get('id')}",
                            source_url=str(item.get("absolute_url") or ""),
                            title=title[:300],
                            company_name=slug.replace("-", " ").title(),
                            location=location[:255] or None,
                            description_raw=desc or title,
                            posted_at=parse_iso_datetime(item.get("updated_at")),
                        ).finalize()
                    )
                    if len(results) >= limit:
                        return results
        return results


class LeverAdapter(JobSourceAdapter):
    """Adapter para postings públicos do Lever ATS."""

    source_name = "lever"

    def __init__(self, company_slugs: list[str] | None = None) -> None:
        self.company_slugs = [
            s for s in (sanitize_company_slug(x) for x in (company_slugs or [])) if s
        ]

    async def fetch_jobs(self, query: str = "", limit: int = 20, **kwargs: Any) -> list[NormalizedJob]:
        slugs = kwargs.get("company_slugs") or self.company_slugs
        valid_slugs = [s for s in (sanitize_company_slug(str(x)) for x in slugs) if s]
        if not valid_slugs:
            return []

        query_terms = [t.lower() for t in re.split(r"[\s,]+", query or "") if len(t) >= 2]
        results: list[NormalizedJob] = []

        async with httpx.AsyncClient(timeout=12.0, follow_redirects=True) as client:
            for slug in valid_slugs:
                url = f"https://api.lever.co/v0/postings/{slug}"
                try:
                    resp = await client.get(url, params={"mode": "json"})
                    if resp.is_error:
                        continue
                    jobs = resp.json()
                except Exception as exc:
                    logger.warning("Falha ao consultar Lever (%s): %s", slug, exc)
                    continue

                if not isinstance(jobs, list):
                    continue

                for item in jobs:
                    if not isinstance(item, dict):
                        continue
                    title = str(item.get("text") or "").strip()
                    if not title:
                        continue
                    desc = str(item.get("descriptionPlain") or "") or strip_html(str(item.get("description") or ""))
                    lists_txt = "\n".join(
                        f"{lst.get('text', '')}: {strip_html(str(lst.get('content', '')))}"
                        for lst in (item.get("lists") or [])
                        if isinstance(lst, dict)
                    )
                    full_desc = f"{desc}\n\n{lists_txt}".strip()
                    cats = item.get("categories") if isinstance(item.get("categories"), dict) else {}
                    location = str(cats.get("location") or "").strip()
                    workplace = str(item.get("workplaceType") or "").lower()
                    work_model = "remote" if "remote" in workplace else ("hybrid" if "hybrid" in workplace else "unknown")

                    haystack = f"{title} {location} {full_desc}".lower()
                    if query_terms and not any(t in haystack for t in query_terms):
                        continue

                    created_ms = item.get("createdAt")
                    posted_at = (
                        datetime.fromtimestamp(created_ms / 1000.0, tz=timezone.utc)
                        if isinstance(created_ms, (int, float))
                        else None
                    )

                    results.append(
                        NormalizedJob(
                            source=self.source_name,
                            external_id=f"{slug}:{item.get('id')}",
                            source_url=str(item.get("hostedUrl") or ""),
                            title=title[:300],
                            company_name=slug.replace("-", " ").title(),
                            location=location[:255] or None,
                            work_model=work_model,
                            description_raw=full_desc or title,
                            posted_at=posted_at,
                        ).finalize()
                    )
                    if len(results) >= limit:
                        return results
        return results
