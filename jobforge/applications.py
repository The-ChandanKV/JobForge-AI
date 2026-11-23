import hashlib
import json
import os
import secrets
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright
from sqlalchemy import select, update

from . import greenhouse
from .matching import profile_field
from .models import Application, ApplicationEvent, FinalApproval, Job, Log, Notification, Profile, Receipt, Resume, Session, SubmissionTask, now

FIELDS = {"name": "Name", "email": "Email", "phone": "Phone", "authorization": "Mock screening answer"}
PREPARABLE = {"FAILED", "NEEDS_REVIEW", "NEEDS_MANUAL_ACTION", "APPLICATION_PREPARED", "READY_FOR_REVIEW", "SKIPPED"}


def record(db, application, status, message):
    application.status = status
    db.add(ApplicationEvent(application_id=application.id, status=status, message=message))
    if status in {"APPLICATION_PREPARED", "SUBMITTED", "SUBMISSION_UNCERTAIN", "FAILED"}:
        db.add(Log(kind="application", message=message, detail={"application_id": application.id, "status": status}))


def still_verified(profile, resume):
    verified = {f["id"]: f for f in profile.facts if f["verified"]}
    return all(verified.get(f["id"], {}).get("value") == f["value"]
               and verified.get(f["id"], {}).get("category") == f["category"]
               and verified.get(f["id"], {}).get("label") == f["label"] for f in resume.report["claims"])


def mock_base():
    base = os.getenv("JOBFORGE_MOCK_ORIGIN", "http://127.0.0.1:8000").rstrip("/")
    parts = urlsplit(base)
    if (parts.scheme != "http" or parts.hostname not in {"127.0.0.1", "localhost", "backend"}
            or parts.path or parts.username or parts.password or parts.query or parts.fragment):
        raise ValueError("Mock browser origin must be the local JobForge server.")
    return base


def browser_run(app, job, resume, values, submit=False):
    base = mock_base()
    with sync_playwright() as pw:
        executable = os.getenv("JOBFORGE_BROWSER_EXECUTABLE")
        launch = {"executable_path": executable} if executable else {}
        browser = pw.chromium.launch(**launch)
        try:
            context = browser.new_context(extra_http_headers={"X-JobForge-Mock": app.summary["mock_key"]},
                                          service_workers="block")
            target = base + f"/mock/{app.id}"
            context.route("**/*", lambda route: route.continue_() if route.request.url == target else route.abort())
            page = context.new_page()
            page.set_default_timeout(10_000)
            page.goto(target, wait_until="domcontentloaded", timeout=15_000)
            if page.locator("main").get_attribute("data-job") != job.id:
                raise ValueError("Mock page identity could not be verified.")
            if page.locator("[data-manual-challenge]").count():
                if submit:
                    raise ValueError("The employer now requires human verification.")
                return {"filled": [], "missing": ["Employer verification challenge requires manual action."]}
            missing, filled = [], []
            filled_values = {}
            fields = page.locator("form input[name], form textarea[name], form select[name]").all()
            signature = [page.locator("form").evaluate("(form) => [form.action, form.method, form.enctype]")]
            if signature[0] != [target, "post", "multipart/form-data"]:
                raise ValueError("The synthetic form action or upload encoding changed.")
            for field in fields:
                name = field.get_attribute("name")
                kind = field.evaluate("(node) => node.type")
                required = field.get_attribute("required") is not None
                signature.append([name, kind, required, field.evaluate(
                    "(field) => [field.value, field.checked ?? false, field.disabled, field.maxLength ?? null]"
                )])
                if name == "resume" and kind == "file":
                    field.set_input_files({"name": "resume.pdf", "mimeType": "application/pdf", "buffer": resume.pdf})
                    filled.append("Resume PDF")
                elif kind in {"text", "email", "tel", "textarea"} and name in values and values[name]:
                    field.fill(values[name])
                    filled.append(FIELDS[name])
                    filled_values[name] = values[name]
                elif required:
                    missing.append(FIELDS.get(name, "Employer-specific required field or consent"))
            form_digest = greenhouse.digest(signature)
            if not submit:
                return {"filled": filled, "missing": missing, "form_digest": form_digest,
                        "pdf_sha256": hashlib.sha256(resume.pdf).hexdigest(), "filled_values": filled_values}
            if missing or app.summary.get("form_digest", form_digest) != form_digest:
                raise ValueError("Required fields changed before submission.")
            page.get_by_role("button", name="Submit simulation").click()
            confirmation = page.locator("[data-confirmation]")
            return confirmation.get_attribute("data-confirmation")
        finally:
            browser.close()


def prepare(job_id, resume_id, profile, mode, eligibility, review_accepted=False, edited_answers=None):
    if eligibility == "INELIGIBLE":
        raise ValueError("Ineligible jobs cannot be prepared.")
    if eligibility != "ELIGIBLE" and not review_accepted:
        raise ValueError("Review and acknowledge the eligibility concerns first.")
    with Session.begin() as db:
        job, resume = db.get(Job, job_id), db.get(Resume, resume_id)
        if not job or not job.available or job.status in {"SKIPPED", "CLOSED"} or not resume or resume.job_id != job_id:
            raise ValueError("The selected role and resume version cannot be prepared.")
        persisted_profile = db.get(Profile, 1)
        if (persisted_profile.facts != profile.facts or persisted_profile.preferences != profile.preferences
                or not still_verified(persisted_profile, resume)):
            raise ValueError("Verified facts changed. Generate a fresh resume.")
        existing = db.scalar(select(Application).where(Application.job_id == job_id))
        if existing and existing.status not in PREPARABLE:
            raise ValueError("This application already has a recorded decision.")
        if existing:
            claimed = db.execute(update(Application).where(
                Application.id == existing.id, Application.status == existing.status
            ).values(status="NEEDS_REVIEW"))
            if claimed.rowcount != 1:
                raise ValueError("Application changed. Refresh the application queue.")
        app = existing or Application(job_id=job_id, resume_id=resume_id, mode=mode, status="NEEDS_REVIEW")
        previous = app.prepared_payload or {}
        answers = edited_answers if edited_answers is not None else previous.get("saved_answers", {})
        if existing and db.scalar(select(SubmissionTask.id).where(SubmissionTask.dispatch_key == existing.id)):
            raise ValueError("This application already has an irreversible dispatch checkpoint.")
        app.prepared_payload = {"saved_answers": answers}
        mock_browser = job.detail["source"] == "mock" and mode == "ASSISTED"
        app.resume_id, app.mode = resume_id, mode
        app.summary = {"eligibility": eligibility, "review_accepted": review_accepted,
                       "simulation": job.detail["source"] == "mock", "browser": mock_browser,
                       "checkpoint": "PREPARING"}
        if mock_browser:
            app.summary = {**app.summary, "mock_key": secrets.token_urlsafe(32),
                           "answers_digest": answers_digest(profile)}
        if not existing:
            db.add(app)
            db.flush()
        db.add(ApplicationEvent(application_id=app.id, status="ELIGIBILITY_CHECKED",
                                message=f"Preparation eligibility: {eligibility}."))
        record(db, app, "NEEDS_REVIEW", "Preparing application review.")
    from .submission import PROVIDERS

    summary = dict(app.summary)
    values = {}
    provider = "manual"
    destination = job.detail.get("apply_url") or job.detail.get("url")
    if mock_browser:
        provider = "mock"
        try:
            destination, values, form = PROVIDERS[provider].prepare(app, job, resume, profile, answers)
            summary.update(form)
        except Exception as exc:
            with Session.begin() as db:
                app = db.get(Application, app.id)
                app.summary = {**app.summary, "checkpoint": "PREPARATION_INTERRUPTED"}
                record(db, app, "FAILED", f"Mock browser preparation failed ({type(exc).__name__}).")
            raise ValueError("Could not prepare the mock form. Check the server origin and Playwright browser.") from exc
    elif mode == "AUTHORIZED_AUTO" and greenhouse.verified_board() and greenhouse.endpoint(job) and eligibility == "ELIGIBLE":
        provider = "greenhouse"
        destination, values, form = PROVIDERS[provider].prepare(app, job, resume, profile, answers)
        summary.update(form)
        summary["integration"] = "greenhouse"
        summary["official_url"] = job.detail.get("apply_url")
    else:
        values = {key: value for key, value in contacts(profile).items() if key != "authorization" and value}
        summary.update({"filled": ["Resume prepared for manual handoff"], "missing": []})
        if mode != "MANUAL" and job.detail["source"] != "mock":
            summary["exception"] = "This employer portal requires manual application."
        if job.detail.get("apply_url"):
            summary["official_url"] = job.detail["apply_url"]
    # The review snapshot and immutable approval refer to the private SQL PDF blob.
    from .resumes import cover_letter
    letter = cover_letter(job, profile.facts) if profile_field(profile.facts, "Name", "personal") else None
    with Session.begin() as db:
        fresh = db.get(Application, app.id)
        if fresh.summary != app.summary or fresh.status != "NEEDS_REVIEW":
            raise ValueError("Application changed during preparation.")
        fresh.summary = {**summary, "checkpoint": "FORM_PREPARED", "custom_answers": bool(answers)}
        fresh.prepared_payload = {
            "application_id": fresh.id, "job_id": job.id, "job": job.detail,
            "resume_id": resume.id, "pdf_sha256": hashlib.sha256(resume.pdf).hexdigest(),
            "pdf_path": f"/api/resumes/{resume.id}/pdf",
            "tex_sha256": hashlib.sha256(resume.tex.encode()).hexdigest(),
            "resume_revision": db.scalar(select(Resume.id).where(Resume.job_id == job.id)
                                         .order_by(Resume.created.desc(), Resume.id.desc()).limit(1)),
            "provider": provider, "destination": destination, "form_digest": summary.get("form_digest"),
            "fields": values, "saved_answers": answers, "pending": summary["missing"],
            "match": job.match, "eligibility": eligibility, "prepared_at": now(), "cover_letter": letter,
        }
        state = "NEEDS_REVIEW" if summary["missing"] else "APPLICATION_PREPARED"
        record(db, fresh, state, "Review required fields." if summary["missing"] else "Application ready for approval.")
        if state == "APPLICATION_PREPARED" and (previous.get("provider") is None or previous.get("pending")):
            db.add(Notification(kind="ready", message="An application is ready for final review."))
        if state == "NEEDS_REVIEW" and summary["missing"] != previous.get("pending"):
            db.add(Notification(kind="action", message="A prepared application needs information."))
        return fresh


def contacts(profile):
    return {key: profile_field(profile.facts, label, "authorization" if key == "authorization" else "personal")
            for key, label in FIELDS.items()}


def answers_digest(profile):
    return hashlib.sha256(json.dumps(contacts(profile), sort_keys=True).encode()).hexdigest()


def submit_simulation(app_id, profile, current_eligibility):
    if current_eligibility == "INELIGIBLE":
        raise ValueError("Current eligibility blocks the application.")
    with Session.begin() as db:
        app = db.get(Application, app_id)
        if not app or not app.summary.get("browser"):
            raise ValueError("Browser submission is available only in the local simulation.")
        job, resume = db.get(Job, app.job_id), db.get(Resume, app.resume_id)
        if not job.available or job.status in {"SKIPPED", "CLOSED"} or not still_verified(profile, resume):
            raise ValueError("The role or verified resume changed after approval.")
        if app.status == "SUBMITTED":
            return app
        if db.scalar(select(SubmissionTask.id).join(FinalApproval).where(FinalApproval.application_id == app_id)):
            raise ValueError("This simulation belongs to the durable final approval workflow.")
        if app.status != "APPROVED":
            raise ValueError("Approve this version through the queue before running the simulation.")
        if (app.summary.get("answers_digest") != answers_digest(profile)
                or app.summary["eligibility"] != current_eligibility):
            raise ValueError("Application answers or eligibility changed after approval. Request changes and prepare again.")
        locked = db.execute(update(Application).where(Application.id == app_id, Application.status == "APPROVED")
                            .values(status="SUBMITTING"))
        if locked.rowcount != 1:
            raise ValueError("Submission already in progress.")
        record(db, app, "SUBMITTING", "Mock browser submission started.")
    try:
        confirmation = browser_run(app, job, resume, contacts(profile), submit=True)
    except Exception:
        confirmation = None
    return reconcile(app_id, confirmation, finished=True)


def reconcile(app_id, confirmation=None, finished=False):
    with Session.begin() as db:
        app = db.get(Application, app_id)
        if not app or app.status not in {"SUBMITTING", "SUBMISSION_UNCERTAIN", "SUBMITTED"}:
            raise ValueError("There is no submission to reconcile.")
        if app.status == "SUBMITTED":
            return app
        latest = db.scalar(select(ApplicationEvent).where(
            ApplicationEvent.application_id == app_id, ApplicationEvent.status == "SUBMITTING"
        ).order_by(ApplicationEvent.created.desc()).limit(1))
        expired = latest and datetime.fromisoformat(latest.created) < datetime.now(UTC) - timedelta(minutes=2)
        if app.summary.get("integration") == "greenhouse":
            if app.status == "SUBMITTING" and expired:
                record(db, app, "SUBMISSION_UNCERTAIN", "No stored confirmation. Verify receipt with the authorized employer.")
            return app
        receipt = db.get(Receipt, app_id)
        if receipt and (not confirmation or secrets.compare_digest(confirmation, receipt.evidence)):
            app.confirmation = receipt.evidence
            record(db, app, "SUBMITTED", "Verified receipt from the local mock employer.")
        elif app.status != "SUBMISSION_UNCERTAIN" and (finished or expired):
            record(db, app, "SUBMISSION_UNCERTAIN", "No matching receipt. Reconcile before retrying.")
        return app


def expected_pdf(data, saved):
    return secrets.compare_digest(hashlib.sha256(data).digest(), hashlib.sha256(saved).digest())
