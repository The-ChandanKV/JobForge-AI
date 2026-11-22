# Submission permissions

JobForge starts in `AUTONOMOUS_PREPARATION` with dry-run enabled. Discovery, matching, resume creation, PDF validation, and supported preparation run without per-job approval. Manual employer handoff remains available. The synthetic Playwright workflow retains explicit test approval and records an unmistakably synthetic receipt.

## Production integration gate

The Greenhouse endpoint is restricted to the credentialed employer board. Before enabling production, retain the employer's documented authorization for this API route, a successful employer-approved sandbox contract test including acknowledgment and timeout handling, and a private reference to that record. The operator sets `JOBFORGE_GREENHOUSE_BOARD`, `JOBFORGE_GREENHOUSE_KEY`, `JOBFORGE_GREENHOUSE_AUTHORIZED=true`, and `JOBFORGE_GREENHOUSE_VERIFICATION_REFERENCE`. The software checks the configured reference and board at runtime. The operator remains responsible for validating the evidence itself. [Greenhouse Job Board API](https://docs.greenhouse.io/job-board.html)

On this installation the employer adapter was tested with mocked transport and production submission stays off. The preflight accepts standard verified contact fields and the selected PDF. Unknown required screening questions, legal attestations, consent and unexpected form controls require user action. Public boards, arbitrary web pages, login gates and CAPTCHAs cannot authorize dispatch.

## Individual final approval

1. In **Automation**, choose **Authorized employer API** and enable individually approved submission for the verified board. Keep the configured daily submission limit.
2. Prepare the current form and review the official destination, verified fields and exact PDF in **Approval Queue**. Click **Approve & Submit** for that application.
3. The worker verifies the approval hash, eligibility, form and current verified facts. A distinct immutable approval is required for each selected application in a bulk review.
4. Set dry-run again to disable live dispatch before an attempt is reserved. Editing the queued application invalidates its approval. A provider request already in progress may need reconciliation.

Standing policies from earlier versions are retained as historical configuration. The current worker accepts final approval tasks exclusively. The workspace daily cap bounds Greenhouse dispatch attempts in the selected timezone. Lever, Ashby and other unconfigured portals use a manual handoff. [Approval workflow and provider matrix](APPROVAL_AND_SUBMISSION.md)

The application records one durable attempt before the external POST. An explicit receipt is required for confirmed status. A timeout, ambiguous acknowledgment, or crash after that checkpoint routes to reconciliation. The adapter never retries that POST automatically. An operator can enter a genuine employer confirmation reference after independent verification.
