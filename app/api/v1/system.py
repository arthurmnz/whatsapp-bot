from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.agent.llm_factory import get_llm_status_summary
from app.core.auth import require_permission, serialize_user_summary
from app.db.models import User
from app.db.repositories.user_repo import user_has_permission
from app.db.session import get_db
from app.modules.devices_control import (
    get_windows_status,
    restart_windows,
    shutdown_windows,
    wake_windows,
)
from app.modules.jobs_career.models import (
    JobApplication,
    JobMatch,
    Resume,
    TailoredResume,
)
from app.modules.jobs_career.profile_service import get_or_create_profile

router = APIRouter(prefix="/api/v1/system", tags=["system"])

_DEVICE_ACTIONS = {
    "status": ("cmd:status_windows", "get_windows_status"),
    "wake": ("cmd:wake_windows", "wake_windows"),
    "restart": ("cmd:restart_windows", "restart_windows"),
    "shutdown": ("cmd:shutdown_windows", "shutdown_windows"),
}


@router.get("/overview")
async def get_system_overview(
    user: User = Depends(require_permission("web:access")),
    db: Session = Depends(get_db),
):
    profile = get_or_create_profile(db, user.id)
    skills_count = len(profile.skills or [])
    resumes_count = db.query(Resume).filter(Resume.user_id == user.id).count()
    tailored_count = db.query(TailoredResume).filter(TailoredResume.user_id == user.id).count()
    total_matches = db.query(JobMatch).filter(JobMatch.user_id == user.id).count()
    compatible_matches = (
        db.query(JobMatch)
        .filter(JobMatch.user_id == user.id, JobMatch.match_score >= 70)
        .count()
    )
    saved_jobs = (
        db.query(JobMatch)
        .filter(JobMatch.user_id == user.id, JobMatch.status == "saved")
        .count()
    )

    stage_rows = (
        db.query(JobApplication.stage, func.count(JobApplication.id))
        .filter(JobApplication.user_id == user.id)
        .group_by(JobApplication.stage)
        .all()
    )
    applications_by_stage = {stage: count for stage, count in stage_rows}
    active_apps = sum(
        count
        for stage, count in applications_by_stage.items()
        if stage not in {"rejected", "withdrawn"}
    )

    return {
        "user": serialize_user_summary(user),
        "profile_summary": {
            "headline": profile.headline or "",
            "years_experience": profile.years_experience or 0.0,
            "location": profile.location or "",
            "target_roles": (profile.preferences.target_roles if profile.preferences else []) or [],
        },
        "counts": {
            "skills": skills_count,
            "base_resumes": resumes_count,
            "tailored_resumes": tailored_count,
            "matched_jobs": total_matches,
            "compatible_jobs": compatible_matches,
            "saved_jobs": saved_jobs,
            "active_applications": active_apps,
        },
        "applications_by_stage": applications_by_stage,
        "llm": get_llm_status_summary(),
    }


@router.post("/devices/{action}")
async def control_device(
    action: str,
    user: User = Depends(require_permission("web:access")),
):
    action_key = action.strip().lower()
    entry = _DEVICE_ACTIONS.get(action_key)
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ação de dispositivo desconhecida: {action}. Use: status, wake, restart ou shutdown.",
        )

    required_perm, fn_name = entry
    if not user_has_permission(user, required_perm):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Acesso negado. Permissão necessária: {required_perm}",
        )

    fn = globals()[fn_name]
    result = await fn()
    return {
        "action": action_key,
        "result": result,
    }
