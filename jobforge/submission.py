"""Final review and durable, at-most-once dispatch."""
import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import func, select, update

from . import applications as forms
from . import greenhouse
from .matching import analyze
from .models import Application, ApplicationEvent, FinalApproval, Job, Log, Notification, Profile, Receipt, Resume, Session, Settings, SubmissionTask, now
from .schemas import Options, Posting, Preferences

READY = {"APPLICATION_PREPARED", "READY_FOR_REVIEW"}
ACTIVE = {"QUEUED", "VALIDATING", "SUBMITTING"}
FIELD_LABELS = {**forms.FIELDS, **greenhouse.CONTACT_FIELDS}


class ReviewChanged(ValueError):
    pass


class DailyLimit(ValueError):
    pass


@dataclass
class Context:
    application: Application
    job: Job
    resume: Resume
    profile: Profile
    options: Options
    payload: dict


class ApplicationProvider(Protocol):
    def validate(self, context: Context) -> None: ...
    def submit(self, context: Context) -> str | None: ...
    def verify_submission(self, db, context: Context, result: str | None) -> str | None: ...


class MockProvider:
    def validate(self, context):
        result = forms.browser_run(context.application, context.job, context.resume, context.payload["fields"])
        if (result["missing"] or result.get("form_digest") != context.payload["form_digest"]
                or result.get("filled_values") != context.payload["fields"]):
            raise ReviewChanged("The synthetic employer form changed after preparation.")

    def submit(self, context):
        return forms.browser_run(context.application, context.job, context.resume, context.payload["fields"], submit=True)

    def verify_submission(self, db, context, result):
        receipt = db.get(Receipt, context.application.id)
        return receipt.evidence if receipt and (not result or secrets.compare_digest(result, receipt.evidence)) else None


class GreenhouseProvider:
    def validate(self, context):
        with httpx.Client(timeout=15, follow_redirects=False) as client:
            url, values, form = greenhouse.preflight(client, context.job, context.profile)
        payload = context.payload
        if (form["missing"] or url != payload["destination"] or values != payload["fields"]
                or form["form_digest"] != payload["form_digest"]):
            raise ReviewChanged("The employer form, destination or verified contact fields changed.")

    def submit(self, context):
        with httpx.Client(timeout=20, follow_redirects=False) as client:
            return greenhouse.dispatch(client, context.payload["destination"], context.payload["fields"], context.resume.pdf)

    def verify_submission(self, db, context, result):
        return result


PROVIDERS: dict[str, ApplicationProvider] = {"mock": MockProvider(), "greenhouse": GreenhouseProvider()}


def stamp(seconds=0):
    return (datetime.now(UTC) + timedelta(seconds=seconds)).isoformat(timespec="microseconds")


def digest(payload):
    return greenhouse.digest(payload)


def lock(db):
    # Shared with settings changes, approval creation and reservation on SQLite/PostgreSQL.
    db.execute(update(Settings).where(Settings.id == 1).values(next_run=Settings.next_run))


def task_for(db, application_id):
    return db.scalar(select(SubmissionTask).join(FinalApproval).where(
        FinalApproval.application_id == application_id
    ).order_by(SubmissionTask.created.desc(), SubmissionTask.id.desc()).limit(1))


def readiness(app):
    if app.status == "APPLICATION_PREPARED":
        return "READY_FOR_REVIEW"
    if app.status == "NEEDS_REVIEW":
        return "PREPARING" if app.summary.get("checkpoint") == "PREPARING" else "NEEDS_MANUAL_ACTION"
    return "REJECTED_BY_USER" if app.status == "SKIPPED" else app.status


def visible_task(db, task):
    if not task:
        return None
    approval = db.get(FinalApproval, task.approval_id)
    return {"id": task.id, "status": task.status, "approval_id": approval.id,
            "approved_at": approval.created, "payload_hash": approval.payload_hash,
            "provider": approval.payload["provider"], "attempted_at": task.attempted_at,
            "finished_at": task.finished_at, "result": task.result, "preflight_attempts": task.attempts}


def context_for(db, app):
    return Context(app, db.get(Job, app.job_id), db.get(Resume, app.resume_id), db.get(Profile, 1),
                   Options.model_validate(db.get(Settings, 1).options), app.prepared_payload or {})


def provider_available(context):
    p = context.payload
    if p.get("provider") == "mock":
        return context.application.summary.get("browser") is True
    return (p.get("provider") == "greenhouse" and not context.options.dry_run
            and context.options.mode == "AUTHORIZED_AUTO" and bool(greenhouse.verified_board())
            and greenhouse.endpoint(context.job) == p.get("destination"))


def validate_snapshot(db, context):
    app, job, resume, profile, options, p = (
        context.application, context.job, context.resume, context.profile, context.options, context.payload
    )
    if (not p or p["pending"] or p["eligibility"] != "ELIGIBLE" or not p.get("form_digest")
            or not p["fields"] or not provider_available(context)):
        raise ReviewChanged("A complete, supported application is required for submission.")
    if (p["application_id"] != app.id or p["job_id"] != job.id or p["resume_id"] != resume.id
            or resume.job_id != job.id or p["job"] != job.detail or not job.available
            or job.status in {"SKIPPED", "CLOSED"}):
        raise ReviewChanged("The prepared job or resume changed. Prepare and review it again.")
    current = analyze(Posting.model_validate(job.detail), profile.facts,
                      Preferences.model_validate(profile.preferences), options.min_match_score)
    if current["eligibility"] != "ELIGIBLE":
        raise ReviewChanged("The job is no longer eligible for submission.")
    revision = db.scalar(select(Resume.id).where(Resume.job_id == job.id)
                         .order_by(Resume.created.desc(), Resume.id.desc()).limit(1))
    if (not resume.pdf.startswith(b"%PDF-") or not resume.report.get("pages") or not resume.report.get("text_length")
            or resume.report.get("quality", {}).get("unsupported_claims")
            or p["pdf_sha256"] != hashlib.sha256(resume.pdf).hexdigest()
            or p["tex_sha256"] != hashlib.sha256(resume.tex.encode()).hexdigest()
            or p["resume_revision"] != revision or not forms.still_verified(profile, resume)):
        raise ReviewChanged("Resume validation or verified evidence changed. Prepare and review the desired version.")
    if p["provider"] == "mock":
        expected = forms.contacts(profile)
        expected.update({key: value for key, value in p["saved_answers"].items() if key == "authorization"})
        if (p["destination"] != forms.mock_base() + f"/mock/{app.id}"
                or any(expected.get(key) != value for key, value in p["fields"].items())
                or not {"name", "email", "authorization"} <= p["fields"].keys()):
            raise ReviewChanged("The simulation destination or verified answers changed.")
    else:
        for key, value in p["fields"].items():
            verified = forms.profile_field(profile.facts, greenhouse.CONTACT_FIELDS[key], "personal")
            if not verified or verified.strip() != value:
                raise ReviewChanged("Verified application contact fields changed.")


def approve(db, app, presented_hash):
    context = context_for(db, app)
    task = task_for(db, app.id)
    if task:
        previous = db.get(FinalApproval, task.approval_id)
        if secrets.compare_digest(previous.payload_hash, presented_hash):
            return task
        if task.status in ACTIVE or task.dispatch_key:
            raise ReviewChanged("A submission task already exists for this application.")
    if app.status not in READY or not context.payload or not secrets.compare_digest(digest(context.payload), presented_hash):
        raise ReviewChanged("The review is stale. Open the application again before approving.")
    validate_snapshot(db, context)
    approval = FinalApproval(application_id=app.id, payload_hash=presented_hash, payload=context.payload)
    db.add(approval)
    db.flush()
    task = SubmissionTask(approval_id=approval.id)
    db.add(task)
    app.summary = {**app.summary, "durable_approval": True}
    forms.record(db, app, "APPROVED", "User approved this exact application and queued final submission.")
    db.flush()
    return task


def invalidate_before_edit(db, app):
    task = task_for(db, app.id)
    if task and (task.dispatch_key or task.status == "SUBMITTING"):
        raise ReviewChanged("This application already has a dispatch checkpoint.")
    if task and task.status in {"QUEUED", "VALIDATING"}:
        task.status, task.result, task.finished_at = "NEEDS_MANUAL_ACTION", "approval_invalidated", now()
        forms.record(db, app, "NEEDS_MANUAL_ACTION", "Editing the application invalidated its pending approval.")


def claim(db):
    lock(db)
    task = db.scalar(select(SubmissionTask).where(
        SubmissionTask.status.in_(["QUEUED", "VALIDATING", "SUBMITTING"]),
        SubmissionTask.available_at <= now(),
    ).order_by(SubmissionTask.available_at).limit(1))
    if not task:
        return None
    approval = db.get(FinalApproval, task.approval_id)
    app = db.get(Application, approval.application_id)
    context = context_for(db, app)
    if task.status == "SUBMITTING":
        provider = PROVIDERS[approval.payload["provider"]]
        complete(db, context, task, provider.verify_submission(db, context, None), "worker_interrupted")
        return None
    if task.attempts >= 3:
        stop_preflight(db, app, task, "preflight_interrupted", "Submission validation attempts were exhausted.")
        return None
    task.status, task.available_at = "VALIDATING", stamp(120)
    task.attempts += 1
    return task.id, task.attempts


def stop_preflight(db, app, task, code, message):
    task.status, task.result, task.finished_at = "NEEDS_MANUAL_ACTION", code, now()
    forms.record(db, app, "NEEDS_MANUAL_ACTION", message)
    db.add(Notification(kind="outcome", message="An application needs attention before submission."))


def complete(db, context, task, confirmation, diagnostic):
    app = context.application
    status = "SUBMITTED" if confirmation else "FAILED" if diagnostic == "provider_rejected" else "SUBMISSION_UNCERTAIN"
    task.status, task.result, task.finished_at = status, "confirmed" if confirmation else diagnostic, now()
    message = {"SUBMITTED": "Provider confirmation recorded.", "FAILED": "Provider definitively rejected the request.",
               "SUBMISSION_UNCERTAIN": "No conclusive receipt. Reconcile before any further action."}[status]
    if confirmation:
        app.confirmation = confirmation
        app.summary = {**app.summary, "confirmed_at": now()}
    forms.record(db, app, status, message)
    db.add(Notification(kind="outcome", message=message))
    db.add(Log(kind="submission", message=message,
               detail={"application_id": app.id, "task_id": task.id, "result": task.result}))


def approved_context(db, task, attempt):
    if not task or task.status != "VALIDATING" or task.attempts != attempt:
        return None
    approval = db.get(FinalApproval, task.approval_id)
    context = context_for(db, db.get(Application, approval.application_id))
    if (context.application.status != "APPROVED" or digest(approval.payload) != approval.payload_hash
            or digest(context.payload) != approval.payload_hash):
        raise ReviewChanged("The approved payload no longer matches this prepared application.")
    validate_snapshot(db, context)
    return context


def process_one(session=None):
    session = session or Session
    with session.begin() as db:
        claimed = claim(db)
    if not claimed:
        return
    identity, attempt = claimed
    try:
        with session() as db:
            context = approved_context(db, db.get(SubmissionTask, identity), attempt)
        if context is None:
            return
        provider = PROVIDERS[context.payload["provider"]]
        provider.validate(context)
        with session.begin() as db:
            lock(db)
            task = db.get(SubmissionTask, identity)
            context = approved_context(db, task, attempt)
            if context is None:
                return
            if context.payload["provider"] == "greenhouse":
                start = datetime.now(ZoneInfo(context.options.timezone)).replace(
                    hour=0, minute=0, second=0, microsecond=0).astimezone(UTC).isoformat()
                used = db.scalar(select(func.count()).select_from(SubmissionTask).join(FinalApproval)
                                 .join(Application).where(Application.mode == "AUTHORIZED_AUTO",
                                                          SubmissionTask.attempted_at >= start))
                if used >= context.options.max_submissions_per_day:
                    raise DailyLimit("The configured daily submission limit was reached.")
            task.status, task.attempted_at, task.available_at = "SUBMITTING", now(), stamp(180)
            task.dispatch_key = context.application.id
            forms.record(db, context.application, "SUBMITTING", "Approved payload reserved for one dispatch attempt.")
    except Exception as exc:
        with session.begin() as db:
            lock(db)
            task = db.get(SubmissionTask, identity)
            if task and task.status == "VALIDATING" and task.attempts == attempt:
                app = db.get(Application, db.get(FinalApproval, task.approval_id).application_id)
                transient = isinstance(exc, (httpx.TransportError, OSError, TimeoutError)) or (
                    isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code in {408, 429, 500, 502, 503, 504}
                )
                if transient and attempt < 3:
                    task.status, task.available_at, task.result = "QUEUED", stamp(30 * attempt), "preflight_retry"
                    db.add(ApplicationEvent(application_id=app.id, status="APPROVED",
                                            message=f"Read-only validation retry scheduled ({attempt}/3)."))
                else:
                    message = str(exc) if isinstance(exc, (ReviewChanged, DailyLimit)) else "Provider preflight could not validate this application."
                    stop_preflight(db, app, task, type(exc).__name__, message)
        return
    result, diagnostic = None, "receipt_missing"
    try:
        result = provider.submit(context)
    except httpx.HTTPStatusError as exc:
        diagnostic = "provider_rejected" if exc.response.status_code in {400, 401, 403, 404, 413, 415, 422, 429} else "provider_http_uncertain"
    except Exception as exc:
        diagnostic = type(exc).__name__
    with session.begin() as db:
        lock(db)
        task = db.get(SubmissionTask, identity)
        if task.status == "SUBMITTING":
            complete(db, context_for(db, db.get(Application, context.application.id)), task,
                     provider.verify_submission(db, context, result), diagnostic)
