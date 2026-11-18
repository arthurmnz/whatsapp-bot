"""Initial RBAC and jobs_career schema

Revision ID: 0001_initial_jobs_career
Revises:
Create Date: 2026-11-17 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001_initial_jobs_career"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("permissions"):
        op.create_table(
            "permissions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("code", sa.String(length=100), nullable=False),
            sa.Column("description", sa.String(length=255), nullable=True),
            sa.UniqueConstraint("code"),
        )
        op.create_index("ix_permissions_code", "permissions", ["code"], unique=True)

    if not inspector.has_table("roles"):
        op.create_table(
            "roles",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(length=50), nullable=False),
            sa.Column("description", sa.String(length=255), nullable=True),
            sa.UniqueConstraint("name"),
        )
        op.create_index("ix_roles_name", "roles", ["name"], unique=True)

    if not inspector.has_table("role_permissions"):
        op.create_table(
            "role_permissions",
            sa.Column("role_id", sa.Integer(), sa.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
            sa.Column("permission_id", sa.Integer(), sa.ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
        )

    if not inspector.has_table("users"):
        op.create_table(
            "users",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("nome", sa.String(length=150), nullable=False),
            sa.Column("senha", sa.Text(), nullable=False),
            sa.Column("remote_jid_hash", sa.String(length=64), nullable=False),
            sa.Column("web_password_hash", sa.Text(), nullable=True),
            sa.Column("role_id", sa.Integer(), sa.ForeignKey("roles.id"), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.UniqueConstraint("remote_jid_hash"),
        )
        op.create_index("ix_users_remote_jid_hash", "users", ["remote_jid_hash"], unique=True)
    else:
        existing_cols = {c["name"] for c in inspector.get_columns("users")}
        if "web_password_hash" not in existing_cols:
            op.add_column("users", sa.Column("web_password_hash", sa.Text(), nullable=True))
        if "updated_at" not in existing_cols:
            op.add_column("users", sa.Column("updated_at", sa.DateTime(), nullable=True))

    if not inspector.has_table("candidate_profiles"):
        op.create_table(
            "candidate_profiles",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("headline", sa.String(length=255), nullable=True),
            sa.Column("summary", sa.Text(), nullable=True),
            sa.Column("years_experience", sa.Float(), nullable=False, server_default="0"),
            sa.Column("location", sa.String(length=255), nullable=True),
            sa.Column("linkedin_url", sa.String(length=500), nullable=True),
            sa.Column("github_url", sa.String(length=500), nullable=True),
            sa.Column("portfolio_url", sa.String(length=500), nullable=True),
            sa.Column("languages", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("user_id"),
        )

    if not inspector.has_table("candidate_skills"):
        op.create_table(
            "candidate_skills",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("profile_id", sa.Integer(), sa.ForeignKey("candidate_profiles.id", ondelete="CASCADE"), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("normalized_name", sa.String(length=120), nullable=False),
            sa.Column("category", sa.String(length=80), nullable=True),
            sa.Column("proficiency", sa.String(length=50), nullable=True),
            sa.Column("years_used", sa.Float(), nullable=True),
            sa.Column("is_core", sa.Boolean(), nullable=False, server_default=sa.false()),
        )

    if not inspector.has_table("job_preferences"):
        op.create_table(
            "job_preferences",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("profile_id", sa.Integer(), sa.ForeignKey("candidate_profiles.id", ondelete="CASCADE"), nullable=False),
            sa.Column("target_roles", sa.JSON(), nullable=False),
            sa.Column("seniority_levels", sa.JSON(), nullable=False),
            sa.Column("work_models", sa.JSON(), nullable=False),
            sa.Column("contract_types", sa.JSON(), nullable=False),
            sa.Column("min_salary", sa.Float(), nullable=True),
            sa.Column("salary_currency", sa.String(length=10), nullable=False, server_default="BRL"),
            sa.Column("desired_stack", sa.JSON(), nullable=False),
            sa.Column("dealbreakers", sa.JSON(), nullable=False),
            sa.Column("target_companies", sa.JSON(), nullable=False),
            sa.Column("preferred_language", sa.String(length=16), nullable=False, server_default="auto"),
            sa.Column("auto_search_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("min_notify_score", sa.Integer(), nullable=False, server_default="70"),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("profile_id"),
        )

    if not inspector.has_table("resumes"):
        op.create_table(
            "resumes",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("language", sa.String(length=16), nullable=False, server_default="pt-BR"),
            sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("source_format", sa.String(length=20), nullable=False, server_default="text"),
            sa.Column("file_path", sa.String(length=500), nullable=True),
            sa.Column("raw_text", sa.Text(), nullable=False),
            sa.Column("structured_data", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )

    if not inspector.has_table("job_postings"):
        op.create_table(
            "job_postings",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("source", sa.String(length=64), nullable=False),
            sa.Column("external_id", sa.String(length=255), nullable=True),
            sa.Column("source_url", sa.String(length=1000), nullable=True),
            sa.Column("dedupe_hash", sa.String(length=64), nullable=False),
            sa.Column("title", sa.String(length=300), nullable=False),
            sa.Column("company_name", sa.String(length=255), nullable=True),
            sa.Column("location", sa.String(length=255), nullable=True),
            sa.Column("work_model", sa.String(length=50), nullable=True),
            sa.Column("contract_type", sa.String(length=50), nullable=True),
            sa.Column("seniority", sa.String(length=50), nullable=True),
            sa.Column("salary_min", sa.Float(), nullable=True),
            sa.Column("salary_max", sa.Float(), nullable=True),
            sa.Column("salary_currency", sa.String(length=10), nullable=True),
            sa.Column("language", sa.String(length=16), nullable=False, server_default="en"),
            sa.Column("description_raw", sa.Text(), nullable=False),
            sa.Column("extracted_requirements", sa.JSON(), nullable=False),
            sa.Column("posted_at", sa.DateTime(), nullable=True),
            sa.Column("fetched_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("dedupe_hash"),
        )

    if not inspector.has_table("job_matches"):
        op.create_table(
            "job_matches",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("job_id", sa.Integer(), sa.ForeignKey("job_postings.id", ondelete="CASCADE"), nullable=False),
            sa.Column("match_score", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("score_breakdown", sa.JSON(), nullable=False),
            sa.Column("matched_skills", sa.JSON(), nullable=False),
            sa.Column("missing_skills", sa.JSON(), nullable=False),
            sa.Column("ai_rationale", sa.Text(), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="new"),
            sa.Column("notified_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("user_id", "job_id", name="uq_job_matches_user_job"),
        )

    if not inspector.has_table("tailored_resumes"):
        op.create_table(
            "tailored_resumes",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("base_resume_id", sa.Integer(), sa.ForeignKey("resumes.id", ondelete="SET NULL"), nullable=True),
            sa.Column("job_id", sa.Integer(), sa.ForeignKey("job_postings.id", ondelete="SET NULL"), nullable=True),
            sa.Column("job_title", sa.String(length=300), nullable=True),
            sa.Column("company_name", sa.String(length=255), nullable=True),
            sa.Column("job_description_snapshot", sa.Text(), nullable=False),
            sa.Column("target_language", sa.String(length=16), nullable=False, server_default="pt-BR"),
            sa.Column("ats_score_before", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("ats_score_after", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("evaluation_report", sa.JSON(), nullable=False),
            sa.Column("changes_summary", sa.JSON(), nullable=False),
            sa.Column("tailored_data", sa.JSON(), nullable=False),
            sa.Column("tailored_markdown", sa.Text(), nullable=False),
            sa.Column("pdf_path", sa.String(length=500), nullable=True),
            sa.Column("docx_path", sa.String(length=500), nullable=True),
            sa.Column("cover_letter", sa.Text(), nullable=True),
            sa.Column("interview_prep", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )

    if not inspector.has_table("job_applications"):
        op.create_table(
            "job_applications",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("job_id", sa.Integer(), sa.ForeignKey("job_postings.id", ondelete="SET NULL"), nullable=True),
            sa.Column("tailored_resume_id", sa.Integer(), sa.ForeignKey("tailored_resumes.id", ondelete="SET NULL"), nullable=True),
            sa.Column("company_name", sa.String(length=255), nullable=False),
            sa.Column("role_title", sa.String(length=300), nullable=False),
            sa.Column("job_url", sa.String(length=1000), nullable=True),
            sa.Column("stage", sa.String(length=50), nullable=False, server_default="wishlist"),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("applied_at", sa.DateTime(), nullable=True),
            sa.Column("follow_up_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )

    if not inspector.has_table("chat_threads"):
        op.create_table(
            "chat_threads",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("channel_origin", sa.String(length=32), nullable=False),
            sa.Column("context_type", sa.String(length=32), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )

    if not inspector.has_table("chat_messages"):
        op.create_table(
            "chat_messages",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("thread_id", sa.Integer(), sa.ForeignKey("chat_threads.id", ondelete="CASCADE"), nullable=False),
            sa.Column("role", sa.String(length=32), nullable=False),
            sa.Column("channel", sa.String(length=32), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("rich_payload", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )


def downgrade() -> None:
    for table in [
        "chat_messages",
        "chat_threads",
        "job_applications",
        "tailored_resumes",
        "job_matches",
        "job_postings",
        "resumes",
        "job_preferences",
        "candidate_skills",
        "candidate_profiles",
    ]:
        op.drop_table(table)
