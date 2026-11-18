from datetime import datetime, timezone
import os
from pathlib import Path
import re
import shutil
from typing import Any
import uuid

from sqlalchemy.orm import Session

from app.modules.jobs_career.cv_parser import (
    extract_text_from_bytes,
    parse_cv_structured,
    validate_cv_upload,
)
from app.modules.jobs_career.cv_renderer import (
    get_user_cv_dir,
    render_cv_docx,
    render_cv_markdown,
    render_cv_pdf,
    render_markdown_to_docx,
    render_markdown_to_pdf,
    resolve_safe_cv_path,
)
from app.modules.jobs_career.cv_tailor import evaluate_and_tailor_cv
from app.modules.jobs_career.models import JobApplication, JobMatch, JobPosting, Resume, TailoredResume
from app.modules.jobs_career.profile_service import (
    get_or_create_profile,
    sync_profile_from_structured_cv,
)
from app.modules.jobs_career.skills_taxonomy import detect_language


def _get_uploaded_user_dir(user_id: int) -> Path:
    raw = os.environ.get("UPLOADED_CVS_DIR", "data/uploaded_cvs").strip() or "data/uploaded_cvs"
    base = Path(raw).resolve()
    base.mkdir(parents=True, exist_ok=True)
    user_dir = (base / f"user_{int(user_id)}").resolve()
    if not user_dir.is_relative_to(base):
        raise ValueError("Caminho inválido para diretório de uploads.")
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir


def _sanitize_slug(raw: str, fallback: str = "cv") -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "-", (raw or "").strip().lower()).strip("-")
    return cleaned[:48] or fallback


def serialize_resume(resume: Resume) -> dict[str, Any]:
    return {
        "id": resume.id,
        "user_id": resume.user_id,
        "title": resume.title,
        "language": resume.language,
        "is_default": bool(resume.is_default),
        "source_format": resume.source_format,
        "has_file": bool(resume.file_path),
        "raw_text": resume.raw_text,
        "structured_data": resume.structured_data or {},
        "created_at": resume.created_at.isoformat() if resume.created_at else None,
        "updated_at": resume.updated_at.isoformat() if resume.updated_at else None,
    }


def serialize_tailored_resume(item: TailoredResume) -> dict[str, Any]:
    return {
        "id": item.id,
        "user_id": item.user_id,
        "base_resume_id": item.base_resume_id,
        "job_id": item.job_id,
        "job_title": item.job_title or "",
        "company_name": item.company_name or "",
        "job_description_snapshot": item.job_description_snapshot,
        "target_language": item.target_language,
        "ats_score_before": item.ats_score_before,
        "ats_score_after": item.ats_score_after,
        "evaluation_report": item.evaluation_report or {},
        "changes_summary": item.changes_summary or [],
        "tailored_data": item.tailored_data or {},
        "tailored_markdown": item.tailored_markdown,
        "has_pdf": bool(item.pdf_path and os.path.exists(item.pdf_path)),
        "has_docx": bool(item.docx_path and os.path.exists(item.docx_path)),
        "cover_letter": item.cover_letter or "",
        "interview_prep": item.interview_prep or {},
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }


async def create_resume_from_upload(
    db: Session,
    user_id: int,
    *,
    filename: str | None = None,
    file_bytes: bytes | None = None,
    raw_text_input: str | None = None,
    title: str | None = None,
    language: str | None = None,
    is_default: bool = False,
    sync_profile: bool = True,
) -> Resume:
    """Processa upload (PDF/DOCX/MD/TXT) ou texto puro, estrutura o CV e opcionalmente sincroniza perfil."""
    saved_path: str | None = None
    if file_bytes is not None:
        safe_filename = Path(filename or "curriculo.txt").name
        source_format = validate_cv_upload(safe_filename, file_bytes)
        raw_text = extract_text_from_bytes(file_bytes, source_format)
        ext = Path(safe_filename).suffix.lower() or f".{source_format}"
        dest = _get_uploaded_user_dir(user_id) / f"{uuid.uuid4().hex[:12]}_{_sanitize_slug(Path(safe_filename).stem)}{ext}"
        dest.write_bytes(file_bytes)
        saved_path = str(dest)
    elif raw_text_input and raw_text_input.strip():
        raw_text = raw_text_input.strip()
        source_format = "markdown" if raw_text.lstrip().startswith("#") else "text"
    else:
        raise ValueError("Envie um arquivo (PDF/DOCX/MD/TXT) ou informe o texto do currículo.")

    resolved_lang = language if language in {"pt-BR", "en"} else detect_language(raw_text)
    structured = await parse_cv_structured(raw_text, target_language=resolved_lang)

    existing_count = db.query(Resume).filter(Resume.user_id == user_id).count()
    should_be_default = is_default or existing_count == 0
    if should_be_default:
        db.query(Resume).filter(Resume.user_id == user_id).update({"is_default": False})

    effective_title = (title or "").strip() or (Path(filename).stem if filename else f"Currículo {resolved_lang}")
    now = datetime.now(timezone.utc)
    resume = Resume(
        user_id=user_id,
        title=effective_title[:255],
        language=resolved_lang,
        is_default=should_be_default,
        source_format=source_format,
        file_path=saved_path,
        raw_text=raw_text,
        structured_data=structured,
        created_at=now,
        updated_at=now,
    )
    db.add(resume)
    db.commit()
    db.refresh(resume)

    if sync_profile:
        sync_profile_from_structured_cv(db, user_id, structured, overwrite_summary=False)

    return resume


def set_default_resume(db: Session, user_id: int, resume_id: int) -> Resume:
    resume = db.query(Resume).filter(Resume.id == resume_id, Resume.user_id == user_id).first()
    if resume is None:
        raise ValueError("Currículo não encontrado.")
    db.query(Resume).filter(Resume.user_id == user_id).update({"is_default": False})
    resume.is_default = True
    resume.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(resume)
    return resume


async def tailor_resume_for_job(
    db: Session,
    user_id: int,
    *,
    base_resume_id: int | None = None,
    resume_text_override: str | None = None,
    job_id: int | None = None,
    job_description: str | None = None,
    job_title: str | None = None,
    company_name: str | None = None,
    target_language: str = "auto",
) -> TailoredResume:
    """Executa avaliação ATS + adaptação anti-alucinação + geração de PDF/DOCX/MD."""
    base_resume: Resume | None = None
    if base_resume_id is not None:
        base_resume = db.query(Resume).filter(Resume.id == base_resume_id, Resume.user_id == user_id).first()
        if base_resume is None:
            raise ValueError("Currículo base informado não foi encontrado.")
    else:
        base_resume = (
            db.query(Resume)
            .filter(Resume.user_id == user_id)
            .order_by(Resume.is_default.desc(), Resume.updated_at.desc())
            .first()
        )

    profile = get_or_create_profile(db, user_id)
    cand_skills = [sk.name for sk in (profile.skills or [])]

    if resume_text_override and resume_text_override.strip():
        raw_cv_text = resume_text_override.strip()
        structured_cv = None
    elif base_resume is not None:
        raw_cv_text = base_resume.raw_text
        structured_cv = base_resume.structured_data
    else:
        # Constrói currículo sintético a partir dos dados reais do perfil
        skills_str = ", ".join(cand_skills) if cand_skills else "Python, SQL"
        raw_cv_text = (
            f"# {profile.headline or 'Profissional de Tecnologia'}\n"
            f"{profile.summary or ''}\n\n"
            f"## Competências Técnicas\n{skills_str}\n"
        ).strip()
        structured_cv = {
            "contact": {
                "name": "",
                "location": profile.location or "",
                "linkedin": profile.linkedin_url or "",
                "github": profile.github_url or "",
                "portfolio": profile.portfolio_url or "",
            },
            "headline": profile.headline or "",
            "summary": profile.summary or "",
            "skills": cand_skills,
            "experiences": [],
            "education": [],
            "projects": [],
            "certifications": [],
            "languages": profile.languages or [],
        }

    resolved_job_desc = (job_description or "").strip()
    resolved_title = (job_title or "").strip()
    resolved_company = (company_name or "").strip()

    if job_id is not None:
        posting = db.query(JobPosting).filter(JobPosting.id == job_id).first()
        if posting is None:
            raise ValueError("Vaga informada não encontrada.")
        if posting.source == "manual":
            has_match = (
                db.query(JobMatch)
                .filter(JobMatch.user_id == user_id, JobMatch.job_id == posting.id)
                .first()
            )
            if has_match is None:
                raise ValueError("Vaga informada não encontrada.")
        resolved_job_desc = resolved_job_desc or posting.description_raw
        resolved_title = resolved_title or posting.title
        resolved_company = resolved_company or (posting.company_name or "")

    if not resolved_job_desc:
        raise ValueError("É necessário informar a descrição da vaga ou o ID de uma vaga salva.")

    result = await evaluate_and_tailor_cv(
        resume_text=raw_cv_text,
        structured_resume=structured_cv,
        job_description=resolved_job_desc,
        job_title=resolved_title or None,
        company_name=resolved_company or None,
        target_language=target_language,
        candidate_skills=cand_skills,
    )

    now = datetime.now(timezone.utc)
    tailored = TailoredResume(
        user_id=user_id,
        base_resume_id=base_resume.id if base_resume else None,
        job_id=job_id,
        job_title=resolved_title or "Vaga Analisada",
        company_name=resolved_company or None,
        job_description_snapshot=resolved_job_desc,
        target_language=result["target_language"],
        ats_score_before=result["ats_score_before"],
        ats_score_after=result["ats_score_after"],
        evaluation_report=result["evaluation_report"],
        changes_summary=result["changes_summary"],
        tailored_data=result["tailored_data"],
        tailored_markdown=result["tailored_markdown"],
        cover_letter=result["cover_letter"],
        interview_prep=result["interview_prep"],
        created_at=now,
        updated_at=now,
    )
    db.add(tailored)
    db.flush()

    user_dir = get_user_cv_dir(user_id)
    slug = _sanitize_slug(f"{tailored.id}_{resolved_company}_{resolved_title}", fallback=f"cv_{tailored.id}")
    pdf_path = user_dir / f"{slug}.pdf"
    docx_path = user_dir / f"{slug}.docx"

    render_cv_pdf(result["tailored_data"], pdf_path, target_language=result["target_language"])
    render_cv_docx(result["tailored_data"], docx_path, target_language=result["target_language"])

    tailored.pdf_path = str(pdf_path)
    tailored.docx_path = str(docx_path)
    db.commit()
    db.refresh(tailored)
    return tailored


def regenerate_tailored_files(
    db: Session,
    user_id: int,
    tailored: TailoredResume,
    *,
    tailored_markdown: str | None = None,
    tailored_data: dict[str, Any] | None = None,
    target_language: str | None = None,
) -> TailoredResume:
    """Atualiza markdown/dados editados manualmente e regera PDF e DOCX."""
    lang = target_language if target_language in {"pt-BR", "en"} else tailored.target_language
    tailored.target_language = lang

    user_dir = get_user_cv_dir(user_id)
    slug = _sanitize_slug(
        f"{tailored.id}_{tailored.company_name or ''}_{tailored.job_title or ''}",
        fallback=f"cv_{tailored.id}",
    )
    pdf_path = resolve_safe_cv_path(user_id, tailored.pdf_path) if tailored.pdf_path else (user_dir / f"{slug}.pdf")
    docx_path = resolve_safe_cv_path(user_id, tailored.docx_path) if tailored.docx_path else (user_dir / f"{slug}.docx")

    if isinstance(tailored_data, dict):
        tailored.tailored_data = tailored_data
        if tailored_markdown is None:
            tailored.tailored_markdown = render_cv_markdown(tailored_data, target_language=lang)
        else:
            tailored.tailored_markdown = tailored_markdown
        render_cv_pdf(tailored.tailored_data, pdf_path, target_language=lang)
        render_cv_docx(tailored.tailored_data, docx_path, target_language=lang)
    elif tailored_markdown is not None:
        tailored.tailored_markdown = tailored_markdown
        render_markdown_to_pdf(tailored_markdown, pdf_path)
        render_markdown_to_docx(tailored_markdown, docx_path)

    tailored.pdf_path = str(pdf_path)
    tailored.docx_path = str(docx_path)
    tailored.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(tailored)
    return tailored


def delete_resume_with_file(db: Session, user_id: int, resume: Resume) -> None:
    """Remove registro do currículo e apaga o arquivo físico enviado com validação de diretório."""
    if resume.file_path:
        try:
            user_dir = _get_uploaded_user_dir(user_id)
            candidate = Path(resume.file_path).resolve()
            if candidate.is_relative_to(user_dir) and candidate.is_file():
                candidate.unlink(missing_ok=True)
        except Exception:
            pass
    db.delete(resume)
    db.commit()


def delete_tailored_resume_with_files(db: Session, user_id: int, tailored: TailoredResume) -> None:
    """Desvincula candidaturas, apaga arquivos PDF/DOCX seguros e exclui o TailoredResume."""
    db.query(JobApplication).filter(
        JobApplication.tailored_resume_id == tailored.id,
        JobApplication.user_id == user_id,
    ).update({"tailored_resume_id": None})

    for raw_path in (tailored.pdf_path, tailored.docx_path):
        if not raw_path:
            continue
        try:
            safe_path = resolve_safe_cv_path(user_id, raw_path)
            if safe_path.is_file():
                safe_path.unlink(missing_ok=True)
        except Exception:
            pass

    db.delete(tailored)
    db.commit()


def save_tailored_as_base_resume(
    db: Session,
    user_id: int,
    tailored: TailoredResume,
    *,
    title: str | None = None,
    is_default: bool = False,
    sync_profile: bool = False,
) -> Resume:
    """Promove um currículo otimizado para um currículo base permanente do usuário."""
    effective_title = (title or "").strip() or (
        f"CV Otimizado - {tailored.job_title or 'Vaga'}"
        + (f" ({tailored.company_name})" if tailored.company_name else "")
    )

    saved_file_path: str | None = None
    if tailored.pdf_path:
        try:
            src_pdf = resolve_safe_cv_path(user_id, tailored.pdf_path)
            if src_pdf.is_file():
                dest = _get_uploaded_user_dir(user_id) / f"{uuid.uuid4().hex[:12]}_{_sanitize_slug(effective_title)}.pdf"
                shutil.copy2(src_pdf, dest)
                saved_file_path = str(dest)
        except Exception:
            saved_file_path = None

    if is_default:
        db.query(Resume).filter(Resume.user_id == user_id).update({"is_default": False})

    now = datetime.now(timezone.utc)
    new_resume = Resume(
        user_id=user_id,
        title=effective_title[:255],
        language=tailored.target_language or "pt-BR",
        is_default=is_default,
        source_format="markdown",
        file_path=saved_file_path,
        raw_text=tailored.tailored_markdown,
        structured_data=tailored.tailored_data or {},
        created_at=now,
        updated_at=now,
    )
    db.add(new_resume)
    db.commit()
    db.refresh(new_resume)

    if sync_profile and isinstance(new_resume.structured_data, dict):
        sync_profile_from_structured_cv(db, user_id, new_resume.structured_data, overwrite_summary=False)

    return new_resume
