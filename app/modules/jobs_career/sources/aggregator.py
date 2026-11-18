import asyncio
from datetime import datetime, timezone
import logging
from typing import Any

from sqlalchemy.orm import Session

from app.modules.jobs_career.matching import calculate_job_match
from app.modules.jobs_career.models import JobMatch, JobPosting
from app.modules.jobs_career.profile_service import get_or_create_profile
from app.modules.jobs_career.sources.arbeitnow import ArbeitnowAdapter
from app.modules.jobs_career.sources.base import JobSourceAdapter, NormalizedJob
from app.modules.jobs_career.sources.github_br import GitHubBRAdapter
from app.modules.jobs_career.sources.greenhouse_lever import GreenhouseAdapter, LeverAdapter
from app.modules.jobs_career.sources.himalayas import HimalayasAdapter
from app.modules.jobs_career.sources.remotive import RemotiveAdapter

logger = logging.getLogger(__name__)

ALL_FREE_SOURCES = ["github_br", "remotive", "arbeitnow", "himalayas", "greenhouse", "lever"]


def _build_adapters(
    sources: list[str] | None,
    greenhouse_slugs: list[str] | None,
    lever_slugs: list[str] | None,
) -> list[JobSourceAdapter]:
    selected = [s.lower().strip() for s in (sources or ALL_FREE_SOURCES) if s]
    adapters: list[JobSourceAdapter] = []
    if "github_br" in selected:
        adapters.append(GitHubBRAdapter())
    if "remotive" in selected:
        adapters.append(RemotiveAdapter())
    if "arbeitnow" in selected:
        adapters.append(ArbeitnowAdapter())
    if "himalayas" in selected:
        adapters.append(HimalayasAdapter())
    if "greenhouse" in selected and greenhouse_slugs:
        adapters.append(GreenhouseAdapter(company_slugs=greenhouse_slugs))
    if "lever" in selected and lever_slugs:
        adapters.append(LeverAdapter(company_slugs=lever_slugs))
    return adapters


def upsert_job_and_match(
    db: Session,
    user_id: int,
    norm_job: NormalizedJob,
    default_status: str = "new",
) -> tuple[JobPosting, JobMatch]:
    """Salva/atualiza JobPosting deduplicada e calcula JobMatch para o usuário."""
    norm_job.finalize()
    d_hash = norm_job.dedupe_hash

    posting = db.query(JobPosting).filter(JobPosting.dedupe_hash == d_hash).first()
    now = datetime.now(timezone.utc)
    if posting is None:
        posting = JobPosting(
            source=norm_job.source,
            external_id=norm_job.external_id,
            source_url=norm_job.source_url,
            dedupe_hash=d_hash,
            title=norm_job.title,
            company_name=norm_job.company_name,
            location=norm_job.location,
            work_model=norm_job.work_model,
            contract_type=norm_job.contract_type,
            seniority=norm_job.seniority,
            salary_min=norm_job.salary_min,
            salary_max=norm_job.salary_max,
            salary_currency=norm_job.salary_currency,
            language=norm_job.language or "en",
            description_raw=norm_job.description_raw,
            extracted_requirements=norm_job.extracted_requirements,
            posted_at=norm_job.posted_at,
            fetched_at=now,
        )
        db.add(posting)
        db.flush()
    else:
        posting.fetched_at = now
        if norm_job.extracted_requirements:
            posting.extracted_requirements = norm_job.extracted_requirements

    profile = get_or_create_profile(db, user_id)
    eval_res = calculate_job_match(
        profile=profile,
        skills=list(profile.skills or []),
        preferences=profile.preferences,
        job_posting=posting,
    )

    match = (
        db.query(JobMatch)
        .filter(JobMatch.user_id == user_id, JobMatch.job_id == posting.id)
        .first()
    )
    if match is None:
        match = JobMatch(
            user_id=user_id,
            job_id=posting.id,
            match_score=eval_res.match_score,
            score_breakdown=eval_res.score_breakdown,
            matched_skills=eval_res.matched_skills,
            missing_skills=eval_res.missing_skills,
            ai_rationale=eval_res.ai_rationale,
            status=default_status,
            created_at=now,
        )
        db.add(match)
    else:
        match.match_score = eval_res.match_score
        match.score_breakdown = eval_res.score_breakdown
        match.matched_skills = eval_res.matched_skills
        match.missing_skills = eval_res.missing_skills
        match.ai_rationale = eval_res.ai_rationale

    db.flush()
    return posting, match


def serialize_job_match(match: JobMatch) -> dict[str, Any]:
    job = match.job
    return {
        "match_id": match.id,
        "job_id": match.job_id,
        "match_score": match.match_score,
        "score_breakdown": match.score_breakdown or {},
        "matched_skills": match.matched_skills or [],
        "missing_skills": match.missing_skills or [],
        "ai_rationale": match.ai_rationale or "",
        "status": match.status,
        "created_at": match.created_at.isoformat() if match.created_at else None,
        "job": {
            "id": job.id,
            "source": job.source,
            "external_id": job.external_id,
            "source_url": job.source_url,
            "title": job.title,
            "company_name": job.company_name,
            "location": job.location,
            "work_model": job.work_model,
            "contract_type": job.contract_type,
            "seniority": job.seniority,
            "salary_min": job.salary_min,
            "salary_max": job.salary_max,
            "salary_currency": job.salary_currency,
            "language": job.language,
            "description_raw": job.description_raw,
            "extracted_requirements": job.extracted_requirements or {},
            "posted_at": job.posted_at.isoformat() if job.posted_at else None,
            "fetched_at": job.fetched_at.isoformat() if job.fetched_at else None,
        }
        if job
        else None,
    }


async def search_and_match_jobs(
    db: Session,
    user_id: int,
    query: str = "",
    sources: list[str] | None = None,
    limit_per_source: int = 15,
    greenhouse_slugs: list[str] | None = None,
    lever_slugs: list[str] | None = None,
) -> dict[str, Any]:
    """Busca vagas em paralelo nas fontes gratuitas, deduplica e calcula score com perfil."""
    profile = get_or_create_profile(db, user_id)
    pref = profile.preferences

    effective_query = (query or "").strip()
    if not effective_query and pref and pref.target_roles:
        effective_query = str(pref.target_roles[0])

    target_companies = [str(c).strip() for c in (pref.target_companies if pref else []) if str(c).strip()]
    eff_gh = greenhouse_slugs if greenhouse_slugs is not None else target_companies
    eff_lv = lever_slugs if lever_slugs is not None else target_companies

    adapters = _build_adapters(sources, eff_gh, eff_lv)
    tasks = [adapter.fetch_jobs(query=effective_query, limit=limit_per_source) for adapter in adapters]
    responses = await asyncio.gather(*tasks, return_exceptions=True)

    source_stats: dict[str, Any] = {}
    all_matches: list[JobMatch] = []
    seen_match_ids: set[int] = set()

    for adapter, res in zip(adapters, responses):
        if isinstance(res, Exception):
            logger.warning("Erro na fonte %s: %s", adapter.source_name, res)
            source_stats[adapter.source_name] = {"fetched": 0, "error": str(res)}
            continue
        source_stats[adapter.source_name] = {"fetched": len(res)}
        for norm_job in res:
            _, match = upsert_job_and_match(db, user_id, norm_job)
            if match.id not in seen_match_ids:
                seen_match_ids.add(match.id)
                all_matches.append(match)

    db.commit()
    for m in all_matches:
        db.refresh(m)

    all_matches.sort(key=lambda m: (m.match_score, m.created_at), reverse=True)
    return {
        "query": effective_query,
        "total_fetched": sum(v.get("fetched", 0) for v in source_stats.values()),
        "sources": source_stats,
        "items": [serialize_job_match(m) for m in all_matches],
    }
