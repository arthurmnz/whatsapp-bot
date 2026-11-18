from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.auth import require_permission
from app.db.models import User
from app.db.repositories.user_repo import user_has_permission
from app.db.session import get_db
from app.modules.jobs_career.interview_service import generate_interview_prep
from app.modules.jobs_career.models import JobApplication, JobMatch, JobPosting, TailoredResume
from app.modules.jobs_career.profile_service import get_or_create_profile

router = APIRouter(prefix="/api/v1/applications", tags=["applications"])

VALID_STAGES = {
    "wishlist",
    "cv_ready",
    "applied",
    "screening",
    "technical_interview",
    "final_interview",
    "offer",
    "rejected",
    "withdrawn",
}


class CreateApplicationBody(BaseModel):
    company_name: str = Field(..., min_length=1, max_length=255)
    role_title: str = Field(..., min_length=1, max_length=300)
    job_id: int | None = None
    tailored_resume_id: int | None = None
    job_url: str | None = Field(default=None, max_length=1000)
    stage: str = "wishlist"
    notes: str | None = None
    applied_at: datetime | None = None
    follow_up_at: datetime | None = None


class UpdateApplicationBody(BaseModel):
    company_name: str | None = Field(default=None, max_length=255)
    role_title: str | None = Field(default=None, max_length=300)
    job_url: str | None = Field(default=None, max_length=1000)
    tailored_resume_id: int | None = None
    stage: str | None = None
    notes: str | None = None
    applied_at: datetime | None = None
    follow_up_at: datetime | None = None


class InterviewPrepBody(BaseModel):
    target_language: str = "auto"



def _validate_job_access_for_user(db: Session, user_id: int, job_id: int) -> JobPosting:
    posting = db.query(JobPosting).filter(JobPosting.id == job_id).first()
    if posting is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vaga informada não encontrada.")
    if posting.source == "manual":
        has_match = (
            db.query(JobMatch)
            .filter(JobMatch.user_id == user_id, JobMatch.job_id == posting.id)
            .first()
        )
        if has_match is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vaga informada não encontrada.")
    return posting

def _serialize_application(app_obj: JobApplication) -> dict[str, Any]:
    return {
        "id": app_obj.id,
        "user_id": app_obj.user_id,
        "job_id": app_obj.job_id,
        "tailored_resume_id": app_obj.tailored_resume_id,
        "company_name": app_obj.company_name,
        "role_title": app_obj.role_title,
        "job_url": app_obj.job_url or "",
        "stage": app_obj.stage,
        "notes": app_obj.notes or "",
        "applied_at": app_obj.applied_at.isoformat() if app_obj.applied_at else None,
        "follow_up_at": app_obj.follow_up_at.isoformat() if app_obj.follow_up_at else None,
        "created_at": app_obj.created_at.isoformat() if app_obj.created_at else None,
        "updated_at": app_obj.updated_at.isoformat() if app_obj.updated_at else None,
    }


@router.get("")
async def list_applications(
    stage: str | None = Query(default=None),
    user: User = Depends(require_permission("jobs:applications")),
    db: Session = Depends(get_db),
):
    q = db.query(JobApplication).filter(JobApplication.user_id == user.id)
    if stage:
        q = q.filter(JobApplication.stage == stage)
    items = q.order_by(JobApplication.updated_at.desc()).all()
    return {"items": [_serialize_application(a) for a in items]}


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_application(
    body: CreateApplicationBody,
    user: User = Depends(require_permission("jobs:applications")),
    db: Session = Depends(get_db),
):
    if body.stage not in VALID_STAGES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Estágio inválido. Use: {', '.join(sorted(VALID_STAGES))}",
        )

    if body.job_id is not None:
        _validate_job_access_for_user(db, user.id, body.job_id)

    if body.tailored_resume_id is not None:
        tr = (
            db.query(TailoredResume)
            .filter(TailoredResume.id == body.tailored_resume_id, TailoredResume.user_id == user.id)
            .first()
        )
        if tr is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Currículo otimizado não encontrado.")

    now = datetime.now(timezone.utc)
    applied_at = body.applied_at or (now if body.stage == "applied" else None)
    app_obj = JobApplication(
        user_id=user.id,
        job_id=body.job_id,
        tailored_resume_id=body.tailored_resume_id,
        company_name=body.company_name.strip(),
        role_title=body.role_title.strip(),
        job_url=body.job_url,
        stage=body.stage,
        notes=body.notes,
        applied_at=applied_at,
        follow_up_at=body.follow_up_at,
        created_at=now,
        updated_at=now,
    )
    db.add(app_obj)
    db.commit()
    db.refresh(app_obj)
    return _serialize_application(app_obj)


@router.patch("/{application_id}")
async def update_application(
    application_id: int,
    body: UpdateApplicationBody,
    user: User = Depends(require_permission("jobs:applications")),
    db: Session = Depends(get_db),
):
    app_obj = (
        db.query(JobApplication)
        .filter(JobApplication.id == application_id, JobApplication.user_id == user.id)
        .first()
    )
    if app_obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidatura não encontrada.")

    if body.stage is not None:
        if body.stage not in VALID_STAGES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Estágio inválido. Use: {', '.join(sorted(VALID_STAGES))}",
            )
        app_obj.stage = body.stage
        if body.stage == "applied" and app_obj.applied_at is None and body.applied_at is None:
            app_obj.applied_at = datetime.now(timezone.utc)

    if body.company_name is not None:
        app_obj.company_name = body.company_name.strip()
    if body.role_title is not None:
        app_obj.role_title = body.role_title.strip()
    if body.job_url is not None:
        app_obj.job_url = body.job_url
    if "tailored_resume_id" in body.model_fields_set:
        if body.tailored_resume_id is None:
            app_obj.tailored_resume_id = None
        else:
            tr = (
                db.query(TailoredResume)
                .filter(TailoredResume.id == body.tailored_resume_id, TailoredResume.user_id == user.id)
                .first()
            )
            if tr is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Currículo otimizado não encontrado.")
            app_obj.tailored_resume_id = body.tailored_resume_id
    if body.notes is not None:
        app_obj.notes = body.notes
    if body.applied_at is not None:
        app_obj.applied_at = body.applied_at
    if body.follow_up_at is not None:
        app_obj.follow_up_at = body.follow_up_at

    app_obj.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(app_obj)
    return _serialize_application(app_obj)


@router.delete("/{application_id}")
async def delete_application(
    application_id: int,
    user: User = Depends(require_permission("jobs:applications")),
    db: Session = Depends(get_db),
):
    app_obj = (
        db.query(JobApplication)
        .filter(JobApplication.id == application_id, JobApplication.user_id == user.id)
        .first()
    )
    if app_obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidatura não encontrada.")
    db.delete(app_obj)
    db.commit()
    return {"status": "deleted", "id": application_id}


@router.post("/{application_id}/interview-prep")
async def create_application_interview_prep(
    application_id: int,
    body: InterviewPrepBody | None = None,
    user: User = Depends(require_permission("jobs:applications")),
    db: Session = Depends(get_db),
):
    if not user_has_permission(user, "jobs:interview"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permissão necessária: jobs:interview")

    app_obj = (
        db.query(JobApplication)
        .filter(JobApplication.id == application_id, JobApplication.user_id == user.id)
        .first()
    )
    if app_obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidatura não encontrada.")

    job_desc = ""
    missing_skills: list[str] = []
    tailored: TailoredResume | None = None
    if app_obj.tailored_resume_id:
        tailored = (
            db.query(TailoredResume)
            .filter(TailoredResume.id == app_obj.tailored_resume_id, TailoredResume.user_id == user.id)
            .first()
        )
        if tailored:
            job_desc = tailored.job_description_snapshot
            missing_skills = list((tailored.evaluation_report or {}).get("real_gaps") or [])

    if not job_desc and app_obj.job_id:
        posting = db.query(JobPosting).filter(JobPosting.id == app_obj.job_id).first()
        if posting:
            if posting.source != "manual" or db.query(JobMatch).filter(JobMatch.user_id == user.id, JobMatch.job_id == posting.id).first() is not None:
                job_desc = posting.description_raw

    profile = get_or_create_profile(db, user.id)
    target_lang = body.target_language if body else "auto"
    prep = await generate_interview_prep(
        job_title=app_obj.role_title,
        company_name=app_obj.company_name,
        job_description=job_desc,
        resume_summary=profile.summary or "",
        missing_skills=missing_skills,
        target_language=target_lang,
    )

    if tailored is not None:
        tailored.interview_prep = prep
        tailored.updated_at = datetime.now(timezone.utc)
        db.commit()

    return {
        "application_id": app_obj.id,
        "company_name": app_obj.company_name,
        "role_title": app_obj.role_title,
        "interview_prep": prep,
    }
