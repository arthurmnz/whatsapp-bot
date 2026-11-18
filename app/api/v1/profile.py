from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.auth import require_permission
from app.db.models import User
from app.db.session import get_db
from app.modules.jobs_career.models import CandidateSkill
from app.modules.jobs_career.profile_service import (
    get_or_create_profile,
    serialize_profile,
    update_preferences_payload,
    update_profile_payload,
    upsert_skills_from_names,
)

router = APIRouter(prefix="/api/v1/profile", tags=["profile"])


class PreferencesPayload(BaseModel):
    target_roles: list[str] | None = None
    seniority_levels: list[str] | None = None
    work_models: list[str] | None = None
    contract_types: list[str] | None = None
    min_salary: float | None = None
    salary_currency: str | None = None
    desired_stack: list[str] | None = None
    dealbreakers: list[str] | None = None
    target_companies: list[str] | None = None
    preferred_language: str | None = None
    auto_search_enabled: bool | None = None
    min_notify_score: int | None = None


class ProfileUpdateBody(BaseModel):
    headline: str | None = Field(default=None, max_length=255)
    summary: str | None = None
    years_experience: float | None = Field(default=None, ge=0, le=70)
    location: str | None = Field(default=None, max_length=255)
    linkedin_url: str | None = Field(default=None, max_length=500)
    github_url: str | None = Field(default=None, max_length=500)
    portfolio_url: str | None = Field(default=None, max_length=500)
    languages: list[dict[str, Any]] | None = None
    skills: list[Any] | None = None
    preferences: PreferencesPayload | None = None


class AddSkillsBody(BaseModel):
    skills: list[str] = Field(..., min_length=1)
    is_core: bool = False


@router.get("")
async def get_profile(
    user: User = Depends(require_permission("jobs:profile")),
    db: Session = Depends(get_db),
):
    profile = get_or_create_profile(db, user.id)
    return serialize_profile(profile)


@router.put("")
async def put_profile(
    body: ProfileUpdateBody,
    user: User = Depends(require_permission("jobs:profile")),
    db: Session = Depends(get_db),
):
    payload = body.model_dump(exclude_unset=True)
    return update_profile_payload(db, user.id, payload)


@router.put("/preferences")
async def put_preferences(
    body: PreferencesPayload,
    user: User = Depends(require_permission("jobs:profile")),
    db: Session = Depends(get_db),
):
    profile = get_or_create_profile(db, user.id)
    update_preferences_payload(db, profile, body.model_dump(exclude_unset=True), commit=True)
    return serialize_profile(profile)


@router.post("/skills")
async def add_skills(
    body: AddSkillsBody,
    user: User = Depends(require_permission("jobs:profile")),
    db: Session = Depends(get_db),
):
    upsert_skills_from_names(db, user.id, body.skills, is_core=body.is_core)
    profile = get_or_create_profile(db, user.id)
    return serialize_profile(profile)


@router.delete("/skills/{skill_id}")
async def delete_skill(
    skill_id: int,
    user: User = Depends(require_permission("jobs:profile")),
    db: Session = Depends(get_db),
):
    profile = get_or_create_profile(db, user.id)
    skill = (
        db.query(CandidateSkill)
        .filter(CandidateSkill.id == skill_id, CandidateSkill.profile_id == profile.id)
        .first()
    )
    if skill is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill não encontrada.")
    db.delete(skill)
    db.commit()
    db.refresh(profile)
    return serialize_profile(profile)
