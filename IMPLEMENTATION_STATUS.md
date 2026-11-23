# Implementation status

## Phase 10

Installed capability is **READY_FOR_REAL_PREPARATION**. Final release acceptance is **ACTIVATION_REQUIRED** because no live job has reached eligibility and preparation. Verified recovery includes an encrypted online SQLite snapshot, an isolated restore, and native Windows watchdog recovery of both services. A real public posting and verified profile produced a one-page PDF in isolation. Dry-run remains enabled and the Approval Queue is empty. [Release evidence](docs/FINAL_RELEASE_REPORT.md)

## Phase 9

The installed profile is ready and seven employer boards are enabled. Two controlled real discovery cycles completed. The saved job requires eligibility review, so there are zero live PDFs, application packages, or pending approvals. Bounded source concurrency, run timings, eligibility exceptions, and manual destination checks are deployed. Local Ollama and PDF generation passed isolated fixture tests. The 24-hour observation remains in progress. [Validation](docs/PHASE_9_VALIDATION.md)

## Phase 7

Implemented batch resume evidence review, identical-upload reuse, saved activation preferences, verified bulk employer selection, and a crash-safe cap of five jobs for first real preparation. Live preparation awaits career verification and user choices. [Results](docs/TEST_REPORT.md)


## Phase 6

Implemented verified employer discovery, SmartRecruiters and Recruitee public feeds, source health, a bounded local semantic ranking option, durable job feedback, resume quality evidence, and a separate readiness checklist. Employer submission authorization is unchanged. The installed profile and board selections still need activation. [Verification](docs/TEST_REPORT.md)


## Phase 4

Implemented verified onboarding, readiness gating, evidence-prioritized resume tailoring, manual handoff, rejection feedback, native Windows notifications, and durable reliability reporting. The public benchmark contains 36 postings and has no human-reviewed labels. Installation observation is underway. [Verification](docs/TEST_REPORT.md)


## One-click final approval

| Feature | Status | Verification and remaining scope |
|---|---|---|
| Approval Queue details, filters, sorting and editing | IMPLEMENTED_AND_TESTED | The React queue uses the persisted job and PDF snapshot, includes provider-aware filters and sorting, and offers an official-link handoff. |
| Exact one-click and bulk submission tasks | IMPLEMENTED_AND_TESTED | SHA-256 approval binding, concurrent click deduplication, bounded preflight retry, and at-most-once dispatch tested. |
| Synthetic employer | IMPLEMENTED_AND_TESTED | Browser end-to-end preparation, preview, one-click approval and receipt. |
| Greenhouse employer submission | MOCK_TRANSPORT_TESTED | Exact-board configuration and explicit approval required. Live contract awaits employer-authorized sandbox verification. |
| Lever and Ashby | MANUAL_HANDOFF | Public discovery and official apply links. Employer submission APIs are documented in the provider matrix. |
| Notifications | IMPLEMENTED | In-app notices, batch scheduling, and a once-per-day summary in the configured time zone are covered by tests. Windows taskbar and opt-in SMTP delivery depend on the configured OS session and SMTP account. |

[Final approval guide](docs/APPROVAL_AND_SUBMISSION.md) · [Test report and changed files](docs/TEST_REPORT.md)

## Autonomy upgrade

| Feature | Status | Verification and remaining scope |
|---|---|---|
| Unattended preparation, controls and exceptions | IMPLEMENTED_AND_TESTED | Scheduled source-to-form pipeline, retry budgets, alerts, daily summary and approval separation. |
| Windows logon tasks | IMPLEMENTED_AND_TESTED | Registered and started both windowless tasks. Verified a dry-run tick and automatic launch of a new worker process after a forced exit. |
| Windows boot tasks | BLOCKED | Both task definitions were checked. Registration needs elevated PowerShell and the account password. Physical boot, logout and sleep behavior remain unverified. |
| Job targeting and eligibility | PARTIAL | Configurable early-career tracks, exclusions, pre-storage filtering, mandatory/preferred evidence and explicit dates. Ambiguous jurisdiction and custom eligibility questions remain review cases. |
| Grounded resume edits and quality report | IMPLEMENTED_AND_TESTED | Deterministic edits with exact fact lineage, supported claim validation, real PDF, selectable text and formatting checks. Unrestricted model paraphrases and general-purpose LaTeX editing remain outside the supported path. |
| Historical standing submission policy | SUPERSEDED | Migration 0004 disarms automatic dispatch. The current worker requires a distinct final approval per application. |
| Varied synthetic forms | IMPLEMENTED_AND_TESTED | Standard fields, textareas, missing answers, consent, manual challenge, and a lost confirmation page with a durable receipt. |
| Local model comparison | IMPLEMENTED_AND_TESTED | Five fixtures tied on observed quality. Qwen2.5 1.5B remains the faster default. |

[Recovery](docs/SCHEDULER_RECOVERY.md) · [Model evaluation](docs/AI_MODEL_EVALUATION.md) · [Submission permissions](docs/SUBMISSION_PERMISSIONS.md) · [Test report](docs/TEST_REPORT.md)

## Baseline components

| Feature | Status | Verification and remaining scope |
|---|---|---|
| Upstream research and attribution | IMPLEMENTED_AND_TESTED | Seven repositories cloned under `research/upstream`. Exact commits and integration decisions are in [Open-source reuse](docs/OPEN_SOURCE_REUSE.md). The vendored career-ops ATS detector routes supported URL intake. |
| Dashboard, FastAPI, SQLite, migrations | IMPLEMENTED_AND_TESTED | The dashboard runs on Windows. Browser tests exercise manual job intake and application decisions against SQLite. Four Alembic revisions apply cleanly. |
| PostgreSQL and Docker Compose | IMPLEMENTED_NOT_TESTED | SQLAlchemy uses both dialects and the Compose configuration includes service health checks. Docker and PostgreSQL were unavailable on this host, so the image build and end-to-end Compose run remain unverified. |
| Profile, PDF/TXT/TEX import, verification | IMPLEMENTED_AND_TESTED | Imported facts start unverified. Fact labels and categories represent personal, education, experience, project, skill, certification, and authorization details. Extraction is structural and requires correction for complex resume layouts. OCR is absent. |
| Greenhouse, Lever, Ashby discovery and deduplication | IMPLEMENTED_AND_TESTED | Public feeds were called without credentials. An isolated run stored 1,272 listings and retained source identities and descriptions. |
| JobSpy and unrestricted web discovery | NOT_STARTED | No explicitly permitted JobSpy source was configured. Supported URL intake is limited to the documented ATS feeds. Unrecognized URLs use pasted descriptions. |
| Eligibility and relevance | PARTIAL | Deterministic evidence, score breakdown, common explicit experience rules and cautious review routing are tested. Open-ended degree equivalence, visas, location restrictions and custom requirements still require human review. |
| Local Ollama and rules fallback | IMPLEMENTED_AND_TESTED | Structured local completion and unsupported fact-ID rejection are verified. [Test report](docs/TEST_REPORT.md) records the model runs. |
| Anthropic and OpenAI-compatible APIs | IMPLEMENTED_NOT_TESTED | Adapters require explicit selection, model and credentials. Live API calls were skipped because no paid or supported API credentials were provided. |
| LaTeX compilation, PDF validation, versions, cover letter | IMPLEMENTED_AND_TESTED | Both templates compiled to selectable-text PDFs. The UI generates, previews and downloads, and the version records retain source facts and warnings. |
| Free-form model rewriting and unrestricted LaTeX editing | PARTIAL | Model tailoring ranks verified wording. It does not write new factual text. The editor permits validated margin edits. An OS-level arbitrary-LaTeX sandbox is absent. |
| Persistent hourly worker, queue, lease, cancellation, retries | IMPLEMENTED_AND_TESTED | Independent Windows worker handled a due scheduled run and a manual queued run in tests. Cancellation is cooperative between bounded stages. Native services need a service manager for restart after a reboot. |
| Playwright form fill, screening, attachment, approval, receipt | IMPLEMENTED_AND_TESTED | Local mock employer only. Browser automation uploads the exact PDF, flags missing data, requires approval, and records a synthetic receipt. |
| Live employer submission and scheduled dispatch | PARTIAL | Greenhouse employer API preflight and response handling were tested through mocked HTTP. Live submission needs an authorized board and employer-issued credentials. Assisted browser filling of real websites is outside the implemented integration. |
| Application tracking and local alerts | IMPLEMENTED_AND_TESTED | Audit timeline, local confirmation, synthetic evidence, run activity and provider fallback are visible in the dashboard. |
| SMTP | IMPLEMENTED_NOT_TESTED | TLS transport is opt-in with environment credentials. No SMTP credentials were supplied and no email was sent. |
| Private storage, export, deletion and optional token | IMPLEMENTED_AND_TESTED | Private SQL blobs and same-origin API access. The supplied deployment is single-user. Hosted multi-user accounts and S3 storage are absent. |

Next verification steps for the remaining external integrations are a clean Compose build on a host with Docker and a Greenhouse employer-authorized sandbox contract test. Exercise optional paid inference and SMTP only with approved credentials and accounts.
