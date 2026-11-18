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

_STOPWORDS_PT_EN = {"de", "da", "do", "das", "dos", "para", "com", "em", "e", "ou", "a", "o", "and", "or", "for", "with"}
_WORKPLACE_PARAM_MAP = {
    "remote": "remote",
    "hybrid": "hybrid",
    "onsite": "on-site",
}


class GupyAdapter(JobSourceAdapter):
    """Adapter para API pública de vagas do portal Gupy com busca em cascata."""

    source_name = "gupy"
    endpoints = (
        "https://portal.api.gupy.io/api/v1/jobs",
        "https://portal.api.gupy.io/api/v2/jobs",
    )

    @staticmethod
    def _build_candidate_queries(query: str) -> list[str]:
        base_query = re.sub(r"\s+", " ", (query or "").strip()) or "desenvolvedor"
        candidates: list[str] = [base_query]
        tokens = [
            t.strip()
            for t in re.split(r"[\s,/|]+", base_query)
            if len(t.strip()) >= 2 and t.strip().lower() not in _STOPWORDS_PT_EN
        ]
        if len(tokens) > 1:
            # Prioriza o último termo (geralmente a tecnologia ex: "Python") e depois o primeiro
            for tok in [tokens[-1], tokens[0], *tokens[1:-1]]:
                if tok not in candidates:
                    candidates.append(tok)
                if len(candidates) >= 4:
                    break
        return candidates

    async def _query_gupy(
        self,
        client: httpx.AsyncClient,
        job_name: str,
        limit: int,
        work_model: str,
        headers: dict[str, str],
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "jobName": job_name,
            "limit": max(5, min(50, int(limit))),
            "offset": 0,
        }
        mapped_wm = _WORKPLACE_PARAM_MAP.get(work_model)
        if mapped_wm:
            params["workplaceType"] = mapped_wm

        for endpoint in self.endpoints:
            try:
                resp = await client.get(endpoint, params=params, headers=headers)
                if resp.is_error:
                    continue
                payload = resp.json()
                if isinstance(payload, dict):
                    items = payload.get("data") or payload.get("results") or payload.get("jobs")
                elif isinstance(payload, list):
                    items = payload
                else:
                    items = None
                if isinstance(items, list):
                    return [x for x in items if isinstance(x, dict)]
            except Exception as exc:
                logger.warning("Falha ao consultar Gupy (%s): %s", endpoint, exc)
                continue
        return []

    async def fetch_jobs(self, query: str = "", limit: int = 20, **kwargs: Any) -> list[NormalizedJob]:
        work_model = (kwargs.get("work_model") or "").strip().lower()
        candidates = self._build_candidate_queries(query)
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://portal.gupy.io",
            "Referer": "https://portal.gupy.io/",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8",
        }

        raw_jobs: list[dict[str, Any]] = []
        try:
            async with httpx.AsyncClient(timeout=12.0, follow_redirects=True) as client:
                for candidate_q in candidates:
                    raw_jobs = await self._query_gupy(client, candidate_q, limit, work_model, headers)
                    if raw_jobs:
                        break
        except Exception as exc:
            logger.warning("Falha ao consultar Gupy API: %s", exc)
            return []

        results: list[NormalizedJob] = []
        for item in raw_jobs:
            title = str(item.get("name") or item.get("title") or "").strip()
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
                    source_url=str(item.get("jobUrl") or item.get("url") or ""),
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
