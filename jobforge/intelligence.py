"""Read-only readiness and recommendation evidence for the workspace."""
from collections import Counter
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from . import submission
from .applications import still_verified
from .matching import expired
from .models import Log
from .profile import readiness
from .providers import fold, safe_url
from .resumes import posting_digest


def semantic_cache_key(job, model, facts):
    evidence = [(fact["id"], fact["category"], fact["value"]) for fact in facts if fact["verified"]]
    return submission.digest([model, posting_digest(job), evidence])


def feedback_for(db, job):
    return db.scalar(select(Log.detail).where(Log.kind == "recommendation_feedback",
                     Log.detail["job_id"].as_string() == job.id).order_by(Log.created.desc(), Log.id.desc()).limit(1))


def ranking_feedback(db):
    entries = db.scalars(select(Log.detail).where(Log.kind == "recommendation_feedback")
                         .order_by(Log.created.desc(), Log.id.desc()).limit(200)).all()
    latest = {}
    for item in entries:
        latest.setdefault(item["job_id"], item)
    counts = Counter()
    for item in latest.values():
        weight = {"good": 2, "bad": -2, "wrong_level": -3}.get(item["value"], 0)
        counts[(item["company"], item["role"])] += weight
    return counts


def priority_score(job, preferred, feedback):
    priority = 4 if fold(job.company) in preferred else 0
    stamp = job.detail.get("posted")
    cutoff = datetime.now(UTC)
    freshness = deadline = 0
    try:
        posted = datetime.fromisoformat(stamp or "")
        posted = posted if posted.tzinfo else posted.replace(tzinfo=UTC)
        freshness = 3 if cutoff - timedelta(days=7) <= posted <= cutoff else 0
    except ValueError:
        pass
    try:
        expires = datetime.fromisoformat(job.detail.get("deadline") or "")
        expires = expires if expires.tzinfo else expires.replace(tzinfo=UTC)
        deadline = 3 if cutoff < expires <= cutoff + timedelta(days=3) else 0
    except ValueError:
        pass
    try:
        history = feedback[(fold(job.company), fold(job.role))]
    except KeyError:
        history = 0
    return (job.match.get("match_score", 0) + priority + freshness + deadline + max(-5, min(5, history)),
            job.verified)


def application_readiness(job, profile, resume=None, application=None, can_dispatch=False, already_applied=False):
    prepared = application.prepared_payload or {} if application else {}
    canonical = submission.readiness(application) if application else None
    manual_url = safe_url(job.detail.get("apply_url")) or safe_url(job.detail.get("url"))
    contact = readiness(profile.facts)["checks"]
    missing = prepared.get("pending") or (application.summary.get("missing") if application else None) or []
    already_applied = already_applied or bool(application and (
        application.confirmation or application.status in {"SUBMITTED", "INTERVIEW", "OFFER"}))
    form_verified = bool(prepared.get("form_digest") and prepared.get("provider") in {"mock", "greenhouse"})
    pdf = bool(resume and resume.pdf.startswith(b"%PDF-") and resume.report.get("claims") and still_verified(profile, resume))
    checks = {
        "Opening available": bool(job.available and not expired(job.detail.get("deadline"))),
        "Eligibility established": job.match.get("eligibility") == "ELIGIBLE",
        "Verified name and email": bool(contact["Name"] and contact["Email"]),
        "Verified career evidence": contact["Career evidence"],
        "Compiled PDF tied to verified facts": pdf,
        "Official destination": bool(manual_url or (can_dispatch and prepared.get("destination"))),
        "Supported submission": can_dispatch,
        "Screening completeness": not missing if form_verified else None,
        "Consent review": False if any("consent" in str(item).casefold() or "attest" in str(item).casefold()
                                      for item in missing) else True if form_verified and not missing else None,
        "No prior submission recorded": not already_applied,
    }
    if already_applied:
        category = "ALREADY_APPLIED"
    elif canonical in {"FAILED", "SUBMISSION_UNCERTAIN"}:
        category = "FAILED_PREPARATION" if canonical == "FAILED" else "NEEDS_INFORMATION"
    elif missing or not all(checks[key] for key in
             ("Opening available", "Eligibility established", "Verified name and email", "Verified career evidence",
              "Compiled PDF tied to verified facts")):
        category = "NEEDS_INFORMATION"
    elif canonical == "READY_FOR_REVIEW" and can_dispatch and form_verified:
        category = "READY_FOR_REVIEW"
    elif manual_url:
        category = "MANUAL_HANDOFF"
    else:
        category = "UNSUPPORTED"
    return {"category": category, "verified_checks": sum(value is True for value in checks.values()),
            "total_checks": len(checks), "checks": checks, "pending": missing, "manual_url": manual_url,
            "status": canonical}
