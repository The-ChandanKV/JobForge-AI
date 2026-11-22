import json
import shutil
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Event

import httpx
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from jobforge import applications, greenhouse, llm, submission, worker
from jobforge.matching import analyze, shortlist
from jobforge.models import (Application, ApplicationEvent, Base, Job, Log, Profile, Receipt, Resume, Run,
                             Settings, WorkerLock, now)
from jobforge.permissions import PolicyRefusal, check_policy, create_policy
from jobforge.providers import fetch_board, save_job
from jobforge.resumes import compile_claims, compile_pdf, edit_bullet
from jobforge.schemas import Fact, Options, PolicyRequest, Posting, Preferences, Source


@pytest.fixture
def local_db(tmp_path, monkeypatch):
    url = "sqlite:///" + (tmp_path / "jobs.sqlite3").as_posix()
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    session = sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(worker, "Session", session)
    monkeypatch.setattr(applications, "Session", session)
    monkeypatch.setenv("DATABASE_URL", url)
    worker.initialize()
    yield session
    engine.dispose()


def fact(category, label, value):
    return Fact(category=category, label=label, value=value, verified=True).model_dump()


def test_real_worker_crash_releases_after_lease_expiry_and_recovers_same_run(local_db):
    command = (
        "import os; from jobforge import worker; "
        "worker.pipeline = lambda *_: os._exit(23); worker.step()"
    )
    assert subprocess.run([sys.executable, "-c", command], timeout=15).returncode == 23
    with local_db.begin() as db:
        run = db.scalar(select(Run))
        assert run.status == "RUNNING" and run.attempts == 1
        identity = run.id
        lock = db.get(WorkerLock, 1)
        assert lock.owner and lock.last_seen
        lock.until = lock.last_seen = worker.future(-3)
    subprocess.run([sys.executable, "-c", "from jobforge.worker import step; step()"], check=True, timeout=15)
    with local_db() as db:
        assert [run.id for run in db.scalars(select(Run))] == [identity]
        restored = db.get(Run, identity)
        assert restored.status == "COMPLETED" and restored.attempts == 2
        assert restored.report["note"].startswith("Recovered")
        assert db.scalar(select(Log).where(Log.kind == "downtime"))
        assert worker.worker_status(db, Options())["status"] == "RUNNING"


def test_pause_resume_and_missed_runs_coalesce(local_db):
    with local_db.begin() as db:
        row = db.get(Settings, 1)
        row.next_run = worker.future(-195)
        row.options = Options(enabled=False).model_dump(mode="json")
        assert worker.queue(db, "scheduled") is None
        assert worker.queue(db, "manual").trigger == "manual"
    worker.step()
    with local_db.begin() as db:
        assert db.scalar(select(Run)).status == "COMPLETED"
        db.get(Settings, 1).options = Options().model_dump(mode="json")
    worker.step()
    with local_db.begin() as db:
        scheduled = db.scalar(select(Run).where(Run.trigger == "scheduled"))
        assert scheduled.report["coalesced_intervals"] == 3
        assert worker.queue(db, "scheduled") is None
        canceled = worker.queue(db, "manual")
        canceled.canceled = True
        identity = canceled.id
    worker.step()
    with local_db() as db:
        assert db.get(Run, identity).status == "CANCELED"


def test_feed_failure_and_bounded_resume_retry(local_db, monkeypatch):
    good = Source(provider="mock", board="great", company="Synthetic API team")
    bad = Source(provider="mock", board="offline", company="Offline fixture")
    options = Options(sources=[good, bad], min_match_score=20, max_job_attempts=2)
    with local_db.begin() as db:
        db.get(Settings, 1).options = options.model_dump(mode="json")
        db.get(Profile, 1).facts = [fact("skill", name, name) for name in ("Python", "SQL", "FastAPI")]

    def read_board(source):
        if source.board == "offline":
            raise httpx.ConnectError("synthetic offline feed")
        return fetch_board(source)

    calls = []

    def fail_compile(*args):
        calls.append(1)
        raise ValueError("synthetic invalid compile")

    monkeypatch.setattr(worker, "fetch_board", read_board)
    monkeypatch.setattr(worker, "generate", fail_compile)
    for _ in range(3):
        with local_db.begin() as db:
            row = db.scalar(select(Job))
            if row and row.automation.get("next_retry"):
                row.automation = {**row.automation, "next_retry": worker.future(-1)}
            run = worker.queue(db, "manual")
        report = worker.pipeline(run.id, Event())
        with local_db.begin() as db:
            db.get(Run, run.id).status = "COMPLETED"
    assert len(calls) == 2
    assert any("ConnectError" in error for error in report["errors"])
    with local_db() as db:
        assert db.scalar(select(Job)).automation["state"] == "EXCEPTION"
        assert db.scalar(select(Log).where(Log.kind == "exception"))


@pytest.mark.parametrize("name", ["missing", "timeout"])
def test_missing_model_and_timeout_fall_back(name, monkeypatch):
    if name == "missing":
        monkeypatch.setattr(llm.httpx, "get", lambda *args, **kwargs: httpx.Response(
            200, json={"models": []}, request=httpx.Request("GET", "http://127.0.0.1")
        ))
        assert llm.model_status(Options(provider="ollama", model="absent"))["status"] == "MODEL_MISSING"

    def fail(*args):
        if name == "timeout":
            raise httpx.ReadTimeout("synthetic timeout")
        req = httpx.Request("POST", "http://127.0.0.1")
        response = httpx.Response(404, request=req)
        response.raise_for_status()

    monkeypatch.setattr(llm, "completion", fail)
    facts = [fact("skill", "Python", "Python")]
    selection, info = llm.select_facts(Options(provider="ollama", model=f"test-{name}"), "Python job", facts, "")
    assert selection is None and info["provider"] == "rules"


def test_grounded_rewrite_and_conservative_eligibility():
    source = fact("project", "API", "- I implemented a Python API and reduced median latency by 14% in 2024.")
    text = edit_bullet(source["value"])
    assert text == "Implemented a Python API and reduced median latency by 14% in 2024."
    assert compile_claims([source], [{"fact_id": source["id"], "text": text}])[0]["value"] == text
    with pytest.raises(ValueError, match="unsupported"):
        compile_claims([source], [{"fact_id": source["id"], "text": text.replace("14%", "41%")}])
    posting = Posting(source_key="test:1", source="manual", company="Synthetic firm", role="Backend Engineer",
                      description="Required skills: Python.\nPreferred: at least 5 years of experience.\nBuild educational tools.")
    facts = [fact("skill", "Python", "Python"), fact("experience", "Years of experience", "1")]
    match = analyze(posting, facts, Preferences(), 50)
    assert match["eligibility"] == "ELIGIBLE" and match["experience_years"] is None
    assert shortlist(posting, Preferences(career_tracks=["backend"], maximum_mandatory_years=2))
    assert not shortlist(posting.model_copy(update={"role": "Senior Backend Engineer"}),
                         Preferences(exclude_senior_roles=True))
    expired_posting = posting.model_copy(update={"deadline": "2000-01-01"})
    assert not shortlist(expired_posting, Preferences())
    assert analyze(expired_posting, facts, Preferences(), 50)["eligibility"] == "INELIGIBLE"


def test_invalid_latex_is_rejected():
    with pytest.raises(ValueError, match="Compilation failed"):
        compile_pdf(r"\documentclass{article}\begin{document}\NotAJobForgeCommand\end{document}", [])


def test_interrupted_form_reuses_the_compiled_version(local_db, monkeypatch):
    source = Source(provider="mock", board="interrupt", company="Synthetic Interrupted")
    with local_db.begin() as db:
        db.get(Settings, 1).options = Options(sources=[source], min_match_score=20).model_dump(mode="json")
        db.get(Profile, 1).facts = [fact("personal", "Name", "Jordan Synthetic")] + [
            fact("skill", name, name) for name in ("Python", "SQL", "FastAPI")
        ]
        run = worker.queue(db, "manual")

    def timed_out(*args):
        raise TimeoutError("synthetic window interruption")

    monkeypatch.setattr(applications, "browser_run", timed_out)
    assert worker.pipeline(run.id, Event())["prepared"] == 0
    with local_db.begin() as db:
        app = db.scalar(select(Application))
        first_version = app.resume_id
        assert app.summary["checkpoint"] == "PREPARATION_INTERRUPTED"
        job = db.get(Job, app.job_id)
        job.automation = {**job.automation, "next_retry": worker.future(-1)}
    monkeypatch.setattr(applications, "browser_run", lambda *args: {"filled": ["Resume PDF"], "missing": []})
    result = worker.pipeline(run.id, Event())
    assert result["prepared"] == 1 and result["compiled"] == 0
    with local_db() as db:
        app = db.scalar(select(Application))
        assert app.resume_id == first_version and app.status == "APPLICATION_PREPARED"
        assert len(db.scalars(select(Resume)).all()) == 1


def dispatch_fixture(db):
    profile = db.get(Profile, 1)
    profile.facts = [fact("personal", "Name", "Jordan Synthetic"), fact("personal", "First name", "Jordan"),
                     fact("personal", "Last name", "Synthetic"), fact("personal", "Email", "jordan@example.test"),
                     fact("skill", "Python", "Python")]
    job = save_job(db, Posting(source_key="greenhouse:synthetic:9", source="greenhouse",
                               company="Synthetic", role="Backend Engineer", description="Required skills: Python."))
    resume = Resume(job_id=job.id, template="classic", tex="test", pdf=b"%PDF-synthetic",
                    report={"claims": [profile.facts[0], profile.facts[-1]]})
    db.add(resume)
    db.flush()
    app = Application(job_id=job.id, resume_id=resume.id, mode="AUTHORIZED_AUTO", status="APPLICATION_PREPARED",
                      summary={"integration": "greenhouse"})
    db.add(app)
    db.flush()
    return profile, job, app


def test_saved_policy_detects_changed_forms_but_cannot_enqueue_or_dispatch(local_db, monkeypatch):
    for key, value in {
        "JOBFORGE_GREENHOUSE_AUTHORIZED": "true", "JOBFORGE_GREENHOUSE_BOARD": "synthetic",
        "JOBFORGE_GREENHOUSE_KEY": "fixture-only", "JOBFORGE_GREENHOUSE_VERIFICATION_REFERENCE": "sandbox-fixture-1",
    }.items():
        monkeypatch.setenv(key, value)
    posts = []
    payload = {"id": 9, "title": "Backend Engineer", "questions": [
        {"required": True, "fields": [{"name": field, "type": "input_text"}]}
        for field in ("first_name", "last_name", "email")
    ] + [{"required": True, "fields": [{"name": "resume", "type": "input_file"}]}]}

    def transport(request):
        if request.method == "POST":
            posts.append(request)
            return httpx.Response(200, json={"application_id": "synthetic-1"})
        return httpx.Response(200, json=payload)

    original_client = httpx.Client
    monkeypatch.setattr(applications.httpx, "Client", lambda **kwargs: original_client(
        **kwargs, transport=httpx.MockTransport(transport)
    ))
    with local_db.begin() as db:
        profile, job, app = dispatch_fixture(db)
        with original_client(transport=httpx.MockTransport(transport)) as client:
            _, values, summary = greenhouse.preflight(client, job, profile)
        app.summary = {**app.summary, **summary}
        request = PolicyRequest(employer="Synthetic", job_keys=[job.source_key], fact_ids=[f["id"] for f in profile.facts],
                                expires=datetime.now(UTC) + timedelta(hours=1), daily_limit=1,
                                minimum_score=20, acknowledge=True)
        policy = create_policy(request, profile, {job.source_key: (job, app)})
        options = Options(min_match_score=20, mode="AUTHORIZED_AUTO", automation_mode="AUTHORIZED_AUTO_SUBMIT",
                          auto_submit=True, dry_run=False)
        match = {"eligibility": "ELIGIBLE", "match_score": 90}
        resume = db.get(Resume, app.resume_id)
        with pytest.raises(PolicyRefusal, match="explicit submission policy"):
            check_policy(options, job, resume, profile, app, summary, values, match)
        options.submission_policy = policy
        db.get(Settings, 1).options = options.model_dump(mode="json")
        assert check_policy(options, job, resume, profile, app, summary, values, match).id == policy.id
        with pytest.raises(PolicyRefusal, match="changed"):
            check_policy(options, job, resume, profile, app, {**summary, "form_digest": "changed"}, values, match)
    submission.process_one(local_db)
    worker.step()
    assert not posts


def test_uncertainty_recovers_only_with_a_receipt(local_db):
    with local_db.begin() as db:
        _, _, app = dispatch_fixture(db)
        app.summary = {"simulation": True}
        app.status = "SUBMITTING"
        app_id = app.id
        db.add(ApplicationEvent(application_id=app.id, status="SUBMITTING", message="attempt", created=worker.future(-3)))
    assert applications.reconcile(app_id).status == "SUBMISSION_UNCERTAIN"
    with local_db.begin() as db:
        db.add(Receipt(id=app_id, evidence="MOCK-durable-fixture"))
    assert applications.reconcile(app_id).confirmation == "MOCK-durable-fixture"


@pytest.mark.skipif(sys.platform != "win32" or not shutil.which("pwsh"), reason="PowerShell 7 and Windows Task Scheduler required")
def test_windows_task_configuration_is_windowless_and_has_restart_settings():
    script = Path("scripts/install-windows-tasks.ps1").resolve()
    for flag, expected in [("", "Logon"), ("-Boot", "Boot")]:
        command = f"& '{script}' -Plan {flag} | ConvertTo-Json -Compress"
        result = subprocess.run(["pwsh", "-NoProfile", "-Command", command],
                                capture_output=True, text=True, encoding="utf-8", timeout=30)
        assert result.returncode == 0, result.stderr
        tasks = json.loads(result.stdout)
        assert len(tasks) == 2
        assert {task["Trigger"] for task in tasks} == {expected}
        assert all(task["RestartCount"] == 5 and task["WatchdogInterval"] == "PT1M"
                   and task["Execute"].lower().endswith("pythonw.exe") for task in tasks)
