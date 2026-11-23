# JobForge AI

## Activate a personal search

Open Activation to review original resume evidence, edit your preferences, and choose verified boards. One confirmation saves your choices and queues the first dry run. [Activation](http://127.0.0.1:8000/activation) · [Activation guide](docs/PHASE_7_ACTIVATION.md) · [Preparation workflow](docs/REAL_APPLICATION_PREPARATION.md)


## Intelligent job discovery

Verify and preview employer feeds in Settings. Job Intelligence explains the match, lists missing evidence, and shows preparation readiness. [Discovery](docs/INTELLIGENT_JOB_DISCOVERY.md) · [Matching](docs/MATCHING_ENGINE.md) · [Resume quality](docs/RESUME_OPTIMIZATION.md) · [Readiness](docs/APPLICATION_READINESS.md)


## Real-world readiness

Use Profile to verify your source facts, then choose public employer boards in Settings. The worker prepares eligible applications for review. [Onboarding and manual handoff](docs/REAL_WORLD_READINESS.md) · [Public benchmark](docs/JOB_MATCHING_EVALUATION.md) · [Reliability report](docs/24_HOUR_RELIABILITY.md)


JobForge is a local job-search workspace. Import a resume, verify source facts, score job descriptions, compile tailored LaTeX PDFs, and manage an application queue. A separate worker runs discovery and preparation with the dashboard closed. The rules fallback works without any API key.

**Start here** · [Setup for Windows, macOS, Linux, and Docker](docs/SETUP.md) · [Build the React workspace](docs/FRONTEND_INTEGRATION.md) · [Workspace test report](docs/UI_TEST_REPORT.md)

1. Build the React workspace, then start the server and worker using the setup guide. Open [the local dashboard](http://127.0.0.1:8000).
2. Open **Profile**, import PDF, TXT, or TEX, and verify the facts you want to use. Label your name **Name** in the personal category.
3. In **Job discovery**, add a description or supported job URL, then open **Resume Studio** for that role. Choose a template and generate a PDF. You can compile a margin revision, compare versions, download both formats, or draft a cover letter.
4. In **Settings**, add and enable public job boards. In **Automation**, set the interval and limits, pause or resume, and inspect heartbeat, model status, daily totals and run logs. Scheduled preparation runs without approval clicks.
5. For a synthetic walkthrough on an empty workspace, explicitly load the test profile from **Settings** in the [legacy dashboard](http://127.0.0.1:8000/legacy). In the React **Approval queue**, open the synthetic application, inspect the saved payload and PDF, then click **Approve & submit** once. For a batch, open each review, select the reviewed versions, and confirm the exact set. The worker records the `MOCK-` receipt in **History** and posts a notification.

The workspace starts in autonomous preparation with dry-run enabled. Windows Task Scheduler keeps the workspace running independently of a terminal. Resolve ambiguous eligibility, missing answers, blocked forms, or exhausted retries in the **Exception Queue**. Each live submission requires a separate approval bound to the application presented for review. The notification center summarizes the previous completed day when there was activity.

[Approval workflow](docs/APPROVAL_AND_SUBMISSION.md) · [Autonomy](docs/AUTONOMY_ARCHITECTURE.md) · [Windows recovery](docs/SCHEDULER_RECOVERY.md) · [Model evaluation](docs/AI_MODEL_EVALUATION.md) · [Submission permissions](docs/SUBMISSION_PERMISSIONS.md) · [Security](docs/SECURITY.md) · [Open-source reuse](docs/OPEN_SOURCE_REUSE.md)
