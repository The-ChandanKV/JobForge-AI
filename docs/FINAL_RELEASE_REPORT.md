# Final release report

Verified on November 23, 2026 in the installed Windows workspace. The starting branch was clean at Phase 9 commit `08dba30`. The baseline suite passed 56 tests. The audit compared the implementation, database, Windows tasks, provider responses, existing operating instructions, and installed service.

## Status and release blockers

**Release acceptance is ACTIVATION_REQUIRED.** The installed capability is **READY_FOR_REAL_PREPARATION**. Its verified applicant profile, preferences, seven enabled boards, hourly worker, Ollama, and Tectonic are ready. Acceptance remains pending because no real posting has qualified and reached the Approval Queue. The installed workspace has 112 verified facts, including six education facts, a graduation-year fact, 67 skills and 18 project facts. Ten roles, one preferred location, an employment preference, and explicit remote discovery are saved. Applicant facts, preferences, and board choices were preserved.

| Priority | Finding | Disposition |
| --- | --- | --- |
| Release blocker | The saved role requires eligibility review. The latest run produced zero eligible matches and zero live packages. | Await a genuinely eligible posting. Keep existing hard eligibility and exact review gates. |
| High for recovery | There was no tested local snapshot and restore command. An old snapshot can predate a dispatch. | Verified online SQLite snapshots, optional Windows DPAPI, and isolated restore. Reconcile pending employer records before promoting an old snapshot. |
| High on shared machines | The listener is on loopback and the optional access token is unset. | Configure a local token if other users or processes share this host. The token-enabled browser suite verified private PDF access and cross-origin protection. |
| Operational | The observed schedule missed five slots. Full-day and physical power-state recovery are unverified. | The installed watchdog recovered both processes in 57.3 seconds. Rollup monitoring continues. |
| External integration | No authorized production Greenhouse board or employer-approved sandbox is configured. | Dry-run and manual external handoff remain active. The employer write path was tested with mocks only. |

The Activation page distinguishes `ACTIVATION_REQUIRED` for missing applicant or monitoring configuration, `DEVELOPMENT_READY` for incomplete runtime or submission configuration, and `READY_FOR_REAL_PREPARATION` for a healthy configured dry-run. `LIVE_SUBMISSION_AVAILABLE` requires a verified enabled Greenhouse board, deliberate non-dry-run mode, and operator-provided authorization and evidence configuration. Each application still requires exact final approval. Installed capability and release acceptance are reported independently.

## Real discovery and resume validation

The controlled run took 14.92 seconds. It scanned 2,357 public listings, filtered 2,356, rechecked one retained job, and saved no duplicate. There were zero eligible or shortlisted jobs, live resume versions, prepared applications, pending approvals, or submissions. The existing job remained available and required eligibility review. Its official posting specifies U.S.-based remote consideration, travel and minimum qualifications. Its numerical experience minimum remained unclear. [Employer posting](https://job-boards.greenhouse.io/anthropic/jobs/5462966008)

| Provider | Public read and normalization |
| --- | --- |
| Greenhouse | 2,302 postings across four enabled boards, all complete. Uses authorized board slug and numeric posting ID for any separately enabled write integration. |
| Lever | 245 Zoox postings in a separate read-only check. All 245 descriptions and unique canonical posting URLs were present. Both posting and application URLs matched the employer board. Zoox was not enabled. |
| Ashby | 31 Linear listings, complete. The adapter uses normalized locations, board-linked URLs and job fields when supplied. |
| SmartRecruiters | 12 Bosch listings, partial. Reads bounded listing detail, checks company identity, and preserves unseen aliases on a partial check. |
| Recruitee | 12 The Codest listings, complete. Uses the employer feed and reconstructs the HTTPS posting URL from the validated employer and offer slug. |

These public feeds worked without discovery credentials. Existing provider spacing is 0.5 seconds for Greenhouse, Lever and Ashby, 0.75 for SmartRecruiters, and 1.0 for Recruitee. The read transport bounds time and response size, disables redirects, and allows one retry for specified transient status codes or transport failures. The test used ordinary public reads and isolated retry fixtures. The worker retains original descriptions, canonical URLs and aliases, caches unchanged matching results, and reuses a validated resume when its provenance and target remain current. The provider endpoints used in this run still require feed reads to establish availability. [Zoox careers board](https://jobs.lever.co/zoox/)

An isolated PDF preview used the actual saved public JD and the verified applicant profile through local Ollama. It produced one page with extractable text, two named fonts, three validated contact annotations, 47 exact fact references, two represented matched skills, and zero unsupported claims or formatting warnings. Compact skill layout reduced the measured preview from two pages to one. The isolated preview was discarded, and the ineligible opening stayed out of live preparation. The synthetic browser workflow separately verified preparation, screening, Approval Queue and submission tracking without employer traffic.

## Windows operation, performance, and recovery

- The installed interactive logon dashboard and worker use the same workspace and IgnoreNew. After a deliberate idle process exit the Windows watchdog recovered both in 57.3 seconds. A single worker tree and advancing heartbeat were verified. The code reload reused the existing tasks and data.
- The real observation covered 10.883 hours, 11 expected schedule slots, six completed scheduled runs, zero failures, five missed slots, eight starts, nine heartbeat gaps, and zero Ollama unavailable transitions. The deliberate crash and reload contributed to the process events. The causes of earlier missed slots were not established. No reboot, logout or sleep cycle was performed.
- The controlled run recorded 14.50 seconds of discovery, 0.233 seconds of matching, 36 SQL statements consuming 0.0925 seconds, 3.72 worker CPU seconds, 199.23 MiB peak RSS and zero pending work after completion. The isolated preview took 5.48 seconds for fact selection and 1.22 seconds for compilation and validation. Live application preparation latency remains unmeasured.
- Existing Windows notifications had Shell delivery events. Isolated tests verified grouping for ready applications and submission outcomes. An application-ready alert has yet to occur for a live package. [Rolling observation](24_HOUR_RELIABILITY.md)

## Database and security

The live and fresh databases passed integrity and foreign key checks at migration 0004. SQLAlchemy pool pre-ping restored a closed SQLite connection in an isolated test. The application keeps foreign keys on and hides SQL parameter values from exception diagnostics.

A live online SQLite snapshot was encrypted with the current Windows user's DPAPI, verified, and restored into a separate file. Profile, uploads, job data, resumes, applications, approvals and receipt table counts and rows matched the snapshot comparison. The live database stayed in place. An isolated WAL regression covered plaintext and encrypted snapshots with non-empty fixture data, refusal to overwrite, and rejection of a corrupt archive. [Backup and restore](BACKUP_AND_RESTORE.md)

The Windows dashboard bound to 127.0.0.1. The data folder ACL had no broad allow entries for Everyone, Authenticated Users, or BUILTIN Users. Private PDF access, no-store responses, immutable approval binding and stale snapshot rejection were checked in the authenticated suite. Uploaded formats remain bounded, TeX uses trusted templates and an untrusted compiler mode, and external contact targets are constrained and verified in the PDF. Employer text cannot select tools or credentials. SQL parameters and secret values remain outside release output. [Operations](OPERATIONS_GUIDE.md) · [Limitations](KNOWN_LIMITATIONS.md)

## Test totals

The full Windows suite passed 62 pytest tests. The additional provider retry test passed separately. There were zero failures or skips and the existing Starlette deprecation warning remained. Three frontend tests, lint, TypeScript, the production build, isolated Playwright flows and the live ten-route smoke test passed. Native and isolated tests together covered restart, cooperative shutdown, scheduling overlap, missed runs, database reconnection, Ollama fallback, compilation failure and exact approval safeguards. An employer-approved production contract test and a complete live ready-package workflow are still outstanding. [Test report](TEST_REPORT.md)
