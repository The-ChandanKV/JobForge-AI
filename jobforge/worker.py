import logging
import signal
import threading
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo
from time import process_time

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from httpx import HTTPError

from .applications import prepare, reconcile, still_verified
from .llm import model_status
from .matching import analyze, evaluate_saved_job, shortlist
from .models import Application, Job, JobSource, Log, Profile, Resume, Run, Session, Settings, SubmissionTask, WorkerLock, now, uid
from .notifications import deliver_review_notifications, record_daily_summary, record_repeat_failures, send_run_summary
from .submission import process_one
from .profile import readiness
from .providers import fetch_board, save_job
from .reliability import anchor_worker, worker_memory_mib
from .resumes import generate
from .schemas import Generation, Options, Posting, Preferences

STOP = threading.Event()
ACTIVE = ("QUEUED", "RUNNING")
LOGGER = logging.getLogger("jobforge.worker")


def future(minutes):
    return (datetime.now(UTC) + timedelta(minutes=minutes)).isoformat(timespec="microseconds")


def day_start(timezone):
    return datetime.now(ZoneInfo(timezone)).replace(hour=0, minute=0, second=0, microsecond=0).astimezone(UTC).isoformat()


def initialize():
    for cls, fields in (
        (Profile, {"facts": [], "preferences": {}}),
        (Settings, {"options": Options().model_dump(mode="json")}),
        (WorkerLock, {}),
    ):
        try:
            with Session.begin() as db:
                if db.get(cls, 1) is None:
                    db.add(cls(id=1, **fields))
        except IntegrityError:
            pass


def lock_settings(db):
    db.execute(update(Settings).where(Settings.id == 1).values(next_run=Settings.next_run))
    return db.get(Settings, 1, populate_existing=True)


def queue(db, trigger):
    settings = lock_settings(db)
    options = Options.model_validate(settings.options)
    existing = db.scalar(select(Run).where(Run.status.in_(ACTIVE)).limit(1))
    if existing:
        return existing
    report = {}
    if trigger == "scheduled":
        if not options.enabled or settings.next_run > now():
            return None
        due = datetime.fromisoformat(settings.next_run)
        interval = timedelta(minutes=options.interval_minutes)
        missed = int((datetime.now(UTC) - due) // interval)
        settings.next_run = (due + (missed + 1) * interval).isoformat(timespec="microseconds")
        report = {"scheduled_for": due.isoformat(), "coalesced_intervals": missed}
    run = Run(trigger=trigger, report=report)
    db.add(run)
    db.flush()
    return run


def lease(owner, renew=False):
    with Session.begin() as db:
        previous = db.get(WorkerLock, 1)
        query = update(WorkerLock).where(WorkerLock.id == 1)
        if renew:
            query = query.where(WorkerLock.owner == owner, WorkerLock.until >= now())
        else:
            query = query.where((WorkerLock.until.is_(None)) | (WorkerLock.until < now()))
        prior = previous.last_seen if previous else None
        acquired = db.execute(query.values(owner=owner, until=future(2), last_seen=now())).rowcount == 1
        if acquired and not renew and prior:
            gap = (datetime.now(UTC) - datetime.fromisoformat(prior)).total_seconds()
            if gap > 45:
                db.add(Log(kind="downtime", message="Worker heartbeat gap detected",
                           detail={"last_seen": prior, "gap_seconds": round(gap)}))
        return acquired


def heartbeat(owner, stop, lost):
    while not stop.wait(20):
        try:
            if lease(owner, renew=True):
                continue
        except Exception:
            LOGGER.exception("Worker heartbeat failed")
        lost.set()
        return


def canceled(run_id, lost):
    with Session() as db:
        run = db.get(Run, run_id)
        return (STOP.is_set() or lost.is_set() or run.canceled
                or run.trigger == "scheduled" and not db.get(Settings, 1).options.get("enabled", True))


def phase_log(kind, message, **detail):
    with Session.begin() as db:
        db.add(Log(kind=kind, message=message, detail=detail))


def worker_status(db, options):
    lock = db.get(WorkerLock, 1)
    last_seen = lock.last_seen if lock else None
    online = bool(last_seen and (datetime.now(UTC) - datetime.fromisoformat(last_seen)).total_seconds() <= 45)
    success = db.scalar(select(Run.finished).where(Run.status == "COMPLETED")
                        .order_by(Run.finished.desc()).limit(1))
    return {
        "status": "STOPPED" if not online else "RUNNING" if options.enabled else "PAUSED",
        "last_heartbeat": last_seen, "last_success": success,
        "pending": db.scalar(select(func.count()).select_from(Run).where(Run.status.in_(ACTIVE))),
        "model": lock.model_status if lock else {},
    }


def refresh_model_status(owner):
    with Session() as db:
        lock = db.get(WorkerLock, 1)
        opts = Options.model_validate(db.get(Settings, 1).options)
        previous = lock.model_status
        if previous.get("checked") and (datetime.now(UTC) - datetime.fromisoformat(
                previous["checked"])).total_seconds() < 60:
            return
    result = {**model_status(opts), "checked": now()}
    with Session.begin() as db:
        db.execute(update(WorkerLock).where(WorkerLock.owner == owner).values(model_status=result))
        if result["provider"] == "ollama" and result["status"] != "AVAILABLE" and previous.get("status") != result["status"]:
            db.add(Log(kind="model_health", message="Local model became unavailable", detail={"status": result["status"]}))


def retry_due(job, options):
    checkpoint = job.automation
    return (checkpoint.get("state") != "EXCEPTION"
            and (not checkpoint.get("next_retry") or checkpoint["next_retry"] <= now())
            and checkpoint.get("attempts", 0) < options.max_job_attempts
            and (options.retry_failed_jobs or job.status != "FAILED"))


def attempt(db, job):
    count = job.automation.get("attempts", 0) + 1
    job.automation = {"state": "STARTED", "attempts": count, "updated": now()}
    return count


def failed_job(db, job, options, count, stage, exc):
    if job.status in {"SKIPPED", "CLOSED"}:
        return
    exhausted = not options.retry_failed_jobs or count >= options.max_job_attempts
    job.status = "FAILED"
    job.automation = {"state": "EXCEPTION" if exhausted else "RETRY_WAIT", "attempts": count,
                      "next_retry": None if exhausted else future(min(60, 2 ** count)),
                      "reason": f"{stage} failed ({type(exc).__name__}).", "updated": now()}
    if not exhausted or options.exception_notifications:
        db.add(Log(kind="exception" if exhausted else "retry", message=job.automation["reason"],
                   detail={"job_id": job.id, "attempts": count, "next_retry": job.automation["next_retry"]}))


def pipeline(run_id, lost):
    with Session() as db:
        profile = db.get(Profile, 1)
        options = Options.model_validate(db.get(Settings, 1).options)
        preferences = Preferences.model_validate(profile.preferences)
    profile_ready = readiness(profile.facts)["ready"]
    result = {"scanned": 0, "filtered": 0, "discovered": 0, "eligible": 0, "compiled": 0,
              "prepared": 0, "blocked_by_profile": 0, "exceptions": 0, "errors": []}
    active_sources = [source for source in options.sources if source.enabled]
    for source in active_sources:
        if canceled(run_id, lost):
            return result
        try:
            jobs, complete = fetch_board(source)
            with Session.begin() as db:
                existing = {entry.key: entry for entry in db.scalars(select(JobSource).where(
                    JobSource.key.startswith(f"{source.provider}:{source.board.lower()}:", autoescape=True)
                ))}
                seen = set()
                for posting in jobs:
                    seen.add(posting.source_key)
                    result["scanned"] += 1
                    if posting.source_key not in existing and (
                        not shortlist(posting, preferences)
                        or analyze(posting, profile.facts, preferences, options.min_match_score)["eligibility"] == "INELIGIBLE"
                    ):
                        result["filtered"] += 1
                        continue
                    saved = save_job(db, posting)
                    result["discovered"] += 1
                    previous = saved.match.get("recommendation")
                    evaluate_saved_job(saved, profile.facts, preferences, options.min_match_score)
                    result["eligible"] += int(saved.match["eligibility"] == "ELIGIBLE")
                    if (saved.match["recommendation"] == "PREPARE_APPLICATION" and previous != "PREPARE_APPLICATION"
                            and shortlist(Posting.model_validate(saved.detail), preferences)):
                        db.add(Log(kind="match", message="Job meets the relevance threshold",
                                   detail={"job_id": saved.id, "score": saved.match["match_score"]}))
                if complete:
                    missing = [entry for key, entry in existing.items() if key not in seen]
                    for entry in missing:
                        entry.available = False
                    for job_id in {entry.job_id for entry in missing}:
                        job = db.get(Job, job_id)
                        job.available = bool(db.scalar(select(JobSource.key).where(
                            JobSource.job_id == job_id, JobSource.available, ~JobSource.key.startswith("manual:")
                        ).limit(1)))
                else:
                    result["errors"].append(f"{source.provider}/{source.board}: some listings could not be normalized")
        except Exception as exc:
            result["errors"].append(f"{source.provider}/{source.board}: {type(exc).__name__}")
            phase_log("source", "Job board request or normalization failed", run_id=run_id,
                      provider=source.provider, error=type(exc).__name__)
    with Session() as db:
        candidates = db.scalars(select(Job).where(Job.available, Job.status.in_(["SHORTLISTED", "RESUME_READY", "FAILED"]))).all()
        candidates.sort(key=lambda job: job.match.get("match_score", 0), reverse=True)
        active_boards = {(source.provider, source.board.casefold()) for source in active_sources}
        discovered = {alias.job_id for alias in db.scalars(select(JobSource).where(JobSource.available))
                      if tuple(alias.key.split(":", 2)[:2]) in active_boards}
        prepared_today = db.scalar(select(func.count()).select_from(Application).where(
            Application.created >= day_start(options.timezone)
        ))
        interrupted_dispatch = db.scalars(select(Application.id).where(
            Application.status.in_(["SUBMITTING", "SUBMISSION_UNCERTAIN"]),
            ~select(SubmissionTask.id).where(SubmissionTask.dispatch_key == Application.id).exists(),
        ).limit(100)).all()
    for application_id in interrupted_dispatch:
        if canceled(run_id, lost):
            return result
        reconcile(application_id)
    attempts = 0
    for candidate in candidates:
        if canceled(run_id, lost):
            break
        if candidate.id not in discovered and candidate.detail["source"] != "manual":
            continue
        if candidate.match.get("recommendation") != "PREPARE_APPLICATION" or not shortlist(
            Posting.model_validate(candidate.detail), preferences
        ):
            continue
        if not profile_ready and candidate.detail["source"] != "mock":
            result["blocked_by_profile"] += 1
            continue
        count = None
        stage = "Resume generation"
        try:
            with Session.begin() as db:
                job = db.get(Job, candidate.id)
                if not job.available or job.status in {"SKIPPED", "CLOSED"}:
                    continue
                application = db.scalar(select(Application).where(Application.job_id == job.id))
                previous_application = bool(application)
                if application and application.status != "FAILED" and application.summary.get("checkpoint") != "PREPARING":
                    continue
                if not retry_due(job, options):
                    if job.automation.get("state") == "STARTED":
                        failed_job(db, job, options, job.automation["attempts"], "Interrupted preparation", RuntimeError())
                    continue
                resume = db.scalar(select(Resume).where(Resume.job_id == job.id).order_by(Resume.created.desc(), Resume.id.desc()).limit(1))
                if resume and not still_verified(profile, resume):
                    resume = None
                if not resume and attempts >= options.max_resume_generations_per_run:
                    continue
                if resume and not previous_application and options.max_applications_per_day <= prepared_today:
                    continue
                count = attempt(db, job)
            with Session.begin() as db:
                job = db.get(Job, candidate.id)
                if not resume:
                    attempts += 1
                    resume = generate(db, job, profile.facts, options, Generation())
                    result["compiled"] += 1
                db.execute(update(Job).where(Job.id == job.id, Job.status.not_in(["SKIPPED", "CLOSED"]))
                           .values(status="RESUME_READY"))
            if (previous_application or options.max_applications_per_day > prepared_today) and not canceled(run_id, lost):
                stage = "Form preparation"
                app = prepare(candidate.id, resume.id, profile, options.mode, candidate.match["eligibility"])
                if app.summary.get("missing") or app.summary.get("exception"):
                    result["exceptions"] += 1
                prepared_today += int(not previous_application)
                result["prepared"] += 1
            with Session.begin() as db:
                job = db.get(Job, candidate.id)
                job.automation = {"state": "READY", "updated": now(), "last_attempts": count}
        except Exception as exc:
            result["errors"].append(f"{candidate.id}: {type(exc).__name__}")
            with Session.begin() as db:
                job = db.get(Job, candidate.id)
                if count is not None:
                    failed_job(db, job, options, count, stage, exc)
    return result


def step():
    owner = uid()
    if not lease(owner):
        return
    done, lost = threading.Event(), threading.Event()
    try:
        refresh_model_status(owner)
        process_one(Session)
        deliver_review_notifications(Session)
        record_daily_summary(Session)
        record_repeat_failures(Session)
        with Session.begin() as db:
            for unfinished in db.scalars(select(Run).where(Run.status == "RUNNING")):
                if unfinished.attempts < 2 and not unfinished.canceled:
                    unfinished.status = "QUEUED"
                else:
                    unfinished.status = "CANCELED" if unfinished.canceled else "FAILED"
                    unfinished.finished = now()
                unfinished.report = {**unfinished.report, "note": "Recovered an interrupted worker run."}
            job_run = queue(db, "scheduled")
            if job_run is None:
                return
            if job_run.canceled:
                job_run.status, job_run.finished = "CANCELED", now()
                return
            job_run.status, job_run.started = "RUNNING", now()
            job_run.attempts += 1
        thread = threading.Thread(target=heartbeat, args=(owner, done, lost), daemon=True)
        thread.start()
        try:
            cpu_started = process_time()
            result = pipeline(job_run.id, lost)
            result["worker_cpu_seconds"] = round(process_time() - cpu_started, 4)
            result["worker_peak_rss_mib"] = worker_memory_mib()
            if lost.is_set():
                return
            with Session.begin() as db:
                row = db.get(Run, job_run.id)
                paused = row.trigger == "scheduled" and not db.get(Settings, 1).options.get("enabled", True)
                row.status = ("CANCELED" if row.canceled or paused else "QUEUED" if STOP.is_set()
                              else "COMPLETED_WITH_ERRORS" if result["errors"] else "COMPLETED")
                row.finished, row.report = now(), {**row.report, **result}
            if row.status in {"COMPLETED", "COMPLETED_WITH_ERRORS"}:
                try:
                    send_run_summary(row.status, result)
                except (OSError, ValueError, KeyError) as exc:
                    phase_log("notification", "Run email could not be delivered", error=type(exc).__name__, run_id=row.id)
        except Exception:
            LOGGER.exception("Automation run failed")
            with Session.begin() as db:
                row = db.get(Run, job_run.id)
                row.status = "QUEUED" if row.attempts < 2 and not row.canceled else "FAILED"
                row.finished, row.report = now(), {**row.report, "error": "Automation run failed."}
                db.add(Log(kind="scheduler", message="Automation run failed", detail={"run_id": row.id}))
    finally:
        done.set()
        with Session.begin() as db:
            db.execute(update(WorkerLock).where(WorkerLock.owner == owner).values(owner=None, until=None))


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    initialize()
    with Session.begin() as db:
        anchor_worker(db, lock_settings(db))
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: STOP.set())
    failed_ticks = 0
    while not STOP.is_set():
        try:
            step()
            failed_ticks = 0
        except Exception:
            LOGGER.exception("Scheduler tick failed")
            failed_ticks += 1
            if failed_ticks >= 5:
                raise
        STOP.wait(3)


if __name__ == "__main__":
    main()
