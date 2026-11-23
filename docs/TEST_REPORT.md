# Test report

## Phase 9 workflow validation

- Windows pytest passed **56 tests** with the existing Starlette test-client warning. This included both Playwright suites, real Ollama against synthetic facts, scheduler crash and lease recovery, source failure and bounded retry, interrupted preparation with PDF reuse, and exact approval and stale-payload safeguards.
- Frontend lint, three Vitest tests, TypeScript and the Vite production build passed. An isolated Chrome session confirmed authenticated PDF access, no-store headers, an official-link manual handoff, application tracking, notifications, and simulated approval. The installed nine-route smoke test checked the live eligibility exception and run measurements.
- A fresh SQLite database migrated to 0004 and Alembic reported no pending operations. The installed database was also at 0004. The dashboard listened on loopback, the single Windows worker process tree advanced its heartbeat, Ollama was available, and Tectonic 0.17.0 compiled the fixture PDF.
- Two controlled public-board cycles completed with zero eligible matches, zero live PDFs or application packages, and zero submissions. Existing Windows shell events showed desktop notifications had been displayed. Live application-ready delivery remains unobserved because no live application reached review. [Phase 9 validation](PHASE_9_VALIDATION.md)

## Phase 8 personal activation

- The Windows backend suite passed 56 tests with the existing Starlette test-client deprecation warning. The five focused activation tests, three frontend tests, lint, TypeScript, and the production build passed.
- The installed Activation screen showed 105 draft fact groups across two saved originals, including source-backed CGPA, graduation year, GitHub, and LinkedIn. The browser check opened the two CGPA excerpts and selected a draft fact and a board without submitting the form.
- All seven saved employer previews were available. The stored samples had no role and location matches for the proposed draft, and the screen uses directory coverage as a secondary ranking signal. Older samples lack posting dates and experience data. No additional public feed discovery was needed for this review.
- The isolated confirmation tests cover grouped duplicates, conflicting values, stale review rejection, rollback on an invalid board, preservation of existing verified facts and salary, and explicit Remote selection. The synthetic preparation run rejected an unrelated ATS board and compiled five real PDFs for fictional jobs. It saved five preparation records and produced zero submission receipts.
- The installed SQLite database and a fresh migration both reported revision 0004. The dashboard returned HTTP 200. One Windows worker process tree advanced its heartbeat, Ollama reported the configured model available, and Tectonic was installed. The worker remained on the 60-minute schedule in dry-run mode. Desktop notifications were enabled, approval email was unset, and the live smoke test generated no notification.
- Live profile readiness still requires career verification. No search preferences or employer monitoring were activated. Jobs ingested, eligible matches, generated resumes, validated PDFs, applications awaiting approval, and submissions were each zero at verification.

## Phase 7 real-world activation

The baseline passed all **51 pytest tests**. The final full Windows suite passed **54 tests**, with the existing Starlette test-client deprecation warning. The three frontend tests, lint, TypeScript, Vite production build, and Playwright flows passed. A fresh temporary SQLite database migrated through 0004 without outstanding schema operations.

- The original upload snapshot, byte-identical replay, exact draft evidence acknowledgement, and atomic rollback of a stale selection passed.
- Source proof rejects a posting from an unrelated ATS board. Bulk enabling is atomic. Exposure to real employer systems was confined to public read-only feed verification.
- An isolated preparation run compiled five actual PDFs from six fictional provider-shaped postings and saved five manual-handoff records. The configured mock board was excluded from that run. There were zero submission receipts.
- Live Chromium opened Activation and the existing profile evidence review. Both Windows tasks reported running, Ollama reported availability, and the worker heartbeat advanced with Chromium closed.
- Public verification saved previews from seven boards with 2,360 returned listings before workspace selection and deduplication. The Bosch check was partial. No boards were enabled, and the live workspace gained no real jobs, eligible matches, resumes or applications. No personal facts or preferences were changed.
- The next scheduled execution was verified at 21:55 IST on November 23, 2026. The preceding reliability read reported four observed scheduled runs and five missed schedule slots. The cause of missed slots was not inferred.
- Dry-run remained enabled. No real submissions occurred.

The changes are grouped in the [feature branch](https://github.com/The-ChandanKV/JobForge-AI/tree/feat/real-world-activation). [Activation guide](PHASE_7_ACTIVATION.md) · [Preparation verification](REAL_APPLICATION_PREPARATION.md)

## Phase 6 intelligent discovery and readiness

The starting branch and GitHub heads contained Phase 4 at commit 8a1cfa7 and no separate Phase 5 branch or implementation. All **47** existing tests passed before changes. The Phase 6 full Windows run had **51 passed, zero failures**, with the existing Starlette test-client warning. An earlier targeted run caught a missing source-model import, which was corrected before the full run.

- Frontend lint, three Vitest tests, TypeScript, the production build, and the Chromium flows passed. Browser coverage includes the new Job Intelligence route and unverified boards staying disabled.
- Added regression tests for normalization and trusted provider URLs, employer verification and opt-in, feedback persistence, alternative skill requirements, strict semantic output, and readiness for manual forms and blocked consent.
- The existing hourly preparation, worker recovery, cross-provider deduplication, provenance, exact approval, bulk approval, and synthetic receipt coverage passed.
- A fresh temporary SQLite migration and Alembic check passed. The installed database remains at revision 0004.
- Read-only public feed tests normalized 12 Bosch Group postings through SmartRecruiters and 12 The Codest postings through Recruitee. No sources or private profile facts were changed in the installed workspace.
- Isolated Tectonic generated and validated one synthetic PDF in 1.88 seconds. The PDF had one page, two named fonts and zero unsupported claims.
- Chromium rendered the installed Job Intelligence, employer directory and source health views. Both registered Windows tasks were running. The worker heartbeat advanced with Chromium closed, the schedule remained 60 minutes, and Ollama was available.
- Real applicant readiness is still missing verified career evidence. There are no target-role or location preferences, enabled employer boards, or live applications waiting for review. Dry-run stayed enabled and no real employer submission was attempted.

Changed files are grouped in the [feature branch](https://github.com/The-ChandanKV/JobForge-AI/tree/feat/intelligent-job-discovery). [Public discovery](INTELLIGENT_JOB_DISCOVERY.md) · [Reviewed benchmark](MATCHING_ENGINE.md) · [Resume optimization](RESUME_OPTIMIZATION.md) · [Readiness checks](APPLICATION_READINESS.md)

## Phase 4 real-world readiness

The final Windows regression run on November 23, 2026 collected and passed **47 pytest tests**, with one existing Starlette test-client deprecation warning. The 41-test entry below describes the original approval backend. Phase 3 React brought the count to 43, and Phase 4 added four cases. ESLint, three Vitest tests, TypeScript, the Vite production build, and both Chromium end-to-end flows passed.

- Fixtures verify unverified resume import and provenance, the real-job preparation gate, rejection feedback without fact changes, and persisted scheduler metrics and deduplicated worker alerts.
- Chromium exercised a compiled tailored PDF, exact application preparation, copyable manual fields, unsupported-portal handling, duplicate-safe exact approval, bulk approval, and a persisted synthetic receipt. Tests used isolated SQLite data, synthetic employers, and mocked employer transport.
- A fresh migration completed through revision 0004 and Alembic found no outstanding operations. The existing database reports revision 0004 at head.
- The live dashboard rendered Profile, Approval Queue and the new reliability panel. Both existing Windows tasks were running, and the worker heartbeat advanced after the test browser closed. The observation window was under one hour at verification.
- Windows blocked the original PowerShell notification helper. The native notification process received the Windows Shell shown event for one synthetic alert in the interactive session. User acknowledgment and SMTP delivery were outside the verification.
- The real workspace had no enabled boards and lacked verified career evidence. No real application or live employer API call was tested.

[Public benchmark](JOB_MATCHING_EVALUATION.md) · [Scheduler observations](24_HOUR_RELIABILITY.md) · [Security audit](SECURITY_AUDIT.md)

## Phase 3 React workspace update

Verified November 23, 2026, on the installed Windows workspace. The full suite passed **43 tests** with the existing Starlette test-client deprecation warning. Two mocked Greenhouse transport tests failed on the first full run because their hooks still referenced the preparation module after transport moved into the provider adapter. Both were corrected and passed in the full rerun.

- ESLint, three Vitest tests, TypeScript and the production build passed.
- Chromium exercised exact single-click approval, version-specific PDF preview, idempotent replay, bulk selection after review, per-application payload hashes, the receipt, and persisted notifications. A final Chromium rerun also verified that an unsupported application appears in Exceptions. Employer traffic was restricted to synthetic fixtures and mocked transport.
- The previous-day summary test checked the configured time zone, excluded events beyond the day boundaries, and verified that a second worker tick did not add a second notification.
- Live Chromium checked approval filters, the automation mode, and the disabled employer control. Both registered Windows tasks reported running and the API reported a fresh worker heartbeat, an enabled 60-minute schedule, and dry-run mode.

| Area | Changed files |
| --- | --- |
| Review, exceptions and monitoring | `frontend/src/api.ts`, `frontend/src/domain.ts`, `frontend/src/pages/pipeline.tsx`, `frontend/src/pages/review-batch.tsx`, `frontend/src/pages/overview.tsx`, `frontend/src/pages/automation.tsx`, `frontend/src/pages/settings.tsx` |
| Preparation and delivery | `jobforge/api.py`, `jobforge/applications.py`, `jobforge/submission.py`, `jobforge/notifications.py`, `jobforge/worker.py`, `scripts/review-notification.ps1` |
| Regression coverage | `frontend/src/domain.test.ts`, `tests/test_autonomy.py`, `tests/test_final_submission.py`, `tests/test_workspace_e2e.py` |

Live Greenhouse dispatch still requires an employer-authorized sandbox contract test. Lever and Ashby use manual handoff in JobForge. Visible Windows alerts, SMTP delivery, and other browser engines were outside this verification run.

## One-click approval and submission

Verified on Windows on November 23, 2026. Development traffic used the local synthetic employer and mocked HTTP. Production employer dispatch stayed disabled throughout verification.

**Final result: 41 passed, 0 failed in 53.11 seconds.** The suite reported the existing Starlette test-client deprecation warning.

```powershell
Set-Location -LiteralPath 'D:\JOBFORGE AI'
$env:JOBFORGE_BROWSER_EXECUTABLE = 'C:/Program Files/Google/Chrome/Application/chrome.exe'
$env:OLLAMA_BASE_URL = 'http://127.0.0.1:11435'
$env:JOBFORGE_TEST_OLLAMA = 'qwen2.5:1.5b'
node --check jobforge/static/dashboard.js
./.venv/Scripts/python.exe -m pytest -q
./.venv/Scripts/python.exe -m alembic upgrade head
./.venv/Scripts/python.exe -m alembic check
./.venv/Scripts/python.exe -m alembic current
Invoke-RestMethod http://127.0.0.1:8000/health
```

The Chrome end-to-end test covers a scheduled synthetic preparation, real PDF, review, one-click final approval, worker dispatch, durable receipt, duplicate approval request, and outcome notification. The regression suite checks concurrent clicks, all-or-nothing bulk review, unsupported providers, eligibility and missing information, and the legacy synthetic workflow. It also verifies that resume, profile, answers and destination changes block stale approval, that a modified approval hash blocks dispatch, and that only read-only preflight retries occur after a timeout.

The Greenhouse contract test uses mocked HTTP and checks that the provider receives the exact approved fields and PDF only after a final approval. The prior standing-policy test now checks that even valid legacy policy data cannot queue or dispatch an application. The transport code for legacy policy dispatch was removed.

The SQLite database was backed up and checked before migration. Migration 0004 adds the snapshot, approvals, tasks, and notification records and disarms inherited standing-dispatch settings. Alembic reported no outstanding schema operations. Both Windows logon tasks restarted, the browser smoke passed against the task-hosted dashboard, and the running worker reported a 60-minute schedule with dry-run enabled.

| Area | Changed files |
|---|---|
| Backend and queue | `jobforge/api.py`, `jobforge/applications.py`, `jobforge/models.py`, `jobforge/notifications.py`, `jobforge/schemas.py`, `jobforge/submission.py`, `jobforge/worker.py` |
| Migration and native notifications | `migrations/versions/0004_final_approval.py`, `scripts/review-notification.ps1` |
| Dashboard | `jobforge/static/index.html`, `jobforge/static/dashboard.js` |
| Tests | `tests/conftest.py`, `tests/test_autonomy.py`, `tests/test_dashboard_e2e.py`, `tests/test_final_submission.py` |
| Documentation | `README.md`, `IMPLEMENTATION_STATUS.md`, `docs/APPROVAL_AND_SUBMISSION.md`, `docs/AUTONOMY_ARCHITECTURE.md`, `docs/SETUP.md`, `docs/SUBMISSION_PERMISSIONS.md`, `docs/TEST_REPORT.md` |

Employer-authorized Greenhouse sandbox behavior, visible Windows taskbar alert delivery, and SMTP delivery remain unverified. Dashboard notification persistence and desktop and email batching decisions are independently testable. [Approval workflow and provider capabilities](APPROVAL_AND_SUBMISSION.md)

## Autonomy upgrade

Windows verification on November 22, 2026 used the workspace's Python 3.12, Chrome, Tectonic, a real local Ollama endpoint, and SQLite. Production employer submission remained disabled. The only dispatch transports exercised were browser simulations and a mocked employer HTTP adapter.

### Automated checks

```powershell
Set-Location -LiteralPath 'D:\JOBFORGE AI'
$env:JOBFORGE_BROWSER_EXECUTABLE = 'C:/Program Files/Google/Chrome/Application/chrome.exe'
$env:OLLAMA_BASE_URL = 'http://127.0.0.1:11435'
$env:JOBFORGE_TEST_OLLAMA = 'qwen2.5:1.5b'
node --check jobforge/static/dashboard.js
./.venv/Scripts/python.exe -m alembic upgrade head
./.venv/Scripts/python.exe -m alembic check
./.venv/Scripts/python.exe -m pytest -q
./.venv/Scripts/python.exe -m scripts.evaluate_models qwen2.5:1.5b qwen2.5:3b
```

The final upgraded suite passed **30 tests in 48.78 seconds**, with one existing Starlette test-client deprecation warning. It checks a due scheduled run that discovers, compiles and prepares a synthetic job, plus approved submission and idempotent replay. It covers missing answers, a known textarea, blocked consent and human verification fixtures, a durable receipt when the confirmation page is unavailable, and continued use of the same PDF after an interrupted preparation. Further tests cover an actual process crash with controlled lease expiry, missed-run coalescing, pause/resume and cancellation, a failed source alongside a healthy source, bounded compilation retries, invalid LaTeX, mutated numeric claims, Ollama timeout and missing model fallback, and exact employer policy enforcement against mocked HTTP. Windows logon and boot task definitions are validated through the native Task Scheduler PowerShell module.

### Native Windows tasks

```powershell
./scripts/install-windows-tasks.ps1 -Plan
./scripts/install-windows-tasks.ps1 -Boot -Plan
./scripts/install-windows-tasks.ps1
Start-ScheduledTask -TaskName 'JobForge AI Dashboard'
Start-ScheduledTask -TaskName 'JobForge AI Worker'
Get-ScheduledTaskInfo -TaskName 'JobForge AI Worker'
Invoke-RestMethod http://127.0.0.1:8000/health
./scripts/install-windows-tasks.ps1 -Repair
```

The native logon tasks registered successfully and the dashboard returned HTTP 200 with the worker reporting a live heartbeat and the local model available. A queued dry-run tick completed under the scheduled process. The restart setting alone failed after a forced kill of the worker child on this host. A repeating watchdog relaunched the stopped process. A second forced-exit test verified a new child process and fresh heartbeat without a manual restart. A Chrome smoke test of the task-hosted Automation Control Center also passed. Boot registration stopped at the installer privilege check. No reboot, logout or sleep transition was performed.

### Model comparison

Both local models ranked the target project first on all five synthetic fixtures and compiled all five to clean, factual PDFs. The median was 2.30 seconds for Qwen2.5 1.5B and 4.08 seconds for Qwen2.5 3B, including compilation. [Evaluation method and limitations](AI_MODEL_EVALUATION.md)

### Changed files

| Area | Files |
|---|---|
| Job intake, requirements, and resumes | `jobforge/providers.py`, `jobforge/matching.py`, `jobforge/resumes.py`, `jobforge/llm.py` |
| Execution, state and policy | `jobforge/worker.py`, `jobforge/models.py`, `jobforge/schemas.py`, `jobforge/permissions.py`, `jobforge/greenhouse.py`, `jobforge/applications.py`, `jobforge/api.py`, `migrations/versions/0003_automation_checkpoints.py` |
| Dashboard and launch | `jobforge/static/index.html`, `jobforge/static/dashboard.js`, `jobforge/windows.py`, `scripts/install-windows-tasks.ps1`, `.env.example`, `docker-compose.yml` |
| Tests and evaluation | `tests/test_autonomy.py`, `tests/test_dashboard_e2e.py`, `tests/fixtures/model_evaluation.json`, `scripts/evaluate_models.py` |
| Documentation | `README.md`, `IMPLEMENTATION_STATUS.md`, `docs/SETUP.md`, `docs/TEST_REPORT.md`, `docs/AUTONOMY_ARCHITECTURE.md`, `docs/SCHEDULER_RECOVERY.md`, `docs/AI_MODEL_EVALUATION.md`, `docs/SUBMISSION_PERMISSIONS.md` |

The machine-local ignored `.env` records the existing Ollama endpoint and absolute compiler, Node, and browser paths so the installed tasks can run outside the development shell.

## Baseline verification

Verification date: November 22, 2026. Windows native, Python 3.12, SQLite, Playwright 1.65.2 with installed Chrome, Tectonic 0.17.0, and Ollama 0.40.17.

## Native application and automated tests

Commands run from the project directory:

```powershell
.venv/Scripts/python.exe -m jobforge.resumes
.venv/Scripts/python.exe -m alembic upgrade head
.venv/Scripts/python.exe -m alembic check
.venv/Scripts/python.exe -m pip check
node --check jobforge/static/dashboard.js
$env:JOBFORGE_BROWSER_EXECUTABLE='C:/Program Files/Google/Chrome/Application/chrome.exe'
$env:OLLAMA_BASE_URL='http://127.0.0.1:11435'
$env:JOBFORGE_TEST_OLLAMA='qwen2.5:1.5b'
.venv/Scripts/python.exe -m pytest -q
```

Tectonic bootstrap completed for both templates. Alembic reported no unrepresented model changes. Python package resolution and JavaScript syntax checks passed. The baseline run reported **19 passed in 22.66 seconds**. Tests cover PDF/TXT/TEX extraction, verified fact exclusion and provenance, both real PDF builds and text extraction, controlled LaTeX edits, normalized board fixtures, deduplication and JD history, scoring and ambiguous eligibility, duplicate queue admission, authorization, local data export and deletion, and a browser workflow against independent Uvicorn and worker processes.

The browser test checks scheduling, missing answers, preparation, PDF upload, approval before submit, mock confirmation and idempotent replay, timeline, manual job analysis, generated PDF preview, recompile, and overview counts. A security-hardening run caught a Chromium form-origin regression. The server now uses a same-origin referrer policy and the full browser workflow passed again. Test data stays in isolated SQLite files. The separate blank dashboard returned HTTP 200 on `http://127.0.0.1:8000/health` with dry-run enabled and a completed scheduled tick.

## Live public discovery

A separate SQLite instance called the public ATS endpoints directly, normalized their responses with JobForge adapters, ran the worker, and stored 1,272 listings. This was a point-in-time result. No company account or application credentials were used.

| Board | Listings |
|---|---:|
| Greenhouse, Stripe | 777 |
| Lever, Palantir | 308 |
| Ashby, Ramp | 187 |

The discovery run recorded zero errors, zero compiled resumes, and zero prepared applications with an empty profile. One official Lever job URL was also resolved through the vendored career-ops classifier and matched its stored listing identity.

## Local model probes

Ollama ran on loopback with cloud disabled. Two small local models were probed with the same synthetic profile and job description. SmolLM2 135M returned valid structured IDs, with a weaker relevance order. Qwen2.5 0.5B returned valid IDs, with the API project first and some unrelated facts still included. These were smoke probes on a single synthetic prompt. The default Qwen2.5 1.5B model passed the live structured-selection and one-page Tectonic PDF integration test with a verified synthetic profile.

To include the real Tectonic plus Ollama integration test, point at a running local Ollama and install the named model first:

```powershell
$env:OLLAMA_BASE_URL='http://127.0.0.1:11434'
$env:JOBFORGE_TEST_OLLAMA='qwen2.5:1.5b'
.venv/Scripts/python.exe -m pytest -q
```

## Verification limits

Docker Compose and PostgreSQL were unavailable on this Windows host. The authorized Greenhouse submission adapter was tested with mocked HTTP. No real application was submitted. No Anthropic, OpenAI-compatible paid provider, or SMTP call was made. The installed FastAPI test client emitted a Starlette deprecation warning for its use of httpx.
