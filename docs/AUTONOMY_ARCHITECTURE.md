# Autonomy architecture

The Activation page exposes configured capability from verified profile and source evidence, the actual worker heartbeat, Ollama health, the compiler executable, and the exact authorized submission configuration. This capability check is independent of the release requirement to observe a qualified real job enter review. [Release status and criteria](FINAL_RELEASE_REPORT.md)

## First-run activation

The activation admission stores its verified board identifiers on the existing run record. The worker rechecks readiness and reserves at most five eligible job IDs before compilation. Reservations persist through a recovered run. The action shares the existing worker lease, retry budget and duplicate-run protection. It does not change the hourly cadence. [First-run workflow](REAL_APPLICATION_PREPARATION.md)


## Intelligent hourly discovery

The worker observes bounded public employer feeds, records source health, and keeps incomplete reads from retiring unseen jobs. Repeated fetches preserve aliases and immutable application approvals. Local semantic ranking is bounded and cached. Job readiness projects verifiable preparation without modifying application state. [Matching](MATCHING_ENGINE.md) · [Readiness](APPLICATION_READINESS.md)


## Phase 4 readiness

Discovery and scoring continue when core evidence is missing. Scheduled real preparation waits for verified name, email, and career evidence. The API observes stale worker heartbeats while the scheduler runs independently. Configured cadence and run telemetry drive the rolling 24-hour report. [Reliability methodology](24_HOUR_RELIABILITY.md)


## Unattended preparation

`AUTONOMOUS_PREPARATION` is the default. An enabled worker admits one due run, reads permitted ATS sources, normalizes and deduplicates listings, and filters out obvious mismatches before storing new jobs. It checks verified profile evidence, scores requirements and achievements separately, and selects qualifying roles. It generates LaTeX, verifies extracted PDF text against the rendered claims, records an application checkpoint, prepares supported forms, and updates the dashboard. These internal stages require no approval.

Profile preferences control engineering tracks, senior title exclusions, mandatory experience ceilings, locations, company allowlists and blocklists. The early-career preset is editable before saving. Expiry uses explicit board deadlines or source liveness. Preferred qualifications contribute to relevance without becoming mandatory. Unknown requirements and jurisdiction-specific eligibility remain reviewable.

## Durable records

SQL stores runs, the schedule, worker lease and heartbeat, last model probe, per-job retry state, prepared payloads, final approvals, submission tasks, notifications, and receipts. The worker checks explicitly approved tasks separately from the hourly preparation schedule. The Automation page rolls up activity in the configured time zone. The worker records the previous completed day's activity in the dashboard notification center once per day.

File-backed SQLite supports verified online snapshots and isolated restore. The recovery command protects the configured live database and existing restore destinations. Reconcile uncertain approvals before resuming a workspace recovered from an older snapshot. [Backup and restore](BACKUP_AND_RESTORE.md)

Resume provenance links each rendered bullet to a verified fact ID and source. Ollama can rank verified candidates, and deterministic overlap prioritizes evidence matching the job. Editing removes list markers or first-person boilerplate and normalizes capitalization. The application recalculates the permitted edit before compiling. Numbers, dates, employers, technologies, and outcomes stay in the literal source wording. The PDF report records missing requirements, represented skills, long bullets, text extraction, layout warnings, and page overflow. The LaTeX editor continues to accept bounded margin edits.

## Intervention

The Exception Queue shows ambiguous high-match eligibility, missing form information, unsupported portals, attestations and verification challenges, exhausted internal retries, and uncertain dispatch. The Approval Queue presents the prepared payload for final review. Approve & Submit writes an immutable approval and an idempotent task. The mock and Greenhouse adapters each own form preparation, validation, dispatch, and receipt handling. Manual handoffs and unresolved provider responses require evidence before the status becomes submitted. [Approval workflow](APPROVAL_AND_SUBMISSION.md)

The worker can run independently of the dashboard. The Windows installer creates separate windowless API and worker Task Scheduler entries. The scheduler's lease expiry and attempt limits protect recovery regardless of the host launch mechanism. [Scheduler recovery](SCHEDULER_RECOVERY.md)
