from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.db.session import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CandidateProfile(Base):
    __tablename__ = "candidate_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    headline = Column(String(255), nullable=True)
    summary = Column(Text, nullable=True)
    years_experience = Column(Float, default=0.0, nullable=False)
    location = Column(String(255), nullable=True)
    linkedin_url = Column(String(500), nullable=True)
    github_url = Column(String(500), nullable=True)
    portfolio_url = Column(String(500), nullable=True)
    languages = Column(JSON, default=list, nullable=False)
    created_at = Column(DateTime, default=_utcnow, nullable=False)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)

    skills = relationship(
        "CandidateSkill",
        back_populates="profile",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    preferences = relationship(
        "JobPreference",
        back_populates="profile",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class CandidateSkill(Base):
    __tablename__ = "candidate_skills"

    id = Column(Integer, primary_key=True, index=True)
    profile_id = Column(
        Integer,
        ForeignKey("candidate_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = Column(String(120), nullable=False)
    normalized_name = Column(String(120), nullable=False, index=True)
    category = Column(String(80), nullable=True)
    proficiency = Column(String(50), nullable=True)
    years_used = Column(Float, nullable=True)
    is_core = Column(Boolean, default=False, nullable=False)

    profile = relationship("CandidateProfile", back_populates="skills")


class JobPreference(Base):
    __tablename__ = "job_preferences"

    id = Column(Integer, primary_key=True, index=True)
    profile_id = Column(
        Integer,
        ForeignKey("candidate_profiles.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    target_roles = Column(JSON, default=list, nullable=False)
    seniority_levels = Column(JSON, default=list, nullable=False)
    work_models = Column(JSON, default=list, nullable=False)
    contract_types = Column(JSON, default=list, nullable=False)
    min_salary = Column(Float, nullable=True)
    salary_currency = Column(String(10), default="BRL", nullable=False)
    desired_stack = Column(JSON, default=list, nullable=False)
    dealbreakers = Column(JSON, default=list, nullable=False)
    target_companies = Column(JSON, default=list, nullable=False)
    preferred_language = Column(String(16), default="auto", nullable=False)
    auto_search_enabled = Column(Boolean, default=False, nullable=False)
    min_notify_score = Column(Integer, default=70, nullable=False)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)

    profile = relationship("CandidateProfile", back_populates="preferences")


class Resume(Base):
    __tablename__ = "resumes"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title = Column(String(255), nullable=False)
    language = Column(String(16), default="pt-BR", nullable=False)
    is_default = Column(Boolean, default=False, nullable=False)
    source_format = Column(String(20), default="text", nullable=False)
    file_path = Column(String(500), nullable=True)
    raw_text = Column(Text, nullable=False)
    structured_data = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime, default=_utcnow, nullable=False)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)


class JobPosting(Base):
    __tablename__ = "job_postings"

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String(64), nullable=False, index=True)
    external_id = Column(String(255), nullable=True)
    source_url = Column(String(1000), nullable=True)
    dedupe_hash = Column(String(64), unique=True, index=True, nullable=False)
    title = Column(String(300), nullable=False)
    company_name = Column(String(255), nullable=True)
    location = Column(String(255), nullable=True)
    work_model = Column(String(50), nullable=True)
    contract_type = Column(String(50), nullable=True)
    seniority = Column(String(50), nullable=True)
    salary_min = Column(Float, nullable=True)
    salary_max = Column(Float, nullable=True)
    salary_currency = Column(String(10), nullable=True)
    language = Column(String(16), default="en", nullable=False)
    description_raw = Column(Text, nullable=False)
    extracted_requirements = Column(JSON, default=dict, nullable=False)
    posted_at = Column(DateTime, nullable=True)
    fetched_at = Column(DateTime, default=_utcnow, nullable=False)


class JobMatch(Base):
    __tablename__ = "job_matches"
    __table_args__ = (
        UniqueConstraint("user_id", "job_id", name="uq_job_matches_user_job"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    job_id = Column(
        Integer,
        ForeignKey("job_postings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    match_score = Column(Integer, default=0, nullable=False)
    score_breakdown = Column(JSON, default=dict, nullable=False)
    matched_skills = Column(JSON, default=list, nullable=False)
    missing_skills = Column(JSON, default=list, nullable=False)
    ai_rationale = Column(Text, nullable=True)
    status = Column(String(32), default="new", nullable=False)
    notified_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_utcnow, nullable=False)

    job = relationship("JobPosting", lazy="joined")


class TailoredResume(Base):
    __tablename__ = "tailored_resumes"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    base_resume_id = Column(
        Integer,
        ForeignKey("resumes.id", ondelete="SET NULL"),
        nullable=True,
    )
    job_id = Column(
        Integer,
        ForeignKey("job_postings.id", ondelete="SET NULL"),
        nullable=True,
    )
    job_title = Column(String(300), nullable=True)
    company_name = Column(String(255), nullable=True)
    job_description_snapshot = Column(Text, nullable=False)
    target_language = Column(String(16), default="pt-BR", nullable=False)
    ats_score_before = Column(Integer, default=0, nullable=False)
    ats_score_after = Column(Integer, default=0, nullable=False)
    evaluation_report = Column(JSON, default=dict, nullable=False)
    changes_summary = Column(JSON, default=list, nullable=False)
    tailored_data = Column(JSON, default=dict, nullable=False)
    tailored_markdown = Column(Text, nullable=False)
    pdf_path = Column(String(500), nullable=True)
    docx_path = Column(String(500), nullable=True)
    cover_letter = Column(Text, nullable=True)
    interview_prep = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime, default=_utcnow, nullable=False)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)


class JobApplication(Base):
    __tablename__ = "job_applications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    job_id = Column(
        Integer,
        ForeignKey("job_postings.id", ondelete="SET NULL"),
        nullable=True,
    )
    tailored_resume_id = Column(
        Integer,
        ForeignKey("tailored_resumes.id", ondelete="SET NULL"),
        nullable=True,
    )
    company_name = Column(String(255), nullable=False)
    role_title = Column(String(300), nullable=False)
    job_url = Column(String(1000), nullable=True)
    stage = Column(String(50), default="wishlist", nullable=False)
    notes = Column(Text, nullable=True)
    applied_at = Column(DateTime, nullable=True)
    follow_up_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_utcnow, nullable=False)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)


class ChatThread(Base):
    __tablename__ = "chat_threads"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title = Column(String(255), default="Nova conversa", nullable=False)
    channel_origin = Column(String(32), default="web", nullable=False)
    context_type = Column(String(32), default="career", nullable=False)
    created_at = Column(DateTime, default=_utcnow, nullable=False)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)

    messages = relationship(
        "ChatMessage",
        back_populates="thread",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at.asc(), ChatMessage.id.asc()",
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    thread_id = Column(
        Integer,
        ForeignKey("chat_threads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role = Column(String(32), nullable=False)
    channel = Column(String(32), default="web", nullable=False)
    content = Column(Text, nullable=False)
    rich_payload = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=_utcnow, nullable=False)

    thread = relationship("ChatThread", back_populates="messages")
