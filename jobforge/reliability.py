"""Report actual scheduler observations from durable runs and worker events."""
import sys
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime, timedelta
from statistics import mean
from time import perf_counter

from sqlalchemy import event, select
from sqlalchemy.engine import Engine

from .models import Log, Run, Session, Settings, WorkerLock
from .schemas import Options


def cadence(db, settings):
    options = Options.model_validate(settings.options)
    db.add(Log(kind="schedule_observation", message="Scheduler observation baseline",
               detail={"enabled": options.enabled, "interval_minutes": options.interval_minutes,
                       "next_run": settings.next_run}))


def anchor_worker(db, settings):
    if not db.scalar(select(Log.id).where(Log.kind == "schedule_observation").limit(1)):
        cadence(db, settings)
    db.add(Log(kind="worker_started", message="Worker process started", detail={}))


def timestamp(value):
    return datetime.fromisoformat(value) if value else None


SQL_OBSERVATION = ContextVar("jobforge_sql_observation", default=None)


@event.listens_for(Engine, "before_cursor_execute")
def start_sql_observation(_connection, _cursor, _statement, _parameters, context, _many):
    totals = SQL_OBSERVATION.get()
    if totals is not None:
        context.jobforge_started = perf_counter()
        totals["statements"] += 1


@event.listens_for(Engine, "after_cursor_execute")
def finish_sql_observation(_connection, _cursor, _statement, _parameters, context, _many):
    started = getattr(context, "jobforge_started", None)
    if started is not None:
        SQL_OBSERVATION.get()["seconds"] += perf_counter() - started


@contextmanager
def observe_sql():
    totals = {"statements": 0, "seconds": 0.0}
    token = SQL_OBSERVATION.set(totals)
    try:
        yield totals
    finally:
        SQL_OBSERVATION.reset(token)
        totals["seconds"] = round(totals["seconds"], 4)


def report(at=None):
    at = at or datetime.now(UTC)
    boundary = at - timedelta(hours=24)
    with Session() as db:
        configurations = db.scalars(select(Log).where(Log.kind == "schedule_observation")
                                    .order_by(Log.created)).all()
        recent = db.scalars(select(Run).where(Run.created >= boundary.isoformat(),
                            Run.created <= at.isoformat())).all()
        logs = db.scalars(select(Log).where(Log.created >= boundary.isoformat(), Log.created <= at.isoformat(),
                          Log.kind.in_(["worker_started", "exception", "model_health", "downtime"]))).all()
        lock = db.get(WorkerLock, 1)
        heartbeat = lock.last_seen if lock else None
    configurations = [record for record in configurations if timestamp(record.created) <= at]
    observed = max(boundary, timestamp(configurations[0].created)) if configurations else None
    slots = []
    for index, record in enumerate(configurations):
        config = record.detail
        if not config["enabled"]:
            continue
        left = max(boundary, timestamp(record.created))
        right = timestamp(configurations[index + 1].created) if index + 1 < len(configurations) else at
        due = timestamp(config["next_run"])
        interval = timedelta(minutes=config["interval_minutes"])
        if due < left:
            due += ((left - due) // interval) * interval
            if due < left:
                due += interval
        while due < right:
            slots.append(due)
            due += interval
    eligible_runs = [run for run in recent if observed and timestamp(run.created) >= observed]
    scheduled = [run for run in eligible_runs if run.trigger == "scheduled"]
    finished = [run for run in scheduled if run.finished and run.status in {"COMPLETED", "COMPLETED_WITH_ERRORS", "FAILED"}]
    durations = [(timestamp(run.finished) - timestamp(run.started)).total_seconds() for run in finished if run.started]
    admission = {value for run in scheduled if (value := timestamp(run.report.get("scheduled_for")))}
    observed_logs = [log for log in logs if observed and timestamp(log.created) >= observed]
    counters = {label: sum(run.report.get(key, 0) for run in finished)
                for label, key in (("Jobs discovered", "discovered"), ("Eligible jobs", "eligible"),
                                   ("PDFs compiled", "compiled"), ("Applications prepared", "prepared"),
                                   ("Blocked by profile", "blocked_by_profile"), ("Preparation exceptions", "exceptions"))}
    cpu = [run.report["worker_cpu_seconds"] for run in finished if "worker_cpu_seconds" in run.report]
    memory = [run.report["worker_peak_rss_mib"] for run in finished if run.report.get("worker_peak_rss_mib") is not None]
    return {"observed_from": observed.isoformat() if observed else None, "observed_until": at.isoformat(),
            "hours_observed": round((at - observed).total_seconds() / 3600, 3) if observed else 0,
            "complete": bool(observed and observed == boundary), "last_worker_heartbeat": heartbeat,
            "metrics": {"Expected runs": len(slots), "Actual scheduled runs": len(scheduled),
                        "Missed schedule slots": sum(slot not in admission for slot in slots),
                        "Successful runs": sum(run.status == "COMPLETED" for run in finished),
                        "Runs with errors": sum(run.status == "COMPLETED_WITH_ERRORS" for run in finished),
                        "Failed runs": sum(run.status == "FAILED" for run in finished),
                        **counters, "Resume versions generated": counters["PDFs compiled"],
                        "Exhausted retries": sum(log.kind == "exception" for log in observed_logs),
                        "Average processing seconds": round(mean(durations), 2) if durations else None,
                        "Worker starts": sum(log.kind == "worker_started" for log in observed_logs),
                        "Detected heartbeat gaps": sum(log.kind == "downtime" for log in observed_logs),
                        "Ollama unavailable transitions": sum(log.kind == "model_health" for log in observed_logs),
                        "Worker CPU seconds": round(sum(cpu), 2) if cpu else None,
                        "Worker peak RSS MiB": max(memory, default=None)}}


def worker_memory_mib():
    if sys.platform != "win32":
        try:
            import resource
            value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            return round(value / (1024 ** 2 if sys.platform == "darwin" else 1024), 2)
        except (ImportError, OSError):
            return None
    import ctypes
    from ctypes import wintypes

    class Counters(ctypes.Structure):
        _fields_ = [("size", wintypes.DWORD), ("faults", wintypes.DWORD), ("peak", ctypes.c_size_t),
                    ("remaining", ctypes.c_size_t * 7)]

    try:
        kernel = ctypes.WinDLL("kernel32")
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        memory = ctypes.WinDLL("psapi").GetProcessMemoryInfo
        memory.argtypes = (wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD)
        memory.restype = wintypes.BOOL
        counters = Counters()
        counters.size = ctypes.sizeof(counters)
        if memory(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.size):
            return round(counters.peak / 1024 ** 2, 2)
    except OSError:
        pass
    return None
