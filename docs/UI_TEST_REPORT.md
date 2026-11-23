# JobForge workspace test report

Verified November 23, 2026, on Windows using the original JobForge installation and Google Chrome through Playwright.

## Frontend

| Check | Result |
| --- | --- |
| `npm --prefix frontend run lint` | Passed |
| `npm --prefix frontend test` | 3 passed across 2 files |
| `npm --prefix frontend run build` | TypeScript check and Vite production build passed |
| Screenshot review | Reviewed the 1440 px desktop overview and 390 px mobile pipeline. Mobile job and application tables render as labeled rows. |

## Backend and browser integration

`python -m pytest -q --tb=short` reported **42 passed**. The existing Starlette `TestClient` emitted one dependency deprecation warning. Tests used isolated SQLite files, a local model where required, and local mock employers.

- Verified authenticated entry and refresh on every workspace route, API and asset 404s, and cross-origin write rejection.
- Exercised workspace search, persistent theme selection, mobile navigation, job creation, job filtering and shortlisting.
- Imported a source resume, generated a compact resume, checked PDF bytes and download, compared the original, and prepared an application.
- Confirmed the exact approval hash in the redesigned dialog, checked the queued response, and waited for the local worker to produce a simulation receipt. The manual application had no automated approval control.
- Saved automation settings and marked persisted notifications as read. The legacy dashboard browser test also passed.
- The isolated Chromium run reported zero browser console or uncaught page errors.

## Installed Windows application

Restarted the existing dashboard scheduled task and confirmed the redesigned workspace at `http://127.0.0.1:8000/`. The running FastAPI process served all 11 direct workspace routes, both hashed assets, the favicon, the legacy fallback and the original CSP. Live Chromium rendered Overview, navigated to Analytics and reloaded that nested route. Both existing scheduled tasks reported running, and the production API reported a running worker. The smoke check read live data and wrote only the normal sign-in cookie when authentication was configured.

Docker image builds and browser engines other than Chromium were outside this verification run. No test submitted a real employer application.
