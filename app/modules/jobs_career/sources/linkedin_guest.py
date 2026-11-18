import asyncio
import logging
import re
from typing import Any

from bs4 import BeautifulSoup
import httpx

from app.modules.jobs_career.skills_taxonomy import infer_seniority
from app.modules.jobs_career.sources.base import (
    JobSourceAdapter,
    NormalizedJob,
    parse_iso_datetime,
    strip_html,
)

logger = logging.getLogger(__name__)

_JOB_ID_RE = re.compile(r"(\d{6,14})")
_LINKEDIN_WT_MAP = {
    "remote": "2",
    "hybrid": "3",
    "onsite": "1",
}
_LINKEDIN_EXP_MAP = {
    "intern": "1",
    "junior": "2",
    "mid": "3,4",
    "senior": "4",
    "lead": "5",
}


class LinkedInGuestAdapter(JobSourceAdapter):
    """Adapter para consulta pública Guest Search do LinkedIn Jobs (sem login/bypass)."""

    source_name = "linkedin"
    search_url = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
    detail_url_tpl = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"

    @staticmethod
    def _extract_job_id(urn: str, href: str) -> str:
        if urn:
            m = _JOB_ID_RE.search(urn)
            if m:
                return m.group(1)
        if href:
            m = _JOB_ID_RE.search(href)
            if m:
                return m.group(1)
        return ""

    async def _fetch_job_description(
        self,
        client: httpx.AsyncClient,
        sem: asyncio.Semaphore,
        job_id: str,
        headers: dict[str, str],
    ) -> str:
        if not job_id:
            return ""
        async with sem:
            try:
                resp = await client.get(
                    self.detail_url_tpl.format(job_id=job_id),
                    headers=headers,
                    timeout=6.0,
                )
                if resp.status_code != 200 or not resp.text:
                    return ""
                soup = BeautifulSoup(resp.text, "html.parser")
                markup = soup.select_one(".show-more-less-html__markup")
                if markup:
                    return strip_html(str(markup))
            except Exception:
                return ""
        return ""

    async def fetch_jobs(self, query: str = "", limit: int = 20, **kwargs: Any) -> list[NormalizedJob]:
        seniority = (kwargs.get("seniority") or "").strip().lower()
        location_kw = (kwargs.get("location") or "").strip() or "Brasil"
        work_model = (kwargs.get("work_model") or "").strip().lower()

        keywords = (query or "").strip() or "developer"

        params: dict[str, Any] = {
            "keywords": keywords,
            "location": location_kw,
            "start": 0,
        }
        if work_model in _LINKEDIN_WT_MAP:
            params["f_WT"] = _LINKEDIN_WT_MAP[work_model]
        if seniority in _LINKEDIN_EXP_MAP:
            params["f_E"] = _LINKEDIN_EXP_MAP[seniority]

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8",
        }

        try:
            async with httpx.AsyncClient(timeout=12.0, follow_redirects=True) as client:
                resp = await client.get(self.search_url, params=params, headers=headers)
                if resp.status_code != 200 or not resp.text:
                    return []

                soup = BeautifulSoup(resp.text, "html.parser")
                cards = soup.select("li")
                parsed_cards: list[dict[str, Any]] = []

                for li in cards:
                    card = li.select_one(".base-search-card") or li
                    title_el = card.select_one(".base-search-card__title")
                    if not title_el:
                        continue
                    title = title_el.get_text(strip=True)
                    if not title:
                        continue

                    company_el = card.select_one(".base-search-card__subtitle")
                    loc_el = card.select_one(".job-search-card__location")
                    link_el = card.select_one("a.base-card__full-link")
                    time_el = card.select_one("time[datetime]")

                    company = company_el.get_text(strip=True) if company_el else ""
                    card_loc = loc_el.get_text(strip=True) if loc_el else location_kw
                    raw_href = str(link_el.get("href") or "") if link_el else ""
                    clean_url = raw_href.split("?", 1)[0] if "linkedin.com/jobs/view" in raw_href else raw_href

                    urn = str(card.get("data-entity-urn") or li.get("data-entity-urn") or "")
                    job_id = self._extract_job_id(urn, clean_url)
                    posted_at = (
                        parse_iso_datetime(str(time_el.get("datetime") or ""))
                        if time_el and time_el.get("datetime")
                        else None
                    )

                    parsed_cards.append(
                        {
                            "external_id": urn or job_id,
                            "job_id": job_id,
                            "title": title,
                            "company_name": company or None,
                            "location": card_loc or location_kw,
                            "source_url": clean_url or None,
                            "posted_at": posted_at,
                        }
                    )
                    if len(parsed_cards) >= limit:
                        break

                if not parsed_cards:
                    return []

                # Limita enriquecimento para no máximo 4 detalhes com concorrência controlada
                enrich_count = min(len(parsed_cards), min(limit, 4))
                sem = asyncio.Semaphore(2)
                detail_tasks = [
                    self._fetch_job_description(client, sem, parsed_cards[i]["job_id"], headers)
                    for i in range(enrich_count)
                ]
                enriched_descs = await asyncio.gather(*detail_tasks, return_exceptions=True)

                results: list[NormalizedJob] = []
                for idx, card_data in enumerate(parsed_cards):
                    desc_raw = ""
                    if idx < len(enriched_descs) and isinstance(enriched_descs[idx], str):
                        desc_raw = enriched_descs[idx].strip()
                    if not desc_raw:
                        parts = [
                            card_data["title"],
                            card_data["company_name"] or "",
                            card_data["location"] or "",
                            f"Keywords: {keywords}" if keywords else "",
                        ]
                        desc_raw = " — ".join(p for p in parts if p)

                    inferred_sen = infer_seniority(card_data["title"])
                    if inferred_sen == "unknown":
                        inferred_sen = infer_seniority(desc_raw)
                    fallback_sen = (
                        seniority
                        if (seniority in _LINKEDIN_EXP_MAP and inferred_sen == "unknown")
                        else (inferred_sen if inferred_sen != "unknown" else None)
                    )

                    results.append(
                        NormalizedJob(
                            source=self.source_name,
                            external_id=str(card_data["external_id"] or "") or None,
                            source_url=card_data["source_url"],
                            title=card_data["title"][:300],
                            company_name=card_data["company_name"][:255] if card_data["company_name"] else None,
                            location=card_data["location"][:255] if card_data["location"] else None,
                            work_model=work_model if work_model in _LINKEDIN_WT_MAP else None,
                            seniority=fallback_sen,
                            description_raw=desc_raw,
                            posted_at=card_data["posted_at"],
                        ).finalize()
                    )
                return results
        except Exception as exc:
            logger.warning("Falha ao consultar LinkedIn Guest Search: %s", exc)
            return []
