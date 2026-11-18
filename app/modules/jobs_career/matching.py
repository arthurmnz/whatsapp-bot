from dataclasses import dataclass
from typing import Any

from app.modules.jobs_career.skills_taxonomy import (
    display_skill_name,
    extract_job_requirements,
    normalize_skill_name,
)

_SENIORITY_RANK = {
    "intern": 0,
    "junior": 1,
    "mid": 2,
    "pleno": 2,
    "senior": 3,
    "sênior": 3,
    "lead": 4,
    "staff": 4,
}


@dataclass
class MatchEvaluation:
    match_score: int
    score_breakdown: dict[str, int]
    matched_skills: list[str]
    missing_skills: list[str]
    ai_rationale: str


def _infer_candidate_seniority(years_exp: float, levels: list[str]) -> list[int]:
    ranks: list[int] = []
    for lv in levels:
        low = lv.lower().strip()
        if low in _SENIORITY_RANK:
            ranks.append(_SENIORITY_RANK[low])
    if ranks:
        return ranks
    if years_exp <= 1.5:
        return [1]
    if years_exp <= 4.5:
        return [2]
    if years_exp <= 8.0:
        return [3]
    return [3, 4]


def calculate_job_match(
    profile: Any,
    skills: list[Any],
    preferences: Any,
    job_posting: Any,
) -> MatchEvaluation:
    """Calcula compatibilidade 0-100 entre perfil/vontades do candidato e uma vaga."""
    reqs = getattr(job_posting, "extracted_requirements", None) or {}
    if not reqs or not reqs.get("keywords_ats"):
        reqs = extract_job_requirements(
            getattr(job_posting, "description_raw", "") or "",
            getattr(job_posting, "title", "") or "",
        )

    must_have = [normalize_skill_name(s) for s in (reqs.get("must_have") or []) if normalize_skill_name(s)]
    nice_to_have = [normalize_skill_name(s) for s in (reqs.get("nice_to_have") or []) if normalize_skill_name(s)]
    all_job_skills = list(dict.fromkeys(must_have + nice_to_have))

    cand_skills_map: dict[str, bool] = {}
    for sk in skills or []:
        norm = getattr(sk, "normalized_name", None) or normalize_skill_name(getattr(sk, "name", "") or str(sk))
        if norm:
            cand_skills_map[norm] = bool(getattr(sk, "is_core", False))

    # Também considera desired_stack se não estiver em skills? Não para match real, apenas para bônus
    matched_norms = [s for s in all_job_skills if s in cand_skills_map]
    missing_norms = [s for s in all_job_skills if s not in cand_skills_map]

    # 1. Skills match (0-50)
    if all_job_skills:
        must_set = set(must_have)
        weighted_hits = 0.0
        weighted_total = 0.0
        for s in all_job_skills:
            weight = 1.5 if s in must_set else 1.0
            weighted_total += weight
            if s in cand_skills_map:
                core_boost = 1.1 if cand_skills_map[s] else 1.0
                weighted_hits += min(weight * 1.05, weight * core_boost)
        skills_score = round(min(50.0, (weighted_hits / max(0.1, weighted_total)) * 50.0))
    else:
        skills_score = 30 if cand_skills_map else 15

    # 2. Preferences match (0-25): cargo alvo, modelo de trabalho, contrato, salário
    target_roles = [str(r).lower().strip() for r in (getattr(preferences, "target_roles", None) or []) if str(r).strip()]
    pref_models = [str(m).lower().strip() for m in (getattr(preferences, "work_models", None) or []) if str(m).strip()]
    pref_contracts = [str(c).lower().strip() for c in (getattr(preferences, "contract_types", None) or []) if str(c).strip()]
    min_salary = getattr(preferences, "min_salary", None)
    pref_currency = (getattr(preferences, "salary_currency", None) or "BRL").upper()

    pref_score = 0
    job_title_low = (getattr(job_posting, "title", "") or "").lower()
    if target_roles:
        if any(role in job_title_low or any(tok in job_title_low for tok in role.split() if len(tok) > 2) for role in target_roles):
            pref_score += 11
    else:
        pref_score += 7

    job_model = (getattr(job_posting, "work_model", "") or "unknown").lower()
    if pref_models:
        if job_model in pref_models or job_model == "unknown":
            pref_score += 7 if job_model in pref_models else 4
    else:
        pref_score += 5

    job_contract = (getattr(job_posting, "contract_type", "") or "unknown").lower()
    if pref_contracts:
        if any(c in job_contract for c in pref_contracts) or job_contract == "unknown":
            pref_score += 4 if any(c in job_contract for c in pref_contracts) else 2
    else:
        pref_score += 3

    job_sal_max = getattr(job_posting, "salary_max", None) or getattr(job_posting, "salary_min", None)
    job_curr = (getattr(job_posting, "salary_currency", None) or "").upper()
    if min_salary and job_sal_max and job_curr == pref_currency:
        if job_sal_max >= float(min_salary):
            pref_score += 3
    else:
        pref_score += 2
    pref_score = min(25, pref_score)

    # 3. Seniority match (0-15)
    job_sen = (getattr(job_posting, "seniority", "") or "unknown").lower()
    years_exp = float(getattr(profile, "years_experience", 0.0) or 0.0)
    pref_levels = list(getattr(preferences, "seniority_levels", None) or [])
    cand_ranks = _infer_candidate_seniority(years_exp, pref_levels)
    if job_sen in _SENIORITY_RANK:
        job_rank = _SENIORITY_RANK[job_sen]
        diff = min(abs(r - job_rank) for r in cand_ranks)
        seniority_score = 15 if diff == 0 else (10 if diff == 1 else 4)
    else:
        seniority_score = 11

    # 4. Desired stack bonus (0-10)
    desired_stack = [normalize_skill_name(s) for s in (getattr(preferences, "desired_stack", None) or []) if normalize_skill_name(s)]
    if desired_stack:
        desired_hits = sum(1 for ds in desired_stack if ds in all_job_skills)
        desired_bonus = round(min(10.0, (desired_hits / len(desired_stack)) * 10.0))
    else:
        desired_bonus = 5

    # 5. Dealbreakers penalty (0 to -50)
    dealbreakers = [str(d).lower().strip() for d in (getattr(preferences, "dealbreakers", None) or []) if str(d).strip()]
    job_text_low = f"{job_title_low} {(getattr(job_posting, 'company_name', '') or '').lower()} {(getattr(job_posting, 'location', '') or '').lower()} {(getattr(job_posting, 'description_raw', '') or '').lower()} {job_model}"
    triggered_dealbreakers: list[str] = []
    for db_item in dealbreakers:
        if db_item in {"presencial", "onsite", "on-site"} and job_model == "onsite":
            triggered_dealbreakers.append(db_item)
        elif db_item in {"hibrido", "híbrido", "hybrid"} and job_model == "hybrid":
            triggered_dealbreakers.append(db_item)
        elif db_item in job_text_low:
            triggered_dealbreakers.append(db_item)

    if min_salary and job_sal_max and job_curr == pref_currency and job_sal_max < float(min_salary) * 0.85:
        triggered_dealbreakers.append("salário abaixo do mínimo")

    dealbreaker_penalty = -min(50, len(triggered_dealbreakers) * 25)

    total_score = max(0, min(100, skills_score + pref_score + seniority_score + desired_bonus + dealbreaker_penalty))

    matched_display = [display_skill_name(s) for s in matched_norms]
    missing_display = [display_skill_name(s) for s in missing_norms]

    rationale_parts = []
    if matched_display:
        rationale_parts.append(f"Compatível com {', '.join(matched_display[:5])}")
    if missing_display:
        rationale_parts.append(f"Gaps: {', '.join(missing_display[:4])}")
    if triggered_dealbreakers:
        rationale_parts.append(f"Penalidade por dealbreaker ({', '.join(triggered_dealbreakers)})")
    if not rationale_parts:
        rationale_parts.append(f"Aderência geral calculada com score {total_score}/100")

    return MatchEvaluation(
        match_score=total_score,
        score_breakdown={
            "skills_match": skills_score,
            "preferences_match": pref_score,
            "seniority_match": seniority_score,
            "desired_stack_bonus": desired_bonus,
            "dealbreaker_penalty": dealbreaker_penalty,
        },
        matched_skills=matched_display,
        missing_skills=missing_display,
        ai_rationale=". ".join(rationale_parts) + ".",
    )
