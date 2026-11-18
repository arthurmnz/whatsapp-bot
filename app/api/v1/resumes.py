import os
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.auth import require_permission
from app.db.models import User
from app.db.session import get_db
from app.modules.jobs_career.cv_parser import MAX_CV_FILE_SIZE
from app.modules.jobs_career.cv_renderer import resolve_safe_cv_path
from app.modules.jobs_career.models import Resume, TailoredResume
from app.modules.jobs_career.resume_service import (
    create_resume_from_upload,
    delete_resume_with_file,
    delete_tailored_resume_with_files,
    save_tailored_as_base_resume,
    regenerate_tailored_files,
    serialize_resume,
    serialize_tailored_resume,
    set_default_resume,
    tailor_resume_for_job,
)
from app.modules.jobs_career.sources import JobUrlBlockedError, ingest_job_from_url, upsert_job_and_match

router = APIRouter(prefix="/api/v1/resumes", tags=["resumes"])


class TailorResumeBody(BaseModel):
    base_resume_id: int | None = None
    resume_text: str | None = None
    job_id: int | None = None
    job_url: str | None = None
    job_description: str | None = None
    job_title: str | None = None
    company_name: str | None = None
    target_language: str = "auto"


class UpdateTailoredResumeBody(BaseModel):
    tailored_markdown: str | None = None
    tailored_data: dict[str, Any] | None = None
    target_language: str | None = None
    cover_letter: str | None = None


class SaveTailoredAsBaseBody(BaseModel):
    title: str | None = None
    is_default: bool = False
    sync_profile: bool = False


@router.get("")
async def list_resumes(
    user: User = Depends(require_permission("jobs:cv_tailor")),
    db: Session = Depends(get_db),
):
    items = (
        db.query(Resume)
        .filter(Resume.user_id == user.id)
        .order_by(Resume.is_default.desc(), Resume.updated_at.desc())
        .all()
    )
    return {"items": [serialize_resume(r) for r in items]}


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_resume(
    file: UploadFile | None = File(default=None),
    raw_text: str | None = Form(default=None),
    title: str | None = Form(default=None),
    language: str | None = Form(default=None),
    is_default: bool = Form(default=False),
    sync_profile: bool = Form(default=True),
    user: User = Depends(require_permission("jobs:cv_tailor")),
    db: Session = Depends(get_db),
):
    file_bytes: bytes | None = None
    filename: str | None = None
    if file is not None:
        filename = file.filename
        file_bytes = await file.read(MAX_CV_FILE_SIZE + 1)

    try:
        resume = await create_resume_from_upload(
            db,
            user.id,
            filename=filename,
            file_bytes=file_bytes,
            raw_text_input=raw_text,
            title=title,
            language=language,
            is_default=is_default,
            sync_profile=sync_profile,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return serialize_resume(resume)


@router.post("/tailor", status_code=status.HTTP_201_CREATED)
async def tailor_resume(
    body: TailorResumeBody,
    user: User = Depends(require_permission("jobs:cv_tailor")),
    db: Session = Depends(get_db),
):
    resolved_job_id = body.job_id
    resolved_desc = body.job_description
    resolved_title = body.job_title
    resolved_company = body.company_name

    if body.job_url and not (resolved_desc and resolved_desc.strip()):
        try:
            norm_job = await ingest_job_from_url(
                body.job_url,
                title_override=body.job_title,
                company_override=body.company_name,
            )
            posting, _ = upsert_job_and_match(db, user.id, norm_job, default_status="saved")
            db.commit()
            resolved_job_id = posting.id
            resolved_desc = posting.description_raw
            resolved_title = resolved_title or posting.title
            resolved_company = resolved_company or posting.company_name
        except JobUrlBlockedError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    try:
        tailored = await tailor_resume_for_job(
            db,
            user.id,
            base_resume_id=body.base_resume_id,
            resume_text_override=body.resume_text,
            job_id=resolved_job_id,
            job_description=resolved_desc,
            job_title=resolved_title,
            company_name=resolved_company,
            target_language=body.target_language,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return serialize_tailored_resume(tailored)


@router.get("/tailored")
async def list_tailored_resumes(
    user: User = Depends(require_permission("jobs:cv_tailor")),
    db: Session = Depends(get_db),
):
    items = (
        db.query(TailoredResume)
        .filter(TailoredResume.user_id == user.id)
        .order_by(TailoredResume.created_at.desc())
        .all()
    )
    return {"items": [serialize_tailored_resume(t) for t in items]}


@router.get("/tailored/{tailored_id}")
async def get_tailored_resume(
    tailored_id: int,
    user: User = Depends(require_permission("jobs:cv_tailor")),
    db: Session = Depends(get_db),
):
    item = (
        db.query(TailoredResume)
        .filter(TailoredResume.id == tailored_id, TailoredResume.user_id == user.id)
        .first()
    )
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Currículo otimizado não encontrado.")
    return serialize_tailored_resume(item)


@router.patch("/tailored/{tailored_id}")
async def update_tailored_resume(
    tailored_id: int,
    body: UpdateTailoredResumeBody,
    user: User = Depends(require_permission("jobs:cv_tailor")),
    db: Session = Depends(get_db),
):
    item = (
        db.query(TailoredResume)
        .filter(TailoredResume.id == tailored_id, TailoredResume.user_id == user.id)
        .first()
    )
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Currículo otimizado não encontrado.")

    if body.cover_letter is not None:
        item.cover_letter = body.cover_letter

    updated = regenerate_tailored_files(
        db,
        user.id,
        item,
        tailored_markdown=body.tailored_markdown,
        tailored_data=body.tailored_data,
        target_language=body.target_language,
    )
    return serialize_tailored_resume(updated)


@router.get("/tailored/{tailored_id}/download")
async def download_tailored_resume(
    tailored_id: int,
    format: str = Query(default="pdf", pattern="^(pdf|docx|md)$"),
    user: User = Depends(require_permission("jobs:cv_tailor")),
    db: Session = Depends(get_db),
):
    item = (
        db.query(TailoredResume)
        .filter(TailoredResume.id == tailored_id, TailoredResume.user_id == user.id)
        .first()
    )
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Currículo otimizado não encontrado.")

    if format == "md":
        filename = f"cv_otimizado_{item.id}_{item.target_language}.md"
        return Response(
            content=item.tailored_markdown or "",
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    raw_path = item.pdf_path if format == "pdf" else item.docx_path
    if not raw_path or not os.path.exists(raw_path):
        item = regenerate_tailored_files(
            db,
            user.id,
            item,
            tailored_markdown=item.tailored_markdown,
            tailored_data=item.tailored_data,
            target_language=item.target_language,
        )
        raw_path = item.pdf_path if format == "pdf" else item.docx_path

    if not raw_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Arquivo ainda não disponível.")

    try:
        safe_path = resolve_safe_cv_path(user.id, raw_path)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    if not safe_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Arquivo não encontrado no disco.")

    media_type = (
        "application/pdf"
        if format == "pdf"
        else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    return FileResponse(
        path=str(safe_path),
        media_type=media_type,
        filename=f"cv_otimizado_{item.id}_{item.target_language}.{format}",
    )


@router.delete("/tailored/{tailored_id}")
async def delete_tailored_resume(
    tailored_id: int,
    user: User = Depends(require_permission("jobs:cv_tailor")),
    db: Session = Depends(get_db),
):
    item = (
        db.query(TailoredResume)
        .filter(TailoredResume.id == tailored_id, TailoredResume.user_id == user.id)
        .first()
    )
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Currículo otimizado não encontrado.")
    delete_tailored_resume_with_files(db, user.id, item)
    return {"status": "deleted", "id": tailored_id}


@router.post("/tailored/{tailored_id}/save-as-base", status_code=status.HTTP_201_CREATED)
async def save_tailored_resume_as_base(
    tailored_id: int,
    body: SaveTailoredAsBaseBody | None = None,
    user: User = Depends(require_permission("jobs:cv_tailor")),
    db: Session = Depends(get_db),
):
    item = (
        db.query(TailoredResume)
        .filter(TailoredResume.id == tailored_id, TailoredResume.user_id == user.id)
        .first()
    )
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Currículo otimizado não encontrado.")
    cfg = body or SaveTailoredAsBaseBody()
    new_resume = save_tailored_as_base_resume(
        db,
        user.id,
        item,
        title=cfg.title,
        is_default=cfg.is_default,
        sync_profile=cfg.sync_profile,
    )
    return serialize_resume(new_resume)


@router.patch("/{resume_id}/default")
async def mark_resume_default(
    resume_id: int,
    user: User = Depends(require_permission("jobs:cv_tailor")),
    db: Session = Depends(get_db),
):
    try:
        resume = set_default_resume(db, user.id, resume_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return serialize_resume(resume)


@router.delete("/{resume_id}")
async def delete_resume(
    resume_id: int,
    user: User = Depends(require_permission("jobs:cv_tailor")),
    db: Session = Depends(get_db),
):
    resume = db.query(Resume).filter(Resume.id == resume_id, Resume.user_id == user.id).first()
    if resume is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Currículo não encontrado.")
    delete_resume_with_file(db, user.id, resume)
    return {"status": "deleted", "id": resume_id}
