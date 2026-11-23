import os
import smtplib
import ssl
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import func, select, update

from .models import ApplicationEvent, Log, Notification, Run, Settings
from .schemas import Options


def send_run_summary(outcome, report):
    """Optional local-worker email. No personal data, job text or attachments."""
    if os.getenv("JOBFORGE_EMAIL_ENABLED") != "true":
        return
    send_email("JobForge automation run summary",
               f"Outcome: {outcome}\nListings processed: {report.get('discovered', 0)}\n"
               f"Compiled resumes: {report.get('compiled', 0)}\nApplications prepared: {report.get('prepared', 0)}\n"
               f"Errors: {len(report.get('errors', []))}\nOpen the local dashboard for run details.")


def send_email(subject, body):
    host = os.getenv("JOBFORGE_SMTP_HOST")
    sender = os.getenv("JOBFORGE_SMTP_FROM")
    recipient = os.getenv("JOBFORGE_NOTIFICATION_EMAIL")
    if not all((host, sender, recipient)):
        raise ValueError("SMTP host, sender, and notification recipient are required.")
    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)
    with smtplib.SMTP_SSL(host, int(os.getenv("JOBFORGE_SMTP_PORT", "465")), timeout=12,
                          context=ssl.create_default_context()) as smtp:
        if os.getenv("JOBFORGE_SMTP_USER"):
            smtp.login(os.environ["JOBFORGE_SMTP_USER"], os.environ["JOBFORGE_SMTP_PASSWORD"])
        smtp.send_message(message)


def desktop_notification(message):
    if sys.platform != "win32" or os.getenv("JOBFORGE_DISABLE_DESKTOP_NOTIFICATIONS") == "true":
        return
    script = Path(__file__).resolve().parent.parent / "scripts" / "review-notification.ps1"
    subprocess.Popen(["powershell.exe", "-NoProfile", "-NonInteractive", "-STA", "-File", str(script), message],
                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def deliver_review_notifications(session):
    with session.begin() as db:
        db.execute(update(Settings).where(Settings.id == 1).values(next_run=Settings.next_run))
        options = Options.model_validate(db.get(Settings, 1).options)
        last = db.scalar(select(Log.created).where(Log.kind == "notice_batch").order_by(Log.created.desc()).limit(1))
        if last and datetime.now(UTC) - datetime.fromisoformat(last) < timedelta(minutes=options.notification_interval_minutes):
            return
        pending = db.scalars(select(Notification).where(Notification.pending.is_(True))).all()
        if not pending:
            return
        ready = sum(row.count for row in pending if row.kind == "ready")
        outcomes = sum(row.count for row in pending if row.kind == "outcome")
        for row in pending:
            row.pending = False
        db.add(Log(kind="notice_batch", message="Review notifications grouped",
                   detail={"ready": ready, "outcomes": outcomes}))
    parts = []
    if ready:
        parts.append(f"{ready} application{'s are' if ready != 1 else ' is'} ready for review.")
    if outcomes:
        parts.append(f"{outcomes} submission update{'s' if outcomes != 1 else ''}.")
    text = " ".join(parts)
    channels = []
    if options.desktop_notifications:
        channels.append(("desktop", lambda: desktop_notification(text)))
    if options.approval_email and os.getenv("JOBFORGE_EMAIL_ENABLED") == "true":
        channels.append(("email", lambda: send_email("JobForge application review", text + "\nhttp://127.0.0.1:8000/approvals")))
    for channel, send in channels:
        try:
            send()
        except (OSError, ValueError, KeyError) as exc:
            with session.begin() as db:
                db.add(Log(kind="notification", message="Review notification delivery failed",
                           detail={"channel": channel, "error": type(exc).__name__}))


def record_daily_summary(session, at=None):
    """Record the last completed local day once, under the worker lease."""
    with session.begin() as db:
        options = Options.model_validate(db.get(Settings, 1).options)
        local = (at or datetime.now(UTC)).astimezone(ZoneInfo(options.timezone))
        midnight = local.replace(hour=0, minute=0, second=0, microsecond=0)
        previous_day = midnight - timedelta(days=1)
        day = previous_day.date().isoformat()
        if db.scalar(select(Log.id).where(Log.kind == "daily_summary",
                                        Log.detail["day"].as_string() == day).limit(1)):
            return
        start = previous_day.astimezone(UTC).isoformat(timespec="microseconds")
        end = midnight.astimezone(UTC).isoformat(timespec="microseconds")
        reports = db.scalars(select(Run.report).where(
            Run.finished >= start, Run.finished < end,
            Run.status.in_(["COMPLETED", "COMPLETED_WITH_ERRORS", "FAILED"]),
        )).all()
        confirmed = db.scalar(select(func.count()).select_from(ApplicationEvent).where(
            ApplicationEvent.status == "SUBMITTED", ApplicationEvent.created >= start,
            ApplicationEvent.created < end,
        ))
        prepared = sum(report.get("prepared", 0) for report in reports)
        compiled = sum(report.get("compiled", 0) for report in reports)
        db.add(Log(kind="daily_summary", message="Daily application summary evaluated",
                   detail={"day": day, "prepared": prepared, "compiled": compiled, "confirmed": confirmed}))
        if reports or confirmed:
            db.add(Notification(
                kind="daily_summary", pending=False,
                message=f"{day} · Runs finished {len(reports)}, resumes compiled {compiled}, "
                        f"applications prepared {prepared}, confirmations recorded {confirmed}.",
            ))
