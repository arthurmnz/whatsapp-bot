import asyncio
import logging
import re
from typing import Any

from bs4 import BeautifulSoup
import httpx

from app.modules.jobs_career.sources.base import (
    JobSourceAdapter,
    NormalizedJob,
    parse_iso_datetime,
    strip_html,
)

logger = logging.getLogger(__name__)

_JOB_ID_RE = re.compile(r"(\d{6,14})")


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
        job_id: str,
        headers: dict[str, str],
    ) -> str:
        if not job_id:
            return ""
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

        base_kw = (query or "").strip() or "developer"
        keywords = f"{base_kw} {seniority}".strip() if seniority and seniority not in base_kw.lower() else base_kw

        params: dict[str, Any] = {
            "keywords": keywords,
            "location": location_kw,
            "start": 0,
        }
        if work_model == "remote":
            params["f_WT"] = "2"

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }

        try:
            async with httpx.AsyncClient(timeout=12.0) as client:
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

                # Enriquece até 8 vagas em paralelo com timeout curto
                enrich_count = min(len(parsed_cards), min(limit, 8))
                detail_tasks = [
                    self._fetch_job_description(client, parsed_cards[i]["job_id"], headers)
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

                    results.append(
                        NormalizedJob(
                            source=self.source_name,
                            external_id=str(card_data["external_id"] or "") or None,
                            source_url=card_data["source_url"],
                            title=card_data["title"][:300],
                            company_name=card_data["company_name"][:255] if card_data["company_name"] else None,
                            location=card_data["location"][:255] if card_data["location"] else None,
                            work_model="remote" if work_model == "remote" else None,
                            description_raw=desc_raw,
                            posted_at=card_data["posted_at"],
                        ).finalize()
                    )
                return results
        except Exception as exc:
            logger.warning("Falha ao consultar LinkedIn Guest Search: %s", exc)
            return []
