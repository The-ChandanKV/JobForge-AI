from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from jobforge import api, applications, notifications, submission, worker
from jobforge.models import Application, ApplicationEvent, Base, Log, Run, FinalApproval, Notification, Profile, Receipt, Resume, Settings, SubmissionTask
from jobforge.providers import save_job
from jobforge.schemas import Fact, Posting


@pytest.fixture
def db_sessions(tmp_path, monkeypatch):
    engine = create_engine("sqlite:///" + (tmp_path / "review.sqlite3").as_posix())
    Base.metadata.create_all(engine)
    session = sessionmaker(engine, expire_on_commit=False)
    for module in (api, applications, submission, worker):
        monkeypatch.setattr(module, "Session", session)
    worker.initialize()
    with session.begin() as db:
        db.get(Profile, 1).facts = [
            Fact(category=category, label=label, value=value, verified=True).model_dump()
            for category, label, value in [
                ("personal", "Name", "Jo Synthetic"), ("personal", "Email", "jo@example.test"),
                ("authorization", "Mock screening answer", "Fixture answer"), ("skill", "Skill", "Python"),
            ]
        ]
    yield session
    engine.dispose()


@pytest.fixture
def fake_browser(db_sessions, monkeypatch):
    posts = []

    def browser(app, job, resume, values, submit=False):
        if submit:
            posts.append((app.id, values))
            with db_sessions.begin() as db:
                db.add(Receipt(id=app.id, evidence=f"MOCK-{app.id}"))
            return f"MOCK-{app.id}"
        return {"filled": list(values), "missing": [], "form_digest": "synthetic-form",
                "filled_values": {key: value for key, value in values.items() if value}}

    monkeypatch.setattr(applications, "browser_run", browser)
    return posts


def prepared(session, sequence="1", source="mock"):
    with session.begin() as db:
        job = save_job(db, Posting(source_key=f"{source}:{sequence}:fixture", source=source,
                                   company=f"Synthetic Employer {sequence}", role="Backend Engineer",
                                   description="Required skills: Python.",
                                   url="https://example.test/job/" + sequence if source != "mock" else None))
        profile = db.get(Profile, 1)
        resume = Resume(job_id=job.id, template="classic", tex="fixture", pdf=b"%PDF-1.4",
                        report={"claims": [profile.facts[-1]], "pages": 1, "text_length": 30})
        db.add(resume)
        db.flush()
    return applications.prepare(job.id, resume.id, profile, "ASSISTED", "ELIGIBLE")


def request_for(app):
    return {"application_id": app.id, "payload_hash": submission.digest(app.prepared_payload)}


def test_final_approval_is_queued_concurrent_and_confirmed_once(db_sessions, fake_browser):
    app = prepared(db_sessions)
    request = request_for(app)

    def click(_):
        with TestClient(api.app) as client:
            response = client.post(f"/api/applications/{app.id}/approve-submit", json=request)
            assert response.status_code == 202, response.text
            assert response.json()["status"] == "QUEUED"
            return response.json()["id"]

    with ThreadPoolExecutor(max_workers=4) as pool:
        ids = list(pool.map(click, range(4)))
    assert len(set(ids)) == 1 and not fake_browser
    submission.process_one()
    submission.process_one()
    with db_sessions() as db:
        assert db.scalar(select(func.count()).select_from(FinalApproval)) == 1
        task = db.get(SubmissionTask, ids[0])
        assert task.status == "SUBMITTED"
        assert task.dispatch_key == app.id and task.attempted_at
        assert db.get(Application, app.id).confirmation == f"MOCK-{app.id}"
        assert db.get(FinalApproval, task.approval_id).payload_hash == request["payload_hash"]
    assert len(fake_browser) == 1


def test_bulk_is_atomic_and_binds_each_previously_presented_hash(db_sessions, fake_browser):
    first, second, manual = (prepared(db_sessions, num, source) for num, source in
                             [("1", "mock"), ("2", "mock"), ("3", "lever")])
    with TestClient(api.app) as client:
        review = client.get(f"/api/applications/{manual.id}/review").json()
        assert not review["approvable"] and review["payload"]["provider"] == "manual"
        assert review["payload"]["destination"] == "https://example.test/job/3"
        wrong = {**request_for(second), "payload_hash": request_for(first)["payload_hash"]}
        bad = client.post("/api/applications/bulk-review", json={"reviews": [request_for(first), wrong]})
        assert bad.status_code == 422
        unsupported = client.post(f"/api/applications/{manual.id}/approve-submit", json=request_for(manual))
        assert unsupported.status_code == 422
        rejected = client.post("/api/applications/bulk-reject", json={"reviews": [request_for(manual)]})
        assert rejected.json() == {"rejected": 1}
        with db_sessions() as db:
            assert db.scalar(select(func.count()).select_from(FinalApproval)) == 0
            assert db.get(Application, manual.id).status == "REJECTED_BY_USER"
        good = client.post("/api/applications/bulk-review", json={"reviews": [request_for(first), request_for(second)]})
        assert good.status_code == 202 and len({task["approval_id"] for task in good.json()}) == 2
        assert not fake_browser
    submission.process_one()
    submission.process_one()
    assert {app_id for app_id, _ in fake_browser} == {first.id, second.id}


@pytest.mark.parametrize("change", ["resume", "answers", "profile", "destination", "approval_hash"])
def test_changed_review_never_dispatches_old_approval(db_sessions, fake_browser, change):
    app = prepared(db_sessions)
    with TestClient(api.app) as client:
        answer = client.post(f"/api/applications/{app.id}/approve-submit", json=request_for(app))
        assert answer.status_code == 202
        task_id = answer.json()["id"]
        if change == "answers":
            result = client.put(f"/api/applications/{app.id}/review", json={"answers": {"authorization": "New exact answer"}})
            assert result.status_code == 200, result.text
            with db_sessions() as db:
                assert db.get(Application, app.id).prepared_payload["fields"]["authorization"] == "New exact answer"
        elif change == "profile":
            profile = client.get("/api/state").json()["profile"]
            email = next(fact for fact in profile["facts"] if fact["label"] == "Email")
            email["value"] = "changed@example.test"
            result = client.put("/api/profile", json=profile)
            assert result.status_code == 200, result.text
        else:
            with db_sessions.begin() as db:
                current = db.get(Application, app.id)
                if change == "resume":
                    db.add(Resume(job_id=app.job_id, template="classic", tex="New version", pdf=b"%PDF-1.4", report={}))
                elif change == "destination":
                    current.prepared_payload = {**current.prepared_payload, "destination": "http://127.0.0.1:8000/different"}
                else:
                    approval = db.get(FinalApproval, db.get(SubmissionTask, task_id).approval_id)
                    approval.payload_hash = "e" * 64
    submission.process_one()
    with db_sessions() as db:
        task = db.get(SubmissionTask, task_id)
        assert task.status == "NEEDS_MANUAL_ACTION" and task.dispatch_key is None
    assert not fake_browser


def test_failed_no_receipt_timeout_is_never_replayed(db_sessions, fake_browser, monkeypatch):
    app = prepared(db_sessions)
    provider = submission.PROVIDERS["mock"]
    attempts = []

    def timeout_after_reservation(_):
        attempts.append(1)
        raise httpx.ReadTimeout("synthetic provider timeout")

    monkeypatch.setattr(provider, "submit", timeout_after_reservation)
    with TestClient(api.app) as client:
        response = client.post(f"/api/applications/{app.id}/approve-submit", json=request_for(app))
        task_id = response.json()["id"]
        submission.process_one()
        submission.process_one()
        replay = client.post(f"/api/applications/{app.id}/approve-submit", json=request_for(app))
        assert replay.json()["status"] == "SUBMISSION_UNCERTAIN"
        with db_sessions() as db:
            assert db.get(SubmissionTask, task_id).attempted_at
            assert db.get(Application, app.id).confirmation is None
    assert attempts == [1]


def test_preflight_retries_only_before_dispatch_and_are_bounded(db_sessions, fake_browser, monkeypatch):
    app = prepared(db_sessions)
    provider = submission.PROVIDERS["mock"]
    attempts = []

    def timeout_before_reservation(_):
        attempts.append(1)
        raise httpx.ReadTimeout("synthetic preflight timeout")

    monkeypatch.setattr(provider, "validate", timeout_before_reservation)
    with db_sessions.begin() as db:
        submission.lock(db)
        task = submission.approve(db, db.get(Application, app.id), request_for(app)["payload_hash"])
        task_id = task.id
    for _ in range(4):
        submission.process_one()
        with db_sessions.begin() as db:
            task = db.get(SubmissionTask, task_id)
            assert task.attempted_at is None
            task.available_at = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()
    assert attempts == [1, 1, 1] and not fake_browser
    assert task.status == "NEEDS_MANUAL_ACTION"


def test_notifications_batch_both_ready_applications_and_are_readable(db_sessions, fake_browser, monkeypatch):
    prepared(db_sessions, "1")
    prepared(db_sessions, "2")
    messages = []
    monkeypatch.setattr(notifications, "desktop_notification", messages.append)
    notifications.deliver_review_notifications(db_sessions)
    prepared(db_sessions, "3")
    notifications.deliver_review_notifications(db_sessions)
    assert messages == ["2 applications are ready for review."]
    with TestClient(api.app) as client:
        assert client.get("/api/state").json()["unread_notifications"] == 3
        assert client.post("/api/notifications/read").json() == {"read": True}
        assert all(item["read"] for item in client.get("/api/notifications").json())
    with db_sessions() as db:
        assert db.scalar(select(func.count()).select_from(Notification).where(Notification.pending.is_(True))) == 1


def test_daily_summary_uses_previous_local_day_and_records_once(db_sessions, fake_browser):
    application = prepared(db_sessions)
    with db_sessions.begin() as db:
        db.get(Settings, 1).options = {**db.get(Settings, 1).options, "timezone": "Asia/Kolkata"}
        for finished, count in [("2026-01-03T18:29:59+00:00", 40),
                                ("2026-01-03T18:30:01+00:00", 2),
                                ("2026-01-04T18:30:01+00:00", 80)]:
            db.add(Run(status="COMPLETED", trigger="scheduled", finished=finished,
                       report={"compiled": count, "prepared": count}))
        db.add(ApplicationEvent(application_id=application.id, status="SUBMITTED",
                                message="Synthetic receipt", created="2026-01-04T12:00:00+00:00"))
    at = datetime(2026, 1, 4, 20, tzinfo=UTC)
    notifications.record_daily_summary(db_sessions, at)
    notifications.record_daily_summary(db_sessions, at + timedelta(minutes=5))
    with db_sessions() as db:
        notice = db.scalars(select(Notification).where(Notification.kind == "daily_summary")).one()
        assert notice.message == "2026-01-04 · Runs finished 1, resumes compiled 2, applications prepared 2, confirmations recorded 1."
        assert not notice.pending
        assert db.scalar(select(func.count()).select_from(Log).where(Log.kind == "daily_summary")) == 1


def test_greenhouse_uses_only_final_approval_and_verifies_mocked_response(db_sessions, monkeypatch):
    for key, value in {
        "JOBFORGE_GREENHOUSE_AUTHORIZED": "true", "JOBFORGE_GREENHOUSE_BOARD": "synthetic",
        "JOBFORGE_GREENHOUSE_KEY": "fixture-only", "JOBFORGE_GREENHOUSE_VERIFICATION_REFERENCE": "sandbox-fixture-one",
    }.items():
        monkeypatch.setenv(key, value)
    post_calls = []
    questions = [
        {"required": True, "fields": [{"name": field, "type": "input_text"}]}
        for field in ("first_name", "last_name", "email")
    ] + [{"required": True, "fields": [{"name": "resume", "type": "input_file"}]}]

    def transport(request):
        assert request.url.host == "boards-api.greenhouse.io"
        if request.method == "POST":
            body = request.read()
            assert b"%PDF-1.4" in body and b"jo@example.test" in body
            post_calls.append(request)
            return httpx.Response(200, json={"application_id": "fixture-123"})
        return httpx.Response(200, json={"id": 123, "title": "Backend Engineer", "questions": questions})

    real_client = httpx.Client
    monkeypatch.setattr(applications.httpx, "Client", lambda **kwargs: real_client(
        **kwargs, transport=httpx.MockTransport(transport)))
    with db_sessions.begin() as db:
        profile = db.get(Profile, 1)
        profile.facts = [*profile.facts, *[Fact(category="personal", label=label, value=value, verified=True).model_dump()
                                         for label, value in [("First name", "Jo"), ("Last name", "Synthetic")]]]
        job = save_job(db, Posting(source_key="greenhouse:synthetic:123", source="greenhouse",
                                   company="Synthetic", role="Backend Engineer", description="Required skills: Python."))
        resume = Resume(job_id=job.id, template="classic", tex="fixture", pdf=b"%PDF-1.4",
                        report={"claims": [profile.facts[3]], "pages": 1, "text_length": 30})
        db.add(resume)
        db.flush()
        settings = db.get(Settings, 1)
        settings.options = {**settings.options, "mode": "AUTHORIZED_AUTO", "dry_run": False}
    app = applications.prepare(job.id, resume.id, profile, "AUTHORIZED_AUTO", "ELIGIBLE")
    submission.process_one()
    assert not post_calls
    with TestClient(api.app) as client:
        old = client.post(f"/api/applications/{app.id}/decision", json={"action": "submit_authorized"})
        assert old.status_code == 422
        with db_sessions() as db:
            options = db.get(Settings, 1).options
        assert client.put("/api/settings", json={**options, "auto_submit": True}).status_code == 422
        assert client.post(f"/api/applications/{app.id}/approve-submit", json=request_for(app)).status_code == 202
        assert not post_calls
        submission.process_one()
        terminal = client.get(f"/api/applications/{app.id}/review").json()
        assert terminal["task"]["provider"] == "greenhouse"
        assert terminal["task"]["status"] == "SUBMITTED", terminal
        assert "fixture-123" in terminal["application"]["confirmation"]
    assert len(post_calls) == 1
