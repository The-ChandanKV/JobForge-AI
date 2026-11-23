import asyncio
import hmac
import logging
import json
from contextlib import asynccontextmanager, suppress
from datetime import UTC, datetime
from pathlib import PurePath
from typing import Literal
from urllib.parse import quote

import httpx
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from jinja2 import Template
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from starlette.middleware.trustedhost import TrustedHostMiddleware

from . import activation, activation_evidence, employers, greenhouse, submission
from .applications import answers_digest, expected_pdf, prepare, reconcile, record, still_verified, submit_simulation
from .config import ACCESS_TOKEN, MAX_UPLOAD, ROOT
from .intelligence import application_readiness, feedback_for, semantic_cache_key
from .llm import configured
from .matching import analyze, evaluate_saved_job, expired
from .models import Application, ApplicationEvent, FinalApproval, Job, JobDescription, JobSource, Log, Notification, Profile, Receipt, Resume, Run, Session, Settings, SubmissionTask, Upload, now, uid
from .notifications import deliver_review_notifications, record_worker_health
from .profile import extract_text, parse_file, readiness
from .permissions import create_policy
from .providers import clean_html, fold, intake, save_job
from .reliability import cadence, report as reliability_report
from .resumes import cover_letter, generate, recompile
from .schemas import Edit, Fact, Generation, Intake, Options, PolicyRequest, Posting, Preferences, ProfileInput
from .worker import ACTIVE, day_start, future, initialize, lock_settings, queue, worker_status


@asynccontextmanager
async def lifespan(_):
    initialize()

    def check_heartbeat():
        if record_worker_health(Session):
            deliver_review_notifications(Session)

    async def watch():
        while True:
            await asyncio.sleep(30)
            try:
                await asyncio.to_thread(check_heartbeat)
            except Exception:
                logging.getLogger(__name__).exception("Worker health observer failed")

    observer = asyncio.create_task(watch())
    try:
        yield
    finally:
        observer.cancel()
        with suppress(asyncio.CancelledError):
            await observer


app = FastAPI(title="JobForge AI", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "backend", "testserver"])
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
FRONTEND_DIST = ROOT.parent / "frontend" / "dist"
FRONTEND_READY = (FRONTEND_DIST / "index.html").is_file()
if FRONTEND_READY:
    app.mount("/ui-assets", StaticFiles(directory=FRONTEND_DIST), name="ui-assets")


@app.middleware("http")
async def private_responses(request, call_next):
    if request.method not in {"GET", "HEAD"}:
        origin = request.headers.get("origin")
        expected_origin = f"{request.url.scheme}://{request.url.netloc}"
        if request.headers.get("sec-fetch-site") == "cross-site" or (origin and origin != expected_origin):
            return JSONResponse({"detail": "Cross-origin write blocked."}, status_code=403)
    size = request.headers.get("content-length", "")
    if size.isdigit() and int(size) > 6_000_000:
        return JSONResponse({"detail": "Request exceeds 6 MB."}, status_code=413)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Cache-Control"] = "no-store"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self'; "
        "img-src 'self' data:; frame-src 'self'; frame-ancestors 'self'; base-uri 'none'; form-action 'self'"
    )
    return response


def authorized(request: Request):
    if ACCESS_TOKEN:
        auth = request.headers.get("authorization", "").removeprefix("Bearer ")
        cookie = request.cookies.get("jobforge_session", "")
        if not any(hmac.compare_digest(value.encode(), ACCESS_TOKEN.encode()) for value in (auth, cookie)):
            raise HTTPException(401, "Sign in to access JobForge.")


@app.exception_handler(ValueError)
async def handle_value_error(_, exc):
    return JSONResponse({"detail": str(exc)}, status_code=422)


@app.exception_handler(RequestValidationError)
async def handle_validation(_, exc):
    detail = [".".join(str(part) for part in item["loc"]) + " — " + item["msg"] for item in exc.errors()]
    return JSONResponse({"detail": "; ".join(detail)}, status_code=422)


@app.exception_handler(httpx.HTTPError)
async def handle_upstream(_, exc):
    return JSONResponse({"detail": f"Job board request failed ({type(exc).__name__})."}, status_code=502)


@app.exception_handler(IntegrityError)
async def handle_conflict(_, exc):
    return JSONResponse({"detail": "Concurrent record update. Refresh and try again."}, status_code=409)


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return FileResponse(ROOT / "static" / "favicon.ico", media_type="image/x-icon")


@app.get("/health")
def health():
    with Session() as db:
        db.get(Settings, 1)
    return {"status": "ok"}


@app.get("/")
@app.get("/jobs")
@app.get("/pipeline")
@app.get("/resume-studio")
@app.get("/automation")
@app.get("/approvals")
@app.get("/exceptions")
@app.get("/history")
@app.get("/analytics")
@app.get("/settings")
@app.get("/profile")
@app.get("/notifications")
@app.get("/intelligence")
@app.get("/activation")
@app.get("/legacy")
def dashboard(request: Request):
    try:
        authorized(request)
    except HTTPException:
        return FileResponse(ROOT / "static" / "login.html")
    frontend = FRONTEND_DIST / "index.html"
    if request.url.path != "/legacy" and FRONTEND_READY and frontend.is_file():
        return FileResponse(frontend)
    return FileResponse(ROOT / "static" / "index.html")


@app.post("/login")
def login(request: Request, token: str = Form(max_length=512)):
    if not ACCESS_TOKEN or not hmac.compare_digest(token.encode(), ACCESS_TOKEN.encode()):
        raise HTTPException(401, "Invalid access token.")
    response = RedirectResponse("/", status_code=303)
    response.set_cookie("jobforge_session", ACCESS_TOKEN, httponly=True, samesite="strict",
                        secure=request.url.scheme == "https")
    return response


def row_item(row, fields):
    return {field: getattr(row, field) for field in fields.split()}


def job_item(row, include_description=True):
    detail = row.detail if include_description else {k: v for k, v in row.detail.items() if k != "description"}
    return {**row_item(row, "id company role match status created verified automation"), **detail,
            "available": row.available and not expired(row.detail.get("deadline"))}


def resume_item(row):
    return row_item(row, "id job_id parent_id template tex report created")


def application_item(row):
    return {**row_item(row, "id job_id resume_id mode status confirmation created"),
            "review_status": submission.readiness(row),
            "submission_method": (row.prepared_payload or {}).get("provider"),
            "summary": {k: v for k, v in row.summary.items() if k not in {"mock_key", "answers_digest"}}}


AUTH = [Depends(authorized)]


@app.get("/api/reliability", dependencies=AUTH)
def reliability():
    return reliability_report()


@app.get("/api/state", dependencies=AUTH)
def state():
    with Session() as db:
        profile, settings = db.get(Profile, 1), db.get(Settings, 1)
        options = Options.model_validate(settings.options)
        provider, model = configured(options)
        jobs = db.scalars(select(Job).order_by(Job.verified.desc(), Job.id.desc())).all()
        apps = db.scalars(select(Application).order_by(Application.created.desc())).all()
        start = day_start(options.timezone)
        today_runs = db.scalars(select(Run).where(Run.finished >= start, Run.status.in_(
            ["COMPLETED", "COMPLETED_WITH_ERRORS", "FAILED"]
        ))).all()
        daily = {key: sum(row.report.get(key, 0) for row in today_runs)
                 for key in ("scanned", "filtered", "discovered", "compiled", "prepared", "submitted")}
        daily.update({"runs": len(today_runs), "failed_runs": sum(row.status == "FAILED" for row in today_runs),
                      "new_jobs": sum(job.created >= start for job in jobs),
                      "confirmed_today": db.scalar(select(func.count()).select_from(ApplicationEvent).where(
                          ApplicationEvent.created >= start, ApplicationEvent.status == "SUBMITTED"
                      ))})
        return {
            "profile": row_item(profile, "facts preferences"),
            "profile_readiness": readiness(profile.facts),
            "options": options.model_dump(mode="json"),
            "provider": provider, "model": model,
            "authorized_board": greenhouse.verified_board(),
            "worker": worker_status(db, options),
            "daily": daily,
            "resume_count": db.scalar(select(func.count()).select_from(Resume)),
            "unread_notifications": db.scalar(select(func.count()).select_from(Notification).where(Notification.read.is_(False))),
            "next_run": settings.next_run if options.enabled else None,
            "jobs": [job_item(job, include_description=False) for job in jobs],
            "applications": [application_item(item) for item in apps],
            "runs": [row_item(row, "id status trigger started finished canceled attempts report created")
                     for row in db.scalars(select(Run).order_by(Run.created.desc(), Run.id.desc()).limit(35))],
            "logs": [row_item(row, "id kind message detail created")
                     for row in db.scalars(select(Log).order_by(Log.created.desc(), Log.id.desc()).limit(50))],
        }


@app.put("/api/profile", dependencies=AUTH)
def update_profile(payload: ProfileInput):
    with Session.begin() as db:
        submission.lock(db)
        row = db.get(Profile, 1)
        old = {fact["id"]: fact for fact in row.facts}
        facts = []
        for value in payload.facts:
            fact = value.model_dump()
            previous = old.get(fact["id"])
            if previous and any(fact[key] != previous[key] for key in ("value", "category", "label")):
                fact["source"] = "manual edit"
                fact["excerpt"] = previous["excerpt"]
            elif previous:
                fact["source"], fact["excerpt"] = previous["source"], previous["excerpt"]
            else:
                fact["source"], fact["excerpt"] = "manual", ""
            facts.append(fact)
        row.facts = facts
        row.preferences = payload.preferences.model_dump()
        refresh_profile_matches(db, row)
        return row_item(row, "facts preferences")


def refresh_profile_matches(db, row):
    threshold = Options.model_validate(db.get(Settings, 1).options).min_match_score
    for job in db.scalars(select(Job)):
        evaluate_saved_job(job, row.facts, Preferences.model_validate(row.preferences), threshold)
    queued = db.execute(select(SubmissionTask, Application).select_from(SubmissionTask)
                        .join(FinalApproval, SubmissionTask.approval_id == FinalApproval.id)
                        .join(Application, FinalApproval.application_id == Application.id)
                        .where(SubmissionTask.status.in_(["QUEUED", "VALIDATING"]))).all()
    for task, app in queued:
        try:
            submission.validate_snapshot(db, submission.context_for(db, app))
        except submission.ReviewChanged as exc:
            submission.stop_preflight(db, app, task, "profile_review_changed", str(exc))


class FactBatch(BaseModel):
    facts: list[Fact] = Field(min_length=1, max_length=250)


@app.post("/api/profile/verify", dependencies=AUTH)
def verify_profile_facts(payload: FactBatch):
    with Session.begin() as db:
        submission.lock(db)
        row = db.get(Profile, 1)
        indexed = {fact["id"]: fact for fact in row.facts}
        selected = {fact.id: fact.model_dump() for fact in payload.facts}
        if len(selected) != len(payload.facts):
            raise ValueError("Select each fact once.")
        for identity, reviewed in selected.items():
            existing = indexed.get(identity)
            evidence = ("category", "label", "value", "source", "excerpt")
            if (not existing or existing.get("unsupported") or not existing["source"].startswith("upload:")
                    or not existing["excerpt"] or any(existing[key] != reviewed[key] for key in evidence)):
                raise HTTPException(409, "A selected source fact changed. Refresh and review the current evidence.")
        count = sum(not indexed[identity]["verified"] for identity in selected)
        if count:
            row.facts = [{**fact, "verified": True} if fact["id"] in selected else fact for fact in row.facts]
            refresh_profile_matches(db, row)
        return {"verified": count}


class ActivationPreferences(BaseModel):
    roles: list[str] = Field(max_length=40)
    locations: list[str] = Field(max_length=40)
    work_modes: list[Literal["remote", "hybrid", "onsite"]]
    employment: list[str] = Field(max_length=20)


@app.put("/api/activation/preferences", dependencies=AUTH)
def activation_preferences(payload: ActivationPreferences):
    with Session.begin() as db:
        submission.lock(db)
        row = db.get(Profile, 1)
        updated = {**row.preferences, **payload.model_dump()}
        row.preferences = Preferences.model_validate(updated).model_dump()
        refresh_profile_matches(db, row)
        return {"preferences_saved": True}


class PersonalActivation(BaseModel):
    revision: str = Field(pattern=r"^[0-9a-f]{64}$")
    fact_ids: list[str] = Field(default_factory=list, max_length=250)
    preferences: ActivationPreferences
    maximum_mandatory_years: int | None = Field(default=None, ge=0, le=30)
    board_keys: list[str] = Field(min_length=1, max_length=10)


@app.get("/api/activation/review", dependencies=AUTH)
def personal_activation_review():
    with Session() as db:
        return activation_evidence.review(db, db.get(Profile, 1))[0]


@app.post("/api/activation/confirm", status_code=202, dependencies=AUTH)
def confirm_personal_activation(payload: PersonalActivation):
    with Session.begin() as db:
        settings = lock_settings(db)
        if db.scalar(select(Run.id).where(Run.status.in_(ACTIVE)).limit(1)):
            raise HTTPException(409, "A run is already pending. Wait for the worker to finish.")
        if not settings.options.get("enabled"):
            raise ValueError("Resume the hourly schedule in Automation before activating.")
        row = db.get(Profile, 1)
        review, records = activation_evidence.review(db, row)
        if payload.revision != review["revision"]:
            raise HTTPException(409, "The profile or originals changed. Refresh the activation review.")
        chosen = set(payload.fact_ids)
        if len(chosen) != len(payload.fact_ids):
            raise ValueError("Select each fact once.")
        items = {item["id"]: item for item in review["groups"]}
        if any(identity not in items or items[identity]["verified"] or not items[identity]["evidence"]
               for identity in chosen):
            raise HTTPException(409, "A selected fact is no longer available for verification.")
        conflicts = {items[identity]["conflict"] for identity in chosen} - {None}
        if any(sum(item["conflict"] == conflict and (item["verified"] or item["id"] in chosen)
                   for item in items.values()) > 1 for conflict in conflicts):
            raise ValueError("Resolve the conflicting credential or link before confirming.")
        existing = {fact["id"] for fact in row.facts}
        added = [{**records[identity], "verified": True} for identity in payload.fact_ids if identity not in existing]
        if len(row.facts) + len(added) > 250:
            raise ValueError("Remove stale draft facts in Profile before adding more evidence.")
        row.facts = [{**fact, "verified": True} if fact["id"] in chosen else fact for fact in row.facts] + added
        updated = {**row.preferences, **payload.preferences.model_dump()}
        updated["activation_confirmed"] = True
        if "maximum_mandatory_years" in payload.model_fields_set:
            updated["maximum_mandatory_years"] = payload.maximum_mandatory_years
        row.preferences = Preferences.model_validate(updated).model_dump()
        identities = enable_verified_boards(db, settings, EmployerBatch(keys=payload.board_keys).unique())
        refresh_profile_matches(db, row)
        setup, sources = activation.plan(db, settings)
        if not setup["ready"]:
            raise ValueError("Complete activation before running: " + ", ".join(
                label for label, ready in setup["checks"].items() if not ready) + ".")
        if not identities.issubset({(source.provider, source.board.casefold()) for source in sources}):
            raise ValueError("Verify every selected board before running.")
        run = queue(db, "activation")
        run.report = {"activation_boards": sorted(identities)}
        return {"id": run.id, "status": run.status}


@app.get("/api/activation", dependencies=AUTH)
def activation_status():
    with Session() as db:
        return activation.snapshot(db)


@app.post("/api/activation/run", status_code=202, dependencies=AUTH)
def start_activation():
    with Session.begin() as db:
        settings = lock_settings(db)
        setup, sources = activation.plan(db, settings)
        if not setup["ready"]:
            raise ValueError("Complete activation before running: " + ", ".join(
                label for label, ready in setup["checks"].items() if not ready) + ".")
        if db.scalar(select(Run.id).where(Run.status.in_(ACTIVE)).limit(1)):
            raise HTTPException(409, "A run is already pending. Wait for the worker to finish.")
        run = queue(db, "activation")
        run.report = {"activation_boards": [[source.provider, source.board.casefold()] for source in sources]}
        return {"id": run.id, "status": run.status}


@app.post("/api/profile/upload", dependencies=AUTH)
def upload(file: UploadFile = File()):
    name = PurePath((file.filename or "").replace("\\", "/")).name[:255]
    data = file.file.read(MAX_UPLOAD + 1)
    facts = parse_file(name, data)
    with Session.begin() as db:
        submission.lock(db)
        already = db.scalar(select(Upload.id).where(Upload.blob == data).order_by(Upload.created).limit(1))
        if already:
            return {"imported": 0, "upload": already, "already_imported": True}
        row = db.get(Profile, 1)
        if len(row.facts) + len(facts) > 250:
            raise ValueError("Profile holds up to 250 facts. Remove stale drafts before importing.")
        original = Upload(name=name, blob=data)
        db.add(original)
        db.flush()
        detected = [f.model_copy(update={"source": f"upload:{original.id}"}).model_dump() for f in facts]
        row.facts = [*row.facts, *detected]
        return {"imported": len(detected), "upload": original.id}


@app.get("/api/profile/uploads", dependencies=AUTH)
def list_uploads():
    with Session() as db:
        rows = db.execute(select(Upload.id, Upload.name, Upload.created)
                          .order_by(Upload.created.desc(), Upload.id)).mappings()
        return [dict(row) for row in rows]


@app.get("/api/profile/uploads/{upload_id}/text", dependencies=AUTH)
def upload_text(upload_id: str):
    with Session() as db:
        upload = required(db, Upload, upload_id)
        name, blob = upload.name, upload.blob
    return {"name": name, "text": extract_text(name, blob)}


@app.get("/api/profile/uploads/{upload_id}", dependencies=AUTH)
def download_upload(upload_id: str):
    with Session() as db:
        upload = required(db, Upload, upload_id)
        filename = quote(upload.name, safe="")
        return Response(upload.blob, media_type="application/octet-stream",
                        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"})


class MonitorEmployer(BaseModel):
    enabled: bool
    group: Literal["priority", "regular", "excluded"]


class EmployerBatch(BaseModel):
    keys: list[str] = Field(min_length=1, max_length=10)

    def unique(self):
        if len(set(self.keys)) != len(self.keys):
            raise ValueError("Select each employer once.")
        for key in self.keys:
            employers.catalog_source(key)
        return self.keys


@app.post("/api/employers/verify-selected", dependencies=AUTH)
def verify_employer_batch(request: EmployerBatch):
    result = {}
    for key in request.unique():
        try:
            result[key] = employers.verify_catalog_source(Session, key)
        except (ValueError, httpx.HTTPError, KeyError, TypeError) as exc:
            result[key] = {"error": str(exc) if isinstance(exc, ValueError) else type(exc).__name__}
    return result


@app.post("/api/employers/enable-selected", dependencies=AUTH)
def enable_employer_batch(request: EmployerBatch):
    keys = request.unique()
    with Session.begin() as db:
        settings = lock_settings(db)
        enable_verified_boards(db, settings, keys)
    return {"enabled": len(keys)}


def enable_verified_boards(db, settings, keys):
    identities = set()
    preferences = Preferences.model_validate(db.get(Profile, 1).preferences)
    priorities = {name.casefold() for name in preferences.priority_companies}
    excluded = {name.casefold() for name in preferences.excluded_companies}
    for key in keys:
        source = employers.catalog_source(key)
        identities.add((source.provider, source.board.casefold()))
        company = source.company.casefold()
        group = "excluded" if company in excluded else "priority" if company in priorities else "regular"
        employers.update_monitor(db, settings, key, True, group)
    return identities


@app.get("/api/employers", dependencies=AUTH)
def discover_employers(company: str = "", industry: str = "", location: str = "", role: str = ""):
    with Session() as db:
        options = Options.model_validate(db.get(Settings, 1).options)
        return employers.company_records(db, options, (company, industry, location, role))


@app.post("/api/employers/{key}/verify", dependencies=AUTH)
def verify_employer(key: str):
    return employers.verify_catalog_source(Session, key)


@app.put("/api/employers/{key}/monitor", dependencies=AUTH)
def monitor_employer(key: str, request: MonitorEmployer):
    with Session.begin() as db:
        employers.update_monitor(db, lock_settings(db), key, request.enabled, request.group)
    return {"enabled": request.enabled, "group": request.group}


@app.put("/api/settings", dependencies=AUTH)
def settings_update(options: Options):
    if options.auto_submit or options.automation_mode == "AUTHORIZED_AUTO_SUBMIT":
        raise ValueError("Employers require final approval for each exact prepared application.")
    if ((options.mode == "AUTHORIZED_AUTO" or not options.dry_run or options.auto_submit)
            and (not greenhouse.verified_board() or options.mode != "AUTHORIZED_AUTO")):
        raise ValueError("Configure an authorized employer integration before allowing real submission.")
    if options.auto_submit and options.dry_run:
        raise ValueError("Disable dry-run explicitly before allowing scheduled employer submissions.")
    with Session.begin() as db:
        row = lock_settings(db)
        previous = Options.model_validate(row.options)
        earlier = {(source.provider, source.board.casefold()) for source in previous.sources if source.enabled}
        for source in options.sources:
            identity = (source.provider, source.board.casefold())
            if (source.enabled and source.provider in {"smartrecruiters", "recruitee"} and identity not in earlier
                    and not employers.recently_verified(db, *identity)):
                raise ValueError("Verify this employer in the discovery catalog before enabling its board.")
        options.submission_policy = previous.submission_policy
        row.options = options.model_dump(mode="json")
        if previous.interval_minutes != options.interval_minutes or previous.enabled != options.enabled:
            row.next_run = future(options.interval_minutes)
            cadence(db, row)
        if previous.min_match_score != options.min_match_score:
            profile = db.get(Profile, 1)
            preferences = Preferences.model_validate(profile.preferences)
            for job in db.scalars(select(Job)):
                evaluate_saved_job(job, profile.facts, preferences, options.min_match_score)
        return row.options


@app.post("/api/submission-policy", dependencies=AUTH)
def save_submission_policy(payload: PolicyRequest):
    with Session.begin() as db:
        settings = lock_settings(db)
        profile = db.get(Profile, 1)
        candidates = db.execute(select(Job, Application).join(Application).where(
            Application.status.in_(["APPLICATION_PREPARED", "APPROVED"]), Job.available
        )).all()
        prepared = {
            key: (job, application) for job, application in candidates
            if (key := job.detail.get("source_key", job.source_key)) in payload.job_keys
            and application.summary.get("integration") == "greenhouse"
            and application.summary.get("form_digest") and not application.summary.get("missing")
        }
        policy = create_policy(payload, profile, prepared)
        settings.options = {**settings.options, "submission_policy": policy.model_dump(mode="json"), "auto_submit": False}
        db.add(Log(kind="policy", message="Submission policy recorded", detail={"policy_id": policy.id}))
        return policy


@app.delete("/api/submission-policy", dependencies=AUTH)
def revoke_submission_policy():
    with Session.begin() as db:
        settings = lock_settings(db)
        options = Options.model_validate(settings.options)
        if options.submission_policy and not options.submission_policy.revoked:
            options.submission_policy.revoked = datetime.now(UTC)
            db.add(Log(kind="policy", message="Submission policy revoked", detail={"policy_id": options.submission_policy.id}))
        options.auto_submit = False
        options.dry_run = True
        options.automation_mode = "AUTONOMOUS_PREPARATION"
        settings.options = options.model_dump(mode="json")
        return settings.options


def demo_fact(category, label, value):
    return {"id": uid(), "category": category, "label": label, "value": value,
            "verified": True, "source": "synthetic fixture", "excerpt": value}


@app.post("/api/demo", dependencies=AUTH)
def demo():
    with Session.begin() as db:
        profile = db.get(Profile, 1)
        if profile.facts:
            raise HTTPException(409, "The synthetic fixture requires an empty profile.")
        entries = [
            ("personal", "Name", "Jordan Rao"),
            ("personal", "Email", "jordan@example.test"),
            ("personal", "Phone", "+1 555 0100"),
            ("authorization", "Mock screening answer", "This is a synthetic test. No real work authorization is asserted."),
            ("skill", "Language", "Python"), ("skill", "Database", "SQL"), ("skill", "Framework", "FastAPI"),
            ("project", "API Observatory", "Built a Python and FastAPI service to track API health."),
            ("project", "Inventory Lab", "Designed SQL queries and tests for a sample inventory database."),
            ("experience", "Sample internship", "Wrote Python unit tests for internal web services."),
            ("education", "Degree", "Bachelor of Science in Computing with Python coursework."),
        ]
        profile.facts = [demo_fact(*entry) for entry in entries]
        profile.preferences = Preferences(roles=["Backend Engineer"]).model_dump()
        settings = lock_settings(db)
        options = Options.model_validate(settings.options)
        if not any(s.provider == "mock" and s.board == "demo" for s in options.sources):
            options.sources.append({"provider": "mock", "board": "demo", "company": "Vertex Labs (synthetic)"})
        settings.options = Options.model_validate({**settings.options, "sources": [
            s.model_dump() if hasattr(s, "model_dump") else s for s in options.sources
        ]}).model_dump(mode="json")
        return {"run": queue(db, "manual").id}


@app.post("/api/runs", dependencies=AUTH)
def run_now():
    with Session.begin() as db:
        return {"id": queue(db, "manual").id}


@app.post("/api/runs/{run_id}/cancel", dependencies=AUTH)
def cancel_run(run_id: str):
    with Session.begin() as db:
        run = required(db, Run, run_id)
        if run.status not in {"QUEUED", "RUNNING"}:
            raise ValueError("Only queued or running requests can be canceled.")
        run.canceled = True
        return {"canceled": True}


def required(db, cls, key):
    row = db.get(cls, key)
    if row is None:
        raise HTTPException(404, "Record not found.")
    return row


@app.post("/api/jobs", dependencies=AUTH)
def add_job(payload: Intake):
    with Session() as db:
        opts = Options.model_validate(db.get(Settings, 1).options)
    posting = intake(payload, opts.sources)
    with Session.begin() as db:
        profile = db.get(Profile, 1)
        row = save_job(db, posting)
        row.match = analyze(posting, profile.facts, Preferences.model_validate(profile.preferences), opts.min_match_score)
        return job_item(row)


@app.get("/api/jobs/{job_id}", dependencies=AUTH)
def job_detail(job_id: str):
    with Session() as db:
        return job_item(required(db, Job, job_id))


class RecommendationFeedback(BaseModel):
    value: Literal["good", "bad", "not_interested", "already_applied", "wrong_level"]


@app.post("/api/jobs/{job_id}/feedback", dependencies=AUTH)
def job_feedback(job_id: str, request: RecommendationFeedback):
    with Session.begin() as db:
        lock_settings(db)
        job = required(db, Job, job_id)
        feedback = feedback_for(db, job)
        if not feedback or feedback["value"] != request.value:
            db.add(Log(kind="recommendation_feedback", message="Job recommendation feedback recorded",
                       detail={"job_id": job.id, "value": request.value,
                               "company": fold(job.company), "role": fold(job.role)}))
        if request.value in {"not_interested", "already_applied", "wrong_level"} and job.status != "CLOSED":
            job.status = "SKIPPED"
    return {"value": request.value}


@app.get("/api/jobs/{job_id}/intelligence", dependencies=AUTH)
def job_intelligence(job_id: str):
    with Session() as db:
        job = required(db, Job, job_id)
        profile = db.get(Profile, 1)
        application = db.scalar(select(Application).where(Application.job_id == job_id))
        resume = db.get(Resume, application.resume_id) if application else db.scalar(select(Resume).where(
            Resume.job_id == job_id).order_by(Resume.created.desc(), Resume.id.desc()).limit(1))
        feedback = feedback_for(db, job)
        dispatch = bool(application and submission.provider_available(submission.context_for(db, application)))
        readiness_summary = application_readiness(job, profile, resume, application, can_dispatch=dispatch,
                                                 already_applied=bool(feedback and feedback["value"] == "already_applied"))
        evidence = [row_item(source, "key canonical_url verified available") for source in db.scalars(
            select(JobSource).where(JobSource.job_id == job.id).order_by(JobSource.verified.desc())
        )]
        public = job_item(job)
        cached = public["match"].get("semantic")
        model = Options.model_validate(db.get(Settings, 1).options).semantic_model
        if cached and (not model or cached.get("key") != semantic_cache_key(job, model, profile.facts)):
            public["match"] = {key: value for key, value in public["match"].items() if key != "semantic"}
        return {"job": public, "readiness": readiness_summary, "sources": evidence,
                "resume": row_item(resume, "id template created") if resume else None,
                "application_id": application.id if application else None, "feedback": feedback["value"] if feedback else None}


class JobAction(BaseModel):
    status: Literal["SHORTLISTED", "SKIPPED", "DISCOVERED"]


@app.put("/api/jobs/{job_id}/status", dependencies=AUTH)
def job_status(job_id: str, action: JobAction):
    with Session.begin() as db:
        job = required(db, Job, job_id)
        job.status = action.status
        return job_item(job)


@app.post("/api/jobs/{job_id}/retry", dependencies=AUTH)
def retry_job(job_id: str):
    with Session.begin() as db:
        job = required(db, Job, job_id)
        if job.automation.get("state") not in {"EXCEPTION", "RETRY_WAIT"}:
            raise ValueError("This job has no failed internal task to retry.")
        job.automation = {}
        job.status = "DISCOVERED"
        profile, settings = db.get(Profile, 1), db.get(Settings, 1)
        options = Options.model_validate(settings.options)
        evaluate_saved_job(job, profile.facts, Preferences.model_validate(profile.preferences), options.min_match_score)
        db.add(Log(kind="retry", message="Operator reset the internal retry budget", detail={"job_id": job.id}))
        return job_item(job)


@app.get("/api/jobs/{job_id}/resumes", dependencies=AUTH)
def versions(job_id: str):
    with Session() as db:
        required(db, Job, job_id)
        return [resume_item(r) for r in db.scalars(
            select(Resume).where(Resume.job_id == job_id).order_by(Resume.created.desc(), Resume.id.desc())
        )]


@app.post("/api/jobs/{job_id}/resumes", dependencies=AUTH)
def new_resume(job_id: str, payload: Generation):
    with Session.begin() as db:
        job = required(db, Job, job_id)
        if payload.parent_id and required(db, Resume, payload.parent_id).job_id != job_id:
            raise ValueError("Parent resume belongs to a different job.")
        profile, settings = db.get(Profile, 1), db.get(Settings, 1)
        options = Options.model_validate(settings.options)
        job.match = analyze(Posting.model_validate(job.detail), profile.facts,
                            Preferences.model_validate(profile.preferences), options.min_match_score)
        resume = generate(db, job, profile.facts, options, payload)
        db.execute(update(Job).where(Job.id == job.id, Job.status.not_in(["SKIPPED", "CLOSED"]))
                   .values(status="RESUME_READY"))
        return resume_item(resume)


@app.get("/api/jobs/{job_id}/letter", dependencies=AUTH)
def letter(job_id: str):
    with Session() as db:
        job, profile = required(db, Job, job_id), db.get(Profile, 1)
        return {"content": cover_letter(job, profile.facts)}


@app.post("/api/resumes/{resume_id}/compile", dependencies=AUTH)
def compile_edit(resume_id: str, request: Edit):
    with Session.begin() as db:
        row = required(db, Resume, resume_id)
        if not still_verified(db.get(Profile, 1), row):
            raise ValueError("Verify the original fact set or regenerate before compiling.")
        return resume_item(recompile(db, row, request.tex))


@app.post("/api/resumes/{resume_id}/restore", dependencies=AUTH)
def restore(resume_id: str):
    with Session.begin() as db:
        row = required(db, Resume, resume_id)
        if not still_verified(db.get(Profile, 1), row):
            raise ValueError("This version contains facts that are no longer verified.")
        version = Resume(job_id=row.job_id, parent_id=row.id, template=row.template, tex=row.tex,
                         pdf=row.pdf, report=row.report)
        db.add(version)
        db.flush()
        return resume_item(version)


@app.get("/api/resumes/{resume_id}/{kind}", dependencies=AUTH)
def download_resume(resume_id: str, kind: Literal["tex", "pdf"], download: bool = False):
    with Session() as db:
        row = required(db, Resume, resume_id)
        return Response(row.pdf if kind == "pdf" else row.tex,
                        media_type="application/pdf" if kind == "pdf" else "text/plain",
                        headers={"Content-Disposition": f'{"attachment" if download else "inline"}; filename="resume.{kind}"'})


class PrepareInput(BaseModel):
    resume_id: str
    review_accepted: bool = False


def current_eligibility(job, profile, options):
    return analyze(Posting.model_validate(job.detail), profile.facts, Preferences.model_validate(profile.preferences),
                   options.min_match_score)["eligibility"]


@app.post("/api/jobs/{job_id}/prepare", dependencies=AUTH)
def prepare_application(job_id: str, payload: PrepareInput):
    with Session.begin() as db:
        submission.lock(db)
        app = db.scalar(select(Application).where(Application.job_id == job_id))
        if app and app.status == "APPROVED" and app.summary.get("durable_approval"):
            submission.invalidate_before_edit(db, app)
    with Session() as db:
        job, profile = required(db, Job, job_id), db.get(Profile, 1)
        options = Options.model_validate(db.get(Settings, 1).options)
        eligibility = current_eligibility(job, profile, options)
    return application_item(prepare(job_id, payload.resume_id, profile, options.mode, eligibility, payload.review_accepted))


class Decision(BaseModel):
    action: Literal["approve", "reject", "changes", "simulate", "submit_authorized", "reconcile", "interview", "offer",
                    "employer_rejection", "closed", "record_confirmation"]
    note: str = Field(default="", max_length=240)
    reason: Literal["not_interested", "wrong_location", "too_senior", "salary_mismatch",
                    "already_applied", "incorrect_match", "other"] | None = None
    block_company: bool = False
    exclude_senior: bool = False


@app.post("/api/applications/{app_id}/decision", dependencies=AUTH)
def decision(app_id: str, payload: Decision):
    if payload.action == "submit_authorized":
        raise ValueError("Open the application review and use Approve & Submit for this exact payload.")
    if payload.action in {"simulate", "reconcile"}:
        if payload.action == "reconcile":
            with Session.begin() as db:
                submission.lock(db)
                item = required(db, Application, app_id)
                task = submission.task_for(db, app_id)
                if task and task.dispatch_key:
                    if item.status == "SUBMISSION_UNCERTAIN" and item.summary.get("simulation"):
                        context = submission.context_for(db, item)
                        evidence = submission.PROVIDERS["mock"].verify_submission(db, context, None)
                        if evidence:
                            submission.complete(db, context, task, evidence, "manual_reconciliation")
                    return application_item(item)
            return application_item(reconcile(app_id))
        with Session() as db:
            application, profile = required(db, Application, app_id), db.get(Profile, 1)
            job, opts = db.get(Job, application.job_id), Options.model_validate(db.get(Settings, 1).options)
            eligibility = current_eligibility(job, profile, opts)
        return application_item(submit_simulation(app_id, profile, eligibility))
    with Session.begin() as db:
        submission.lock(db)
        application = required(db, Application, app_id)
        action, original_status = payload.action, application.status
        if action == "approve":
            if application.status != "APPLICATION_PREPARED":
                raise ValueError("Complete preparation before approving.")
            job, profile = db.get(Job, application.job_id), db.get(Profile, 1)
            opts = Options.model_validate(db.get(Settings, 1).options)
            eligibility = current_eligibility(job, profile, opts)
            if (eligibility == "INELIGIBLE" or not job.available or job.status in {"SKIPPED", "CLOSED"}
                    or not still_verified(profile, db.get(Resume, application.resume_id))):
                raise ValueError("Current job or profile data blocks approval.")
            if application.summary["eligibility"] != eligibility:
                raise ValueError("Eligibility has changed. Prepare and review the application again.")
            if application.summary.get("browser") and application.summary.get("answers_digest") != answers_digest(profile):
                raise ValueError("Verified answers changed. Prepare and review the application again.")
            if application.prepared_payload and application.prepared_payload.get("saved_answers"):
                raise ValueError("Review the edited answers and use Approve & Submit.")
            status, message = "APPROVED", "User approved the selected resume and preparation summary."
        elif action == "record_confirmation":
            if (application.summary.get("simulation") or application.status not in {
                "APPROVED", "APPLICATION_PREPARED", "READY_FOR_REVIEW", "NEEDS_MANUAL_ACTION", "SUBMISSION_UNCERTAIN"
            }
                    or not 3 <= len(payload.note.strip()) <= 175):
                raise ValueError("An approved real application or uncertain receipt and a confirmation reference are required.")
            application.confirmation = f"User recorded: {payload.note.strip()}"
            application.summary = {**application.summary, "external_confirmation": True, "confirmed_at": now()}
            task = submission.task_for(db, app_id)
            if task and task.status in {"QUEUED", "VALIDATING"}:
                submission.invalidate_before_edit(db, application)
                original_status = application.status
            elif task and task.status == "SUBMISSION_UNCERTAIN":
                task.status, task.result, task.finished_at = "SUBMITTED", "user_recorded_confirmation", now()
            status, message = "SUBMITTED", "User recorded employer confirmation evidence."
        elif action in {"reject", "changes"}:
            if application.status not in {"APPLICATION_PREPARED", "READY_FOR_REVIEW", "NEEDS_REVIEW", "NEEDS_MANUAL_ACTION", "APPROVED", "FAILED"}:
                raise ValueError("This application is outside the review stage.")
            submission.invalidate_before_edit(db, application)
            original_status = application.status
            status = "REJECTED_BY_USER" if action == "reject" else "NEEDS_REVIEW"
            message = "User declined this application." if action == "reject" else "User requested changes."
            if action == "reject" and (payload.reason or payload.block_company or payload.exclude_senior):
                job = required(db, Job, application.job_id)
                application.summary = {**application.summary, "rejection_reason": payload.reason}
                if payload.reason:
                    message += " Reason: " + payload.reason.replace("_", " ") + "."
                if payload.block_company or payload.exclude_senior:
                    profile = db.get(Profile, 1)
                    preferences = Preferences.model_validate(profile.preferences)
                    if payload.block_company and job.company.casefold() not in {company.casefold() for company in preferences.excluded_companies}:
                        preferences.excluded_companies.append(job.company)
                    if payload.exclude_senior:
                        preferences.exclude_senior_roles = True
                    profile.preferences = preferences.model_dump()
        else:
            if application.status not in {"APPROVED", "SUBMITTED", "INTERVIEW", "OFFER"}:
                raise ValueError("Tracking updates require an approved or submitted application.")
            status = {"interview": "INTERVIEW", "offer": "OFFER", "employer_rejection": "REJECTED", "closed": "CLOSED"}[action]
            message = "User recorded an employer status update."
        with db.no_autoflush:
            locked = db.execute(update(Application).where(
                Application.id == app_id, Application.status == original_status
            ).values(status=status))
        if locked.rowcount != 1:
            raise HTTPException(409, "Application changed. Refresh the queue.")
        record(db, application, status, message if action == "record_confirmation" else f"{message} {payload.note}".strip())
        return application_item(application)


class ApprovalClick(BaseModel):
    application_id: str
    payload_hash: str = Field(pattern=r"^[a-f0-9]{64}$")


class BulkReview(BaseModel):
    reviews: list[ApprovalClick] = Field(min_length=1, max_length=20)


@app.get("/api/applications/{app_id}/review", dependencies=AUTH)
def application_review(app_id: str):
    with Session() as db:
        item = required(db, Application, app_id)
        context = submission.context_for(db, item)
        task = submission.task_for(db, app_id)
        payload = item.prepared_payload or {}
        complete = bool(payload.get("provider"))
        approvable, refusal = False, None
        if complete and context.payload["provider"] in submission.PROVIDERS and item.status in submission.READY:
            try:
                submission.validate_snapshot(db, context)
                approvable = not task or not task.dispatch_key and task.status not in submission.ACTIVE
            except submission.ReviewChanged as exc:
                refusal = str(exc)
        original = db.scalar(select(JobDescription.description).where(JobDescription.job_id == context.job.id)
                    .order_by(JobDescription.created.desc(), JobDescription.id.desc()).limit(1))
        return {"application": application_item(item), "job": job_item(context.job),
                "payload": payload, "payload_hash": submission.digest(payload) if complete else None,
                "resume": row_item(context.resume, "id template created"),
                "original_description": clean_html(original) if original else original,
                "readiness": submission.readiness(item), "approvable": approvable, "refusal": refusal,
                "task": submission.visible_task(db, task),
                "readiness_details": application_readiness(context.job, context.profile, context.resume, item,
                                                           can_dispatch=submission.provider_available(context))}


@app.post("/api/applications/{app_id}/approve-submit", dependencies=AUTH, status_code=202)
def approve_submit(app_id: str, request: ApprovalClick):
    if app_id != request.application_id:
        raise ValueError("The approval belongs to another application.")
    with Session.begin() as db:
        submission.lock(db)
        task = submission.approve(db, required(db, Application, app_id), request.payload_hash)
        return submission.visible_task(db, task)


@app.post("/api/applications/bulk-review", dependencies=AUTH, status_code=202)
def bulk_approve(request: BulkReview):
    if len({row.application_id for row in request.reviews}) != len(request.reviews):
        raise ValueError("Select each application once.")
    with Session.begin() as db:
        submission.lock(db)
        return [submission.visible_task(db, submission.approve(
            db, required(db, Application, item.application_id), item.payload_hash
        )) for item in request.reviews]


@app.post("/api/applications/bulk-reject", dependencies=AUTH)
def bulk_reject(request: BulkReview):
    with Session.begin() as db:
        submission.lock(db)
        for row in request.reviews:
            app = required(db, Application, row.application_id)
            if app.status not in submission.READY | {"NEEDS_REVIEW", "NEEDS_MANUAL_ACTION"} or (
                    not app.prepared_payload or submission.digest(app.prepared_payload) != row.payload_hash):
                raise ValueError("One of the selected applications changed. Reload the selection.")
            submission.invalidate_before_edit(db, app)
            record(db, app, "REJECTED_BY_USER", "User rejected this application in bulk review.")
        return {"rejected": len(request.reviews)}


class ReviewEdit(BaseModel):
    answers: dict[str, str] | None = None


@app.put("/api/applications/{app_id}/review", dependencies=AUTH)
def edit_review(app_id: str, request: ReviewEdit):
    with Session.begin() as db:
        submission.lock(db)
        app = required(db, Application, app_id)
        if app.status in {"SUBMITTED", "SUBMITTING", "SUBMISSION_UNCERTAIN", "REJECTED_BY_USER", "SKIPPED"}:
            raise ValueError("This application is outside the editable review stage.")
        context = submission.context_for(db, app)
        answers = request.answers
        if answers is not None:
            if len(answers) > 20 or any(not 1 <= len(key) <= 120 or len(value) > 1500 for key, value in answers.items()):
                raise ValueError("Answers must use bounded question text and values.")
            if app.summary.get("browser") and set(answers) - {"authorization"}:
                raise ValueError("The mock form only accepts its exact screening question.")
            if context.payload.get("provider") == "greenhouse" and answers:
                raise ValueError("Edit verified contact fields in Profile. Custom employer questions require manual handling.")
        submission.invalidate_before_edit(db, app)
        if app.status == "APPROVED":
            record(db, app, "NEEDS_MANUAL_ACTION", "Previous approval superseded by a new review.")
        job, profile, options = context.job, context.profile, context.options
        resume_id = context.resume.id
    return application_item(prepare(job.id, resume_id, profile, options.mode, current_eligibility(job, profile, options),
                                    app.summary.get("review_accepted", False), edited_answers=answers))


@app.get("/api/notifications", dependencies=AUTH)
def list_notifications():
    with Session() as db:
        return [row_item(item, "id kind message count read created") for item in db.scalars(
            select(Notification).order_by(Notification.created.desc()).limit(75)
        )]


@app.post("/api/notifications/read", dependencies=AUTH)
def mark_notifications_read():
    with Session.begin() as db:
        db.execute(update(Notification).where(Notification.read.is_(False)).values(read=True))
        return {"read": True}


@app.get("/api/applications/{app_id}/events", dependencies=AUTH)
def timeline(app_id: str):
    with Session() as db:
        item = required(db, Application, app_id)
        job, resume = db.get(Job, item.job_id), db.get(Resume, item.resume_id)
        events = [row_item(event, "status message created") for event in db.scalars(
            select(ApplicationEvent).where(ApplicationEvent.application_id == app_id).order_by(ApplicationEvent.created)
        )]
        return sorted([
            {"status": "DISCOVERED", "message": "Job first saved.", "created": job.created},
            {"status": "PDF_VALIDATED", "message": "Saved compiled PDF version.", "created": resume.created},
            *events,
        ], key=lambda event: event["created"])


@app.get("/api/export", dependencies=AUTH)
def export():
    import base64

    with Session() as db:
        payload = state()
        payload["originals"] = [{**row_item(item, "id name created"), "base64": base64.b64encode(item.blob).decode()}
                                for item in db.scalars(select(Upload))]
        payload["resumes"] = [{**resume_item(item), "pdf_base64": base64.b64encode(item.pdf).decode()}
                              for item in db.scalars(select(Resume))]
        payload["events"] = [row_item(item, "application_id status message created")
                             for item in db.scalars(select(ApplicationEvent))]
        payload["prepared_payloads"] = [item.prepared_payload for item in db.scalars(select(Application)) if item.prepared_payload]
        payload["final_approvals"] = [row_item(item, "id application_id payload_hash payload created")
                                      for item in db.scalars(select(FinalApproval))]
        payload["submission_tasks"] = [submission.visible_task(db, item) for item in db.scalars(select(SubmissionTask))]
        payload["job_description_history"] = [row_item(item, "job_id digest description created")
                                              for item in db.scalars(select(JobDescription))]
        return Response(json.dumps(payload), media_type="application/json",
                        headers={"Content-Disposition": 'attachment; filename="jobforge-export.json"'})


@app.delete("/api/data", dependencies=AUTH)
def erase():
    with Session.begin() as db:
        settings = lock_settings(db)
        if db.scalar(select(Run.id).where(Run.status.in_(["QUEUED", "RUNNING"])).limit(1)):
            raise ValueError("Cancel active runs before deleting data.")
        if db.scalar(select(SubmissionTask.id).where(SubmissionTask.status.in_(submission.ACTIVE)).limit(1)):
            raise ValueError("Complete or invalidate active submission tasks before deleting data.")
        for cls in [Receipt, SubmissionTask, FinalApproval, Notification, ApplicationEvent, Application, Resume, Job, Upload, Log, Run]:
            db.execute(delete(cls))
        profile = db.get(Profile, 1)
        profile.facts, profile.preferences = [], {}
        settings.options = Options(enabled=False).model_dump(mode="json")
        return {"deleted": True}


MOCK = Template("""<!doctype html><html lang="en"><meta charset="utf-8"><title>Mock employer</title>
<main data-job="{{ job }}"><h1>{{ role }}</h1><p>Synthetic application fixture</p>
{% if variant == 'fixture-challenge' %}
<p data-manual-challenge>Human verification required before this form is available.</p>
{% else %}
<form method="post" enctype="multipart/form-data">
<label>Full name <input name="name" required maxlength="150"></label>
<label>Email <input name="email" type="email" required maxlength="250"></label>
<label>Phone <input name="phone" type="tel" maxlength="50"></label>
<label>What screening answer did you approve for this simulation?
{% if variant == 'fixture-textarea' %}<textarea name="authorization" required maxlength="1500"></textarea>
{% else %}<input name="authorization" required maxlength="1500">{% endif %}</label>
{% if variant == 'fixture-consent' %}<label>Legal declaration <input type="checkbox" name="consent" required></label>{% endif %}
<label>Resume PDF <input name="resume" type="file" accept="application/pdf" required></label>
<button type="submit">Submit simulation</button></form>
{% endif %}</main></html>""", autoescape=True)


def fixture_variant(job):
    return job.source_key.split(":", 2)[1] if job.source_key.startswith("mock:") else ""


def mock_application(request, app_id, db):
    item = required(db, Application, app_id)
    token = request.headers.get("x-jobforge-mock", "")
    if not item.summary.get("browser") or not hmac.compare_digest(token.encode(), item.summary["mock_key"].encode()):
        raise HTTPException(404)
    return item


@app.get("/mock/{app_id}")
def mock_page(request: Request, app_id: str):
    with Session() as db:
        item = mock_application(request, app_id, db)
        job = db.get(Job, item.job_id)
        return HTMLResponse(MOCK.render(job=job.id, role=job.role, variant=fixture_variant(job)))


@app.post("/mock/{app_id}")
def mock_submit(request: Request, app_id: str, name: str = Form(min_length=1, max_length=150),
                email: str = Form(min_length=1, max_length=250), authorization: str = Form(min_length=1, max_length=1500),
                resume: UploadFile = File()):
    with Session.begin() as db:
        item = mock_application(request, app_id, db)
        variant = fixture_variant(db.get(Job, item.job_id))
        if variant in {"fixture-challenge", "fixture-consent"}:
            raise HTTPException(409, "Human action is required for this fixture.")
        if item.status not in {"SUBMITTING", "SUBMITTED"}:
            raise HTTPException(409, "Approval is required.")
        stored = db.get(Resume, item.resume_id)
        if (not name.strip() or "@" not in email or not authorization.strip()
                or not expected_pdf(resume.file.read(5_000_001), stored.pdf)):
            raise HTTPException(422, "Required fields or attached resume are invalid.")
        receipt = db.get(Receipt, app_id)
        if receipt is None:
            receipt = Receipt(id=app_id, evidence=f"MOCK-{uid()}")
            db.add(receipt)
        if variant == "fixture-receipt-only":
            return HTMLResponse("<main>Confirmation page unavailable.</main>", status_code=503)
        return HTMLResponse(f'<main data-confirmation="{receipt.evidence}">Simulation received.</main>')
