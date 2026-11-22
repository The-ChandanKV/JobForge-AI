# JobForge AI

JobForge is a local job-search workspace. Import a resume, verify source facts, score job descriptions, compile tailored LaTeX PDFs, and manage an application queue. A separate worker runs discovery and preparation with the dashboard closed. The rules fallback works without any API key.

**Start here** · [Setup for Windows, macOS, Linux, and Docker](docs/SETUP.md) · [Implementation status](IMPLEMENTATION_STATUS.md) · [Test report](docs/TEST_REPORT.md)

1. Start the server and worker using the setup guide. Open [the local dashboard](http://127.0.0.1:8000).
2. Open **Profile**, import PDF, TXT, or TEX, and verify the facts you want to use. Label your name **Name** in the personal category.
3. Open **Resume Studio** and paste a description or supported job URL. Analyze the posting, choose a template, and generate a PDF. You can compile a margin revision, compare versions, download both formats, or draft a cover letter.
4. In **Settings**, add and enable public job boards. In **Automation Control Center**, set the interval and limits, pause or resume, and inspect heartbeat, model status, daily totals and run logs. Scheduled preparation runs without approval clicks.
5. For a synthetic walkthrough on an empty workspace, use **Settings → Load synthetic test profile**. In **Approval Queue**, open the application preview, inspect the PDF and answer, then click **Approve & Submit**. The worker records the `MOCK-` receipt in **Applications** and posts a notification.

The workspace starts in autonomous preparation with dry-run enabled. Windows Task Scheduler keeps the workspace running independently of a terminal. Resolve ambiguous eligibility, missing answers, blocked forms, or exhausted retries in the **Exception Queue**. Each live submission requires a separate approval bound to the application presented for review.

[Approval workflow](docs/APPROVAL_AND_SUBMISSION.md) · [Autonomy](docs/AUTONOMY_ARCHITECTURE.md) · [Windows recovery](docs/SCHEDULER_RECOVERY.md) · [Model evaluation](docs/AI_MODEL_EVALUATION.md) · [Submission permissions](docs/SUBMISSION_PERMISSIONS.md) · [Security](docs/SECURITY.md) · [Open-source reuse](docs/OPEN_SOURCE_REUSE.md)
