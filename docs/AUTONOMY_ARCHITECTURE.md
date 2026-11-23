# Autonomy architecture

## Unattended preparation

`AUTONOMOUS_PREPARATION` is the default. An enabled worker admits one due run, reads permitted ATS sources, normalizes and deduplicates listings, and filters out obvious mismatches before storing new jobs. It checks verified profile evidence, scores requirements and achievements separately, and selects qualifying roles. It generates LaTeX, verifies extracted PDF text against the rendered claims, records an application checkpoint, prepares supported forms, and updates the dashboard. These internal stages require no approval.

Profile preferences control engineering tracks, senior title exclusions, mandatory experience ceilings, locations, company allowlists and blocklists. The early-career preset is editable before saving. Expiry uses explicit board deadlines or source liveness. Preferred qualifications contribute to relevance without becoming mandatory. Unknown requirements and jurisdiction-specific eligibility remain reviewable.

## Durable records

SQL stores runs, the schedule, worker lease and heartbeat, last model probe, per-job retry state, prepared payloads, final approvals, submission tasks, notifications, and receipts. The worker checks explicitly approved tasks separately from the hourly preparation schedule. The Automation page rolls up activity in the configured time zone. The worker records the previous completed day's activity in the dashboard notification center once per day.

Resume provenance links each rendered bullet to a verified fact ID and source. Ollama can rank verified candidates, and deterministic overlap prioritizes evidence matching the job. Editing removes list markers or first-person boilerplate and normalizes capitalization. The application recalculates the permitted edit before compiling. Numbers, dates, employers, technologies, and outcomes stay in the literal source wording. The PDF report records missing requirements, represented skills, long bullets, text extraction, layout warnings, and page overflow. The LaTeX editor continues to accept bounded margin edits.

## Intervention

The Exception Queue shows ambiguous high-match eligibility, missing form information, unsupported portals, attestations and verification challenges, exhausted internal retries, and uncertain dispatch. The Approval Queue presents the prepared payload for final review. Approve & Submit writes an immutable approval and an idempotent task. The mock and Greenhouse adapters each own form preparation, validation, dispatch, and receipt handling. Manual handoffs and unresolved provider responses require evidence before the status becomes submitted. [Approval workflow](APPROVAL_AND_SUBMISSION.md)

The worker can run independently of the dashboard. The Windows installer creates separate windowless API and worker Task Scheduler entries. The scheduler's lease expiry and attempt limits protect recovery regardless of the host launch mechanism. [Scheduler recovery](SCHEDULER_RECOVERY.md)
