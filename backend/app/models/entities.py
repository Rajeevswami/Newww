from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import (
    String,
    Float,
    Integer,
    Boolean,
    ForeignKey,
    JSON,
    DateTime,
    Index,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def uid():
    return str(uuid4())


def now():
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Tenant(Base):
    __tablename__ = "tenants"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(100))
    slug: Mapped[str] = mapped_column(String(100), unique=True)
    plan: Mapped[str] = mapped_column(String(20), default="Free")
    stripe_customer_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class TenantScoped:
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)


class User(TenantScoped, Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("tenant_id", "email"),
        Index("ix_users_tenant_id_id", "tenant_id", "id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(255), index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(25))
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    token_version: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Job(TenantScoped, Base):
    __tablename__ = "jobs"
    __table_args__ = (Index("ix_jobs_tenant_id_id", "tenant_id", "id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    title: Mapped[str] = mapped_column(String(150))
    department: Mapped[str] = mapped_column(String(100), default="Engineering")
    description: Mapped[str] = mapped_column(Text)
    required_skills: Mapped[list] = mapped_column(JSON, default=list)
    experience_level: Mapped[str] = mapped_column(String(30), default="Mid-level")
    location: Mapped[str] = mapped_column(String(100), default="Remote")
    employment_type: Mapped[str] = mapped_column(String(30), default="Full-time")
    salary: Mapped[str] = mapped_column(String(100), default="")
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Resume(TenantScoped, Base):
    __tablename__ = "resumes"
    __table_args__ = (Index("ix_resumes_tenant_id_id", "tenant_id", "id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    filename: Mapped[str] = mapped_column(String(255))
    parsed_json: Mapped[dict] = mapped_column(JSON, default=dict)
    embedding: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(20), default="ready")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Application(TenantScoped, Base):
    __tablename__ = "applications"
    __table_args__ = (
        UniqueConstraint("job_id", "user_id"),
        Index("ix_applications_tenant_id_id", "tenant_id", "id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    resume_id: Mapped[str] = mapped_column(ForeignKey("resumes.id"))
    match_score: Mapped[float | None] = mapped_column(Float, nullable=True, default=None)
    status: Mapped[str] = mapped_column(String(30), default="New")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Interview(TenantScoped, Base):
    __tablename__ = "interviews"
    __table_args__ = (
        Index("ix_interviews_tenant_id_id", "tenant_id", "id"),
        Index(
            "uq_active_interview",
            "tenant_id",
            "application_id",
            unique=True,
            sqlite_where=text("status IN ('in_progress', 'processing')"),
            postgresql_where=text("status IN ('in_progress', 'processing')"),
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id"))
    transcript_json: Mapped[list] = mapped_column(JSON, default=list)
    scorecard_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    state_json: Mapped[dict] = mapped_column(JSON, default=dict)
    turn: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(30), default="in_progress")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RefreshToken(TenantScoped, Base):
    __tablename__ = "refresh_tokens"
    __table_args__ = (Index("ix_refresh_tokens_tenant_id_id", "tenant_id", "id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)


class ActionToken(TenantScoped, Base):
    __tablename__ = "action_tokens"
    __table_args__ = (Index("ix_action_tokens_tenant_id_id", "tenant_id", "id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    purpose: Mapped[str] = mapped_column(String(20))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used: Mapped[bool] = mapped_column(Boolean, default=False)


class ApiKey(TenantScoped, Base):
    __tablename__ = "api_keys"
    __table_args__ = (Index("ix_api_keys_tenant_id_id", "tenant_id", "id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(80))
    key_hash: Mapped[str] = mapped_column(String(64), unique=True)
    scopes: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)


class AuditLog(TenantScoped, Base):
    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_logs_tenant_id_id", "tenant_id", "id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(String(36))
    action: Mapped[str] = mapped_column(String(100))
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
