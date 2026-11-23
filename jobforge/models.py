from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import JSON, ForeignKey, String, Text, UniqueConstraint, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from .config import DATABASE


def uid():
    return uuid4().hex


def now():
    return datetime.now(UTC).isoformat(timespec="microseconds")


class Base(DeclarativeBase):
    pass


class Profile(Base):
    __tablename__ = "profiles"
    id: Mapped[int] = mapped_column(primary_key=True)
    facts: Mapped[list] = mapped_column(JSON, default=list)
    preferences: Mapped[dict] = mapped_column(JSON, default=dict)


class Upload(Base):
    __tablename__ = "uploads"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(255))
    blob: Mapped[bytes]
    created: Mapped[str] = mapped_column(default=now)


class Settings(Base):
    __tablename__ = "settings"
    id: Mapped[int] = mapped_column(primary_key=True)
    options: Mapped[dict] = mapped_column(JSON)
    next_run: Mapped[str] = mapped_column(default=now)


class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    source_key: Mapped[str] = mapped_column(String(300), unique=True)
    canonical_url: Mapped[str | None] = mapped_column(String(1024), unique=True)
    fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    company: Mapped[str] = mapped_column(String(240))
    role: Mapped[str] = mapped_column(String(300))
    detail: Mapped[dict] = mapped_column(JSON)
    match: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(32), default="DISCOVERED")
    created: Mapped[str] = mapped_column(default=now)
    verified: Mapped[str] = mapped_column(default=now)
    available: Mapped[bool] = mapped_column(default=True)
    automation: Mapped[dict] = mapped_column(JSON, default=dict, server_default="{}")


class JobDescription(Base):
    __tablename__ = "job_descriptions"
    __table_args__ = (UniqueConstraint("job_id", "digest"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    digest: Mapped[str] = mapped_column(String(64))
    description: Mapped[str] = mapped_column(Text)
    created: Mapped[str] = mapped_column(default=now)


class JobSource(Base):
    __tablename__ = "job_sources"
    key: Mapped[str] = mapped_column(String(300), primary_key=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    canonical_url: Mapped[str | None] = mapped_column(String(1024), index=True)
    verified: Mapped[str] = mapped_column(default=now)
    available: Mapped[bool] = mapped_column(default=True)


class Resume(Base):
    __tablename__ = "resumes"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    parent_id: Mapped[str | None] = mapped_column(String(32))
    template: Mapped[str] = mapped_column(String(16))
    tex: Mapped[str] = mapped_column(Text)
    pdf: Mapped[bytes]
    report: Mapped[dict] = mapped_column(JSON)
    created: Mapped[str] = mapped_column(default=now)


class Application(Base):
    __tablename__ = "applications"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), unique=True)
    resume_id: Mapped[str] = mapped_column(ForeignKey("resumes.id"))
    mode: Mapped[str] = mapped_column(String(24))
    status: Mapped[str] = mapped_column(String(32), index=True)
    summary: Mapped[dict] = mapped_column(JSON, default=dict)
    prepared_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    confirmation: Mapped[str | None] = mapped_column(String(200))
    created: Mapped[str] = mapped_column(default=now)


class FinalApproval(Base):
    __tablename__ = "final_approvals"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), index=True)
    payload_hash: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JSON)
    created: Mapped[str] = mapped_column(default=now)


class SubmissionTask(Base):
    __tablename__ = "submission_tasks"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    approval_id: Mapped[str] = mapped_column(ForeignKey("final_approvals.id", ondelete="CASCADE"), unique=True)
    # A unique non-null dispatch key reserves the only possible POST for this application.
    dispatch_key: Mapped[str | None] = mapped_column(String(32), unique=True)
    status: Mapped[str] = mapped_column(String(32), index=True, default="QUEUED")
    attempts: Mapped[int] = mapped_column(default=0)
    available_at: Mapped[str] = mapped_column(default=now)
    attempted_at: Mapped[str | None]
    finished_at: Mapped[str | None]
    result: Mapped[str | None] = mapped_column(String(100))
    created: Mapped[str] = mapped_column(default=now)


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    kind: Mapped[str] = mapped_column(String(32))
    message: Mapped[str] = mapped_column(String(240))
    count: Mapped[int] = mapped_column(default=1)
    pending: Mapped[bool] = mapped_column(default=True)
    read: Mapped[bool] = mapped_column(default=False)
    created: Mapped[str] = mapped_column(default=now)


class ApplicationEvent(Base):
    __tablename__ = "application_events"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(32))
    message: Mapped[str] = mapped_column(String(320))
    created: Mapped[str] = mapped_column(default=now)


class Receipt(Base):
    __tablename__ = "mock_receipts"
    id: Mapped[str] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), primary_key=True)
    evidence: Mapped[str] = mapped_column(String(100), unique=True)
    created: Mapped[str] = mapped_column(default=now)


class Run(Base):
    __tablename__ = "runs"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    status: Mapped[str] = mapped_column(String(24), index=True, default="QUEUED")
    trigger: Mapped[str] = mapped_column(String(16))
    started: Mapped[str | None]
    finished: Mapped[str | None]
    canceled: Mapped[bool] = mapped_column(default=False)
    attempts: Mapped[int] = mapped_column(default=0)
    report: Mapped[dict] = mapped_column(JSON, default=dict)
    created: Mapped[str] = mapped_column(default=now)


class WorkerLock(Base):
    __tablename__ = "worker_lock"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner: Mapped[str | None] = mapped_column(String(32))
    until: Mapped[str | None]
    last_seen: Mapped[str | None]
    model_status: Mapped[dict] = mapped_column(JSON, default=dict, server_default="{}")


class Log(Base):
    __tablename__ = "logs"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    kind: Mapped[str] = mapped_column(String(32))
    message: Mapped[str] = mapped_column(String(360))
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created: Mapped[str] = mapped_column(default=now)


engine = create_engine(DATABASE, pool_pre_ping=True, hide_parameters=True)
Session = sessionmaker(engine, expire_on_commit=False)


if engine.dialect.name == "sqlite":
    @event.listens_for(engine, "connect")
    def sqlite_settings(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=10000")
