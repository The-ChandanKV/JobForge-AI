from datetime import UTC, datetime
from threading import Event

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from jobforge import notifications, reliability, worker
from jobforge.matching import evaluate_saved_job
from jobforge.models import Base, Log, Notification, Profile, Run, Settings, WorkerLock
from jobforge.profile import parse_file, readiness
from jobforge.providers import save_job
from jobforge.schemas import Fact, Options, Posting, Preferences


def configure(path, monkeypatch):
    engine = create_engine("sqlite:///" + path.as_posix())
    session = sessionmaker(engine, expire_on_commit=False)
    Base.metadata.create_all(engine)
    monkeypatch.setattr(worker, "Session", session)
    monkeypatch.setattr(reliability, "Session", session)
    worker.initialize()
    return session


def verified(category, label, value):
    return Fact(category=category, label=label, value=value, verified=True).model_dump()


def test_import_preserves_unverified_graduation_cgpa_and_contact_evidence():
    facts = parse_file("resume.txt", b"Synthetic Candidate\nfixture@example.test\nhttps://github.com/fixture-example\n"
                       b"Education\nGraduation year: 2026 | CGPA 9.1/10\nInternships\nBuilt a Python service\n"
                       b"Technical skills: Python, SQL")
    lookup = {fact.label: fact for fact in facts}
    assert lookup["Graduation year"].value == "2026"
    assert lookup["CGPA"].value == "9.1/10"
    assert lookup["Internship"].category == "experience"
    assert lookup["GitHub"].category == "personal"
    assert all(not fact.verified and fact.excerpt for fact in facts)
    assert not readiness([fact.model_dump() for fact in facts])["ready"]
    blocked = Fact(category="project", label="Project", value="Synthetic", verified=True, unsupported=True, prioritized=True)
    assert not blocked.verified and not blocked.prioritized


def test_worker_leaves_real_job_alone_without_verified_contact(tmp_path, monkeypatch):
    session = configure(tmp_path / "profile.sqlite3", monkeypatch)
    with session.begin() as db:
        db.get(Settings, 1).options = Options(min_match_score=0).model_dump(mode="json")
        profile = db.get(Profile, 1)
        profile.facts = [verified("personal", "Name", "Synthetic Candidate"), verified("skill", "Python", "Python")]
        job = save_job(db, Posting(source="manual", source_key="manual:fixture", role="Backend Engineer",
                                  company="Synthetic Employer", description="Required skills: Python"))
        evaluate_saved_job(job, profile.facts, Preferences(), 0)
        assert job.status == "SHORTLISTED"
        run = Run(trigger="manual", status="RUNNING")
        db.add(run)
        db.flush()
        run_id = run.id
    result = worker.pipeline(run_id, Event())
    assert result["blocked_by_profile"] == 1
    assert result["compiled"] == result["prepared"] == 0


def test_reliability_uses_recorded_slots_and_dedupes_unhealthy_worker_notice(tmp_path, monkeypatch):
    session = configure(tmp_path / "reliability.sqlite3", monkeypatch)
    with session.begin() as db:
        db.add(Log(kind="schedule_observation", message="Scheduler baseline", created="2026-01-04T10:00:00+00:00",
                   detail={"enabled": True, "interval_minutes": 60, "next_run": "2026-01-04T11:00:00+00:00"}))
        for hour in (11, 13):
            slot = f"2026-01-04T{hour}:00:00+00:00"
            db.add(Run(trigger="scheduled", status="COMPLETED", created=slot, started=slot,
                       finished=f"2026-01-04T{hour}:01:00+00:00",
                       report={"scheduled_for": slot, "compiled": 1, "prepared": 1}))
        db.get(WorkerLock, 1).last_seen = "2026-01-04T13:10:00+00:00"
    at = datetime(2026, 1, 4, 13, 30, tzinfo=UTC)
    summary = reliability.report(at)
    assert not summary["complete"] and summary["hours_observed"] == 3.5
    assert summary["metrics"]["Expected runs"] == 3
    assert summary["metrics"]["Actual scheduled runs"] == 2
    assert summary["metrics"]["Missed schedule slots"] == 1
    assert summary["metrics"]["Average processing seconds"] == 60
    assert notifications.record_worker_health(session, at)
    assert notifications.record_worker_health(session, at)
    with session() as db:
        assert len(db.scalars(select(Notification).where(Notification.kind == "health")).all()) == 1
