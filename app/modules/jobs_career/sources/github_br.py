import logging
import re
from typing import Any

import httpx

from app.modules.jobs_career.sources.base import (
    JobSourceAdapter,
    NormalizedJob,
    parse_iso_datetime,
)

logger = logging.getLogger(__name__)

DEFAULT_GITHUB_VAGAS_REPOS = [
    "backend-br/vagas",
    "frontendbr/vagas",
    "qa-brasil/vagas",
    "react-brasil/vagas",
]


def _extract_company_from_title(title: str) -> tuple[str, str | None]:
    """Tenta separar título e empresa de padrões comuns do GitHub Vagas (ex: '[Remoto] Dev Python @ Empresa')."""
    at_match = re.search(r"(?:\s+na\s+|\s+no\s+|\s+@\s+)(.+)$", title, re.IGNORECASE)
    if at_match:
        company = at_match.group(1).strip(" []|-")
        clean_title = title[: at_match.start()].strip()
        return clean_title or title, company or None
    return title, None


class GitHubBRAdapter(JobSourceAdapter):
    """Adapter para repositórios públicos brasileiros de vagas no GitHub."""

    source_name = "github_br"

    def __init__(self, repos: list[str] | None = None) -> None:
        self.repos = repos or DEFAULT_GITHUB_VAGAS_REPOS

    async def fetch_jobs(self, query: str = "", limit: int = 20, **kwargs: Any) -> list[NormalizedJob]:
        per_repo = max(5, min(30, limit))
        query_terms = [t.strip().lower() for t in re.split(r"[\s,]+", query or "") if len(t.strip()) >= 2]
        results: list[NormalizedJob] = []

        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "C3PO-CareerAgent/1.0",
        }
        async with httpx.AsyncClient(timeout=12.0, follow_redirects=True) as client:
            for repo in self.repos:
                url = f"https://api.github.com/repos/{repo}/issues"
                try:
                    resp = await client.get(
                        url,
                        params={"state": "open", "per_page": per_repo, "sort": "created", "direction": "desc"},
                        headers=headers,
                    )
                    if resp.status_code in {403, 429}:
                        logger.warning("GitHub API rate limit/access (%s) ao consultar %s.", resp.status_code, repo)
                        continue
                    if resp.is_error:
                        continue
                    issues = resp.json()
                    if not isinstance(issues, list):
                        continue
                except Exception as exc:
                    logger.warning("Falha ao buscar vagas no GitHub (%s): %s", repo, exc)
                    continue

                for issue in issues:
                    if not isinstance(issue, dict) or issue.get("pull_request"):
                        continue
                    raw_title = str(issue.get("title") or "").strip()
                    body = str(issue.get("body") or "").strip()
                    labels = [
                        str(lb.get("name") or "").strip()
                        for lb in (issue.get("labels") or [])
                        if isinstance(lb, dict)
                    ]
                    if not raw_title:
                        continue

                    haystack = f"{raw_title} {' '.join(labels)} {body}".lower()
                    if query_terms and not any(term in haystack for term in query_terms):
                        continue

                    clean_title, company = _extract_company_from_title(raw_title)
                    label_blob = " ".join(labels).lower()
                    work_model = "unknown"
                    if "remoto" in label_blob or "remote" in label_blob:
                        work_model = "remote"
                    elif "hibrido" in label_blob or "híbrido" in label_blob:
                        work_model = "hybrid"
                    elif "presencial" in label_blob:
                        work_model = "onsite"

                    full_desc = body
                    if labels:
                        full_desc = f"Labels: {', '.join(labels)}\n\n{body}"

                    job = NormalizedJob(
                        source=self.source_name,
                        external_id=f"{repo}#{issue.get('number')}",
                        source_url=str(issue.get("html_url") or ""),
                        title=clean_title[:300],
                        company_name=company,
                        location="Brasil" if work_model != "remote" else "Remoto (Brasil)",
                        work_model=work_model,
                        language="pt-BR",
                        description_raw=full_desc or clean_title,
                        posted_at=parse_iso_datetime(issue.get("created_at")),
                    ).finalize()
                    results.append(job)
                    if len(results) >= limit:
                        return results
        return results
