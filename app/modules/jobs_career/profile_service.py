from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.modules.jobs_career.models import CandidateProfile, CandidateSkill, JobPreference
from app.modules.jobs_career.skills_taxonomy import (
    display_skill_name,
    infer_skill_category,
    normalize_languages_list,
    normalize_skill_name,
)


def get_or_create_profile(db: Session, user_id: int) -> CandidateProfile:
    """Garante que o usuário possua um perfil de candidato e preferências de mercado."""
    profile = (
        db.query(CandidateProfile)
        .filter(CandidateProfile.user_id == user_id)
        .first()
    )
    created = False
    if profile is None:
        profile = CandidateProfile(
            user_id=user_id,
            years_experience=0.0,
            languages=[],
        )
        db.add(profile)
        db.flush()
        created = True

    if profile.preferences is None:
        pref = JobPreference(
            profile_id=profile.id,
            target_roles=[],
            seniority_levels=[],
            work_models=["remote"],
            contract_types=[],
            salary_currency="BRL",
            desired_stack=[],
            dealbreakers=[],
            target_companies=[],
            preferred_language="auto",
            auto_search_enabled=False,
            min_notify_score=70,
        )
        db.add(pref)
        created = True

    if created:
        db.commit()
        db.refresh(profile)
    return profile


def serialize_profile(profile: CandidateProfile) -> dict[str, Any]:
    pref = profile.preferences
    return {
        "id": profile.id,
        "user_id": profile.user_id,
        "headline": profile.headline or "",
        "summary": profile.summary or "",
        "years_experience": profile.years_experience or 0.0,
        "location": profile.location or "",
        "linkedin_url": profile.linkedin_url or "",
        "github_url": profile.github_url or "",
        "portfolio_url": profile.portfolio_url or "",
        "languages": normalize_languages_list(profile.languages),
        "skills": [
            {
                "id": sk.id,
                "name": sk.name,
                "normalized_name": sk.normalized_name,
                "category": sk.category or "other",
                "proficiency": sk.proficiency or "intermediate",
                "years_used": sk.years_used,
                "is_core": bool(sk.is_core),
            }
            for sk in (profile.skills or [])
        ],
        "preferences": {
            "target_roles": (pref.target_roles if pref else []) or [],
            "seniority_levels": (pref.seniority_levels if pref else []) or [],
            "work_models": (pref.work_models if pref else []) or [],
            "contract_types": (pref.contract_types if pref else []) or [],
            "min_salary": pref.min_salary if pref else None,
            "salary_currency": (pref.salary_currency if pref else "BRL") or "BRL",
            "desired_stack": (pref.desired_stack if pref else []) or [],
            "dealbreakers": (pref.dealbreakers if pref else []) or [],
            "target_companies": (pref.target_companies if pref else []) or [],
            "preferred_language": (pref.preferred_language if pref else "auto") or "auto",
            "auto_search_enabled": bool(pref.auto_search_enabled) if pref else False,
            "min_notify_score": pref.min_notify_score if pref else 70,
        },
        "updated_at": profile.updated_at.isoformat() if profile.updated_at else None,
    }


def _replace_skills(db: Session, profile: CandidateProfile, raw_skills: list[Any]) -> None:
    db.query(CandidateSkill).filter(CandidateSkill.profile_id == profile.id).delete()
    seen: set[str] = set()
    for item in raw_skills:
        if isinstance(item, str):
            raw_name = item.strip()
            category = None
            proficiency = "intermediate"
            years_used = None
            is_core = False
        elif isinstance(item, dict):
            raw_name = str(item.get("name") or "").strip()
            category = item.get("category")
            proficiency = item.get("proficiency") or "intermediate"
            years_used = item.get("years_used")
            is_core = bool(item.get("is_core", False))
        else:
            continue

        norm = normalize_skill_name(raw_name)
        if not norm or norm in seen:
            continue
        seen.add(norm)
        db.add(
            CandidateSkill(
                profile_id=profile.id,
                name=display_skill_name(raw_name),
                normalized_name=norm,
                category=category or infer_skill_category(norm),
                proficiency=proficiency,
                years_used=float(years_used) if years_used is not None else None,
                is_core=is_core,
            )
        )


def upsert_skills_from_names(
    db: Session,
    user_id: int,
    skill_names: list[str],
    is_core: bool = False,
) -> list[CandidateSkill]:
    """Adiciona novas skills ao perfil sem apagar as existentes."""
    profile = get_or_create_profile(db, user_id)
    existing_norms = {sk.normalized_name for sk in (profile.skills or [])}
    added: list[CandidateSkill] = []
    for raw in skill_names:
        norm = normalize_skill_name(raw)
        if not norm or norm in existing_norms:
            continue
        existing_norms.add(norm)
        skill = CandidateSkill(
            profile_id=profile.id,
            name=display_skill_name(raw),
            normalized_name=norm,
            category=infer_skill_category(norm),
            proficiency="intermediate",
            is_core=is_core,
        )
        db.add(skill)
        added.append(skill)
    profile.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(profile)
    return added


def update_profile_payload(db: Session, user_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    """Atualiza campos do perfil, lista de skills e preferências de mercado."""
    profile = get_or_create_profile(db, user_id)

    for field in (
        "headline",
        "summary",
        "location",
        "linkedin_url",
        "github_url",
        "portfolio_url",
    ):
        if field in payload and payload[field] is not None:
            setattr(profile, field, str(payload[field]).strip())

    if "years_experience" in payload and payload["years_experience"] is not None:
        profile.years_experience = max(0.0, float(payload["years_experience"]))

    if "languages" in payload and isinstance(payload["languages"], list):
        profile.languages = normalize_languages_list(payload["languages"])

    if "skills" in payload and isinstance(payload["skills"], list):
        _replace_skills(db, profile, payload["skills"])

    pref_data = payload.get("preferences")
    if isinstance(pref_data, dict):
        update_preferences_payload(db, profile, pref_data, commit=False)

    profile.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(profile)
    return serialize_profile(profile)


def update_preferences_payload(
    db: Session,
    profile: CandidateProfile,
    pref_data: dict[str, Any],
    commit: bool = True,
) -> JobPreference:
    pref = profile.preferences
    if pref is None:
        pref = JobPreference(profile_id=profile.id)
        db.add(pref)
        db.flush()

    list_fields = (
        "target_roles",
        "seniority_levels",
        "work_models",
        "contract_types",
        "desired_stack",
        "dealbreakers",
        "target_companies",
    )
    for field in list_fields:
        if field in pref_data and isinstance(pref_data[field], list):
            cleaned = [str(v).strip() for v in pref_data[field] if str(v).strip()]
            setattr(pref, field, cleaned)

    if "min_salary" in pref_data:
        val = pref_data["min_salary"]
        pref.min_salary = float(val) if val is not None and val != "" else None

    if "salary_currency" in pref_data and pref_data["salary_currency"]:
        pref.salary_currency = str(pref_data["salary_currency"]).strip().upper()[:10]

    if "preferred_language" in pref_data and pref_data["preferred_language"] in {"auto", "pt-BR", "en"}:
        pref.preferred_language = pref_data["preferred_language"]

    if "auto_search_enabled" in pref_data:
        pref.auto_search_enabled = bool(pref_data["auto_search_enabled"])

    if "min_notify_score" in pref_data and pref_data["min_notify_score"] is not None:
        pref.min_notify_score = max(0, min(100, int(pref_data["min_notify_score"])))

    pref.updated_at = datetime.now(timezone.utc)
    if commit:
        db.commit()
        db.refresh(profile)
    return pref


def sync_profile_from_structured_cv(
    db: Session,
    user_id: int,
    structured_data: dict[str, Any],
    overwrite_summary: bool = False,
) -> dict[str, Any]:
    """Sincroniza skills e dados básicos extraídos de um currículo para o perfil do usuário."""
    profile = get_or_create_profile(db, user_id)
    contact = structured_data.get("contact") or {}

    if (not profile.headline or overwrite_summary) and structured_data.get("headline"):
        profile.headline = str(structured_data["headline"])[:255]
    if (not profile.summary or overwrite_summary) and structured_data.get("summary"):
        profile.summary = str(structured_data["summary"])
    if not profile.location and contact.get("location"):
        profile.location = str(contact["location"])[:255]
    if not profile.linkedin_url and contact.get("linkedin"):
        profile.linkedin_url = str(contact["linkedin"])[:500]
    if not profile.github_url and contact.get("github"):
        profile.github_url = str(contact["github"])[:500]
    if not profile.portfolio_url and contact.get("portfolio"):
        profile.portfolio_url = str(contact["portfolio"])[:500]
    if not profile.languages and structured_data.get("languages"):
        profile.languages = normalize_languages_list(structured_data["languages"])

    raw_skills = structured_data.get("skills") or []
    upsert_skills_from_names(db, user_id, [str(s) for s in raw_skills])
    db.refresh(profile)
    return serialize_profile(profile)
