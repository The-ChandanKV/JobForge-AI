
# UI integration audit

The recovery branch points to original commit `5967557`. The design source is `The-ChandanKV/screenshot-match` at `c54c657`. Its home route contained an external placeholder image. The repository supplied a dark/light shadcn token set, application shell styles, React components, draft API types, demo fixtures, and an unfinished roadmap. The application uses the source styles and shared Card, Button, and Badge components in a static React build. It uses the local implementation of FastAPI as the API contract.

| Workspace | Authoritative endpoints | Behavior and limits |
| --- | --- | --- |
| Overview | `GET /api/state` | Counts saved rows, qualified match evaluations, and persisted worker activity. Live data comes from the active SQLite database. |
| Jobs | `GET /api/state`, `GET /api/jobs/{id}`, `POST /api/jobs`, `PUT /api/jobs/{id}/status` | Lists and filters stored postings. Detail includes match evidence, hard eligibility flags, and requirements. Discovery remains a worker operation. |
| Pipeline and History | `GET /api/state`, `GET /api/applications/{id}/review`, `GET /api/applications/{id}/events`, `POST /api/applications/{id}/decision` | Displays actual stages, original description, and saved evidence. Employer outcomes are recorded only from permitted statuses. |
| Resume Studio | `POST /api/profile/upload`, `PUT /api/profile`, `GET/POST /api/jobs/{id}/resumes`, `GET /api/jobs/{id}/letter`, `GET /api/resumes/{id}/{pdf,tex}`, `POST /api/resumes/{id}/{compile,restore}`, `POST /api/jobs/{id}/prepare` | Compiles with the existing Python and LaTeX services. Imported facts start unverified. Prepared applications pin the selected resume version. |
| Automation | `GET /api/state`, `POST /api/runs`, `POST /api/runs/{id}/cancel`, `PUT /api/settings` | FastAPI queues work. The existing worker executes and records the outcome. Run summaries and logs are bounded in the snapshot. |
| Approvals | `GET/PUT /api/applications/{id}/review`, `POST /api/applications/{id}/approve-submit`, `POST /api/applications/{id}/decision` | Explicit confirmation uses the exact displayed payload hash. The server validates the snapshot and defers dispatch to the worker. |
| Exceptions | `GET /api/state`, `POST /api/jobs/{id}/retry`, review and decision endpoints above | Internal retry resets the job retry budget. An uncertain submission permits reconciliation and manual evidence where accepted by the server. |
| Analytics | `GET /api/state` | Uses persisted jobs, application records and the available recent run summaries. Current application status determines whether an outcome has been reported. |
| Settings and Profile | `GET /api/state`, `PUT /api/settings`, `PUT /api/profile`, `POST /api/profile/upload` | Saves existing models through Pydantic validation. Integration credentials stay in backend configuration. |
| Notifications | `GET /api/notifications`, `POST /api/notifications/read` | Displays the most recent 75 persisted notifications. The header uses the server unread count. |

`Job.status` and `Application.status` represent different records. The public application projection adds `review_status` so older `APPLICATION_PREPARED`, `NEEDS_REVIEW`, and `SKIPPED` rows can be displayed correctly. Job automation adds checkpoints, attempts, and retry timing. Final approval, submission task, receipt, and event records are independent of the displayed pipeline stage. The UI keeps simulation, external confirmation, and provider-verified submissions distinguishable.

The optional access token enters via the existing form and same-origin HttpOnly, SameSite strict cookie. FastAPI rejects cross-origin writes and applies the existing CSP to both shells. The SPA uses relative URLs, compiled CSS, SVG attributes, and explicit page routes.
