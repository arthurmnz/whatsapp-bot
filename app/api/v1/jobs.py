from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import case
from sqlalchemy.orm import Session

from app.core.auth import require_permission
from app.db.models import User
from app.db.session import get_db
from app.modules.jobs_career.models import JobMatch, JobPosting
from app.modules.jobs_career.sources import (
    JobUrlBlockedError,
    ingest_job_from_text,
    ingest_job_from_url,
    normalize_seniority_filter,
    search_and_match_jobs,
    serialize_job_match,
    upsert_job_and_match,
)

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])

VALID_MATCH_STATUSES = {"new", "notified", "saved", "dismissed", "applied"}


class JobSearchBody(BaseModel):
    query: str = ""
    sources: list[str] | None = None
    limit_per_source: int = Field(default=15, ge=1, le=30)
    greenhouse_slugs: list[str] | None = None
    lever_slugs: list[str] | None = None
    seniority: str | None = None
    location: str | None = None
    work_model: str | None = None


class JobIngestBody(BaseModel):
    url: str | None = None
    description_raw: str | None = None
    title: str | None = None
    company_name: str | None = None
    location: str | None = None
    work_model: str | None = None
    contract_type: str | None = None


class UpdateMatchStatusBody(BaseModel):
    status: str


@router.get("")
async def list_jobs(
    status_filter: str | None = Query(default=None, alias="status"),
    min_score: int = Query(default=0, ge=0, le=100),
    source: str | None = Query(default=None),
    language: str | None = Query(default=None),
    seniority: str | None = Query(default=None),
    location: str | None = Query(default=None),
    work_model: str | None = Query(default=None),
    search: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(require_permission("jobs:search")),
    db: Session = Depends(get_db),
):
    q = (
        db.query(JobMatch)
        .join(JobPosting, JobMatch.job_id == JobPosting.id)
        .filter(JobMatch.user_id == user.id, JobMatch.match_score >= min_score)
    )
    if status_filter:
        q = q.filter(JobMatch.status == status_filter)
    if source:
        q = q.filter(JobPosting.source == source)
    if language:
        q = q.filter(JobPosting.language == language)
    norm_sen = normalize_seniority_filter(seniority)
    if norm_sen:
        q = q.filter((JobPosting.seniority == norm_sen) | (JobPosting.seniority == "unknown"))
    if work_model and work_model.strip():
        q = q.filter(JobPosting.work_model == work_model.strip().lower())
    if location and location.strip():
        loc = location.strip()
        loc_pattern = f"%{loc}%"
        if loc.lower() in {"brasil", "brazil", "br"}:
            q = q.filter(
                (JobPosting.location.ilike("%brasil%"))
                | (JobPosting.location.ilike("%brazil%"))
                | (JobPosting.location.ilike("%latam%"))
                | (JobPosting.description_raw.ilike("%brasil%"))
                | (JobPosting.description_raw.ilike("%brazil%"))
                | (JobPosting.language == "pt-BR")
            )
        else:
            q = q.filter(
                (JobPosting.location.ilike(loc_pattern))
                | (JobPosting.description_raw.ilike(loc_pattern))
            )
    if search and search.strip():
        pattern = f"%{search.strip()}%"
        q = q.filter(
            (JobPosting.title.ilike(pattern))
            | (JobPosting.company_name.ilike(pattern))
            | (JobPosting.description_raw.ilike(pattern))
        )

    total = q.count()
    order_cols = []
    if norm_sen:
        order_cols.append(case((JobPosting.seniority == norm_sen, 0), else_=1))
    order_cols.extend([JobMatch.match_score.desc(), JobMatch.created_at.desc()])

    matches = (
        q.order_by(*order_cols)
        .offset(offset)
        .limit(limit)
        .all()
    )
    return {"total": total, "items": [serialize_job_match(m) for m in matches]}


@router.post("/search")
async def search_jobs(
    body: JobSearchBody,
    user: User = Depends(require_permission("jobs:search")),
    db: Session = Depends(get_db),
):
    return await search_and_match_jobs(
        db,
        user.id,
        query=body.query,
        sources=body.sources,
        limit_per_source=body.limit_per_source,
        greenhouse_slugs=body.greenhouse_slugs,
        lever_slugs=body.lever_slugs,
        seniority=body.seniority,
        location=body.location,
        work_model=body.work_model,
    )


@router.post("/ingest", status_code=status.HTTP_201_CREATED)
async def ingest_job(
    body: JobIngestBody,
    user: User = Depends(require_permission("jobs:search")),
    db: Session = Depends(get_db),
):
    if not body.url and not (body.description_raw and body.description_raw.strip()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Informe a URL pública da vaga ou cole a descrição em `description_raw`.",
        )

    try:
        if body.url and not (body.description_raw and body.description_raw.strip()):
            norm_job = await ingest_job_from_url(
                body.url,
                title_override=body.title,
                company_override=body.company_name,
            )
        else:
            norm_job = ingest_job_from_text(
                description_raw=body.description_raw or "",
                title=body.title,
                company_name=body.company_name,
                source_url=body.url,
                location=body.location,
                work_model=body.work_model,
                contract_type=body.contract_type,
            )
    except JobUrlBlockedError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    _, match = upsert_job_and_match(db, user.id, norm_job, default_status="saved")
    db.commit()
    db.refresh(match)
    return serialize_job_match(match)


@router.patch("/matches/{match_id}")
async def update_match_status(
    match_id: int,
    body: UpdateMatchStatusBody,
    user: User = Depends(require_permission("jobs:search")),
    db: Session = Depends(get_db),
):
    if body.status not in VALID_MATCH_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Status inválido. Use um de: {', '.join(sorted(VALID_MATCH_STATUSES))}",
        )
    match = db.query(JobMatch).filter(JobMatch.id == match_id, JobMatch.user_id == user.id).first()
    if match is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match de vaga não encontrado.")

    match.status = body.status
    db.commit()
    db.refresh(match)
    return serialize_job_match(match)
