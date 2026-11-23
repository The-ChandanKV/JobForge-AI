"""Readiness and job reservations for a dry-run activation."""
from datetime import UTC, datetime, timedelta
from shutil import which

from sqlalchemy import select

from . import employers
from .config import TECTONIC
from .models import Profile, Run, Settings
from .profile import readiness
from .schemas import Options, Preferences

INITIAL_LIMIT = 5


def capability(db, worker, authorized_board):
    settings = db.get(Settings, 1)
    profile = db.get(Profile, 1)
    options = Options.model_validate(settings.options)
    preferences = Preferences.model_validate(profile.preferences)
    sources = [source for source in options.sources if source.enabled and source.provider != "mock"
               and employers.latest_proof(db, source.provider, source.board)]
    model = worker["model"]
    checked = datetime.fromisoformat(model["checked"]) if model.get("checked") else None
    configuration = {
        "Applicant profile verified": readiness(profile.facts)["ready"],
        "Target roles saved": any(role.strip() for role in preferences.roles),
        "Locations or remote saved": any(location.strip() for location in preferences.locations) or "remote" in preferences.work_modes,
        "Verified employer monitoring enabled": bool(sources),
    }
    runtime = {
        "Hourly worker running": worker["status"] == "RUNNING" and options.interval_minutes == 60,
        "Local Ollama available": bool(model.get("provider") == "ollama" and model.get("status") == "AVAILABLE"
                                      and checked and datetime.now(UTC) - checked <= timedelta(minutes=3)),
        "Tectonic executable available": bool(which(TECTONIC)),
    }
    live = bool(not options.dry_run and options.mode == "AUTHORIZED_AUTO" and authorized_board
                and any(source.provider == "greenhouse" and source.board.casefold() == authorized_board for source in sources))
    if not all(configuration.values()):
        status = "ACTIVATION_REQUIRED"
    elif not all(runtime.values()) or (not options.dry_run and not live):
        status = "DEVELOPMENT_READY"
    else:
        status = "LIVE_SUBMISSION_AVAILABLE" if live else "READY_FOR_REAL_PREPARATION"
    return {"status": status, "checks": {**configuration, **runtime}}


def plan(db, settings=None):
    settings = settings if settings is not None else db.get(Settings, 1)
    profile = db.get(Profile, 1)
    options = Options.model_validate(settings.options)
    preferences = Preferences.model_validate(profile.preferences)
    sources = [source for source in options.sources if source.enabled and source.provider != "mock"
               and employers.recently_verified(db, source.provider, source.board)]
    checks = {
        **readiness(profile.facts)["checks"],
        "Target roles": any(role.strip() for role in preferences.roles),
        "Preferred locations or remote work": any(location.strip() for location in preferences.locations)
                                               or "remote" in preferences.work_modes,
        "Verified enabled employer board": bool(sources),
        "Real submission disabled": bool(options.dry_run and not options.auto_submit and options.mode != "AUTHORIZED_AUTO"),
    }
    return {"checks": checks, "ready": all(checks.values()), "verified_enabled_boards": len(sources),
            "enabled_boards": sum(source.enabled and source.provider != "mock" for source in options.sources),
            "limit": INITIAL_LIMIT, "next_run": settings.next_run if options.enabled else None}, sources


def snapshot(db):
    result, _ = plan(db)
    run = db.scalar(select(Run).where(Run.trigger == "activation")
                    .order_by(Run.created.desc(), Run.id.desc()).limit(1))
    counts = ("scanned", "discovered", "eligible", "compiled", "prepared")
    result["latest_run"] = None if not run else {
        "id": run.id, "status": run.status, "finished": run.finished,
        "selected": len(run.report.get("activation_jobs", [])),
        **{key: run.report.get(key, 0) for key in counts},
        "errors": run.report.get("errors", []),
    }
    return result


def reserve(db, run_id, job_id):
    row = db.get(Run, run_id)
    if row is None or row.trigger != "activation":
        return True
    if row.canceled:
        return False
    selection = row.report.get("activation_jobs", [])
    if job_id in selection:
        return True
    if len(selection) >= INITIAL_LIMIT:
        return False
    row.report = {**row.report, "activation_jobs": [*selection, job_id]}
    return True
