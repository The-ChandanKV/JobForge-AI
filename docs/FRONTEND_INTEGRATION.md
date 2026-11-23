
# JobForge workspace integration

FastAPI serves the React workspace and its hashed assets on port 8000. React Router handles known workspace paths, and FastAPI serves the production entry point for direct visits or refreshes. The existing login form, session cookie, CSP, cross-origin write checks, API paths, and worker remain in place. `/legacy` provides the original interface. A checkout without a production bundle also starts in the original interface.

## Build and start on Windows

Run these commands from the original project directory. Install Node.js 24 with npm if needed.

```powershell
Set-Location 'D:\JOBFORGE AI'
npm --prefix frontend ci
npm --prefix frontend run build
.\.venv\Scripts\python.exe -m uvicorn jobforge.api:app --host 127.0.0.1 --port 8000
```

If the dashboard task already owns port 8000, restart that task after building instead of launching another API process.

```powershell
Stop-ScheduledTask -TaskName 'JobForge AI Dashboard'
Start-ScheduledTask -TaskName 'JobForge AI Dashboard'
```

Open [the local dashboard](http://127.0.0.1:8000/). On a fresh Python installation, run `scripts/setup.ps1` before starting. The same existing worker process runs `python -m jobforge.worker`; Windows installations with the scheduled worker already running require no separate worker command. The Dockerfile builds the frontend in a separate Node stage and copies the static bundle to the Python runtime image.

## Implementation

- `frontend/src/pages/` contains the live workspace pages. `api.ts` supplies typed same-origin requests and `domain.ts` maps persisted statuses.
- `frontend/src/lovable.css` and `frontend/src/components/ui/` reuse the Lovable tokens, CSS and three shadcn components. `workspace.css` supplies responsive sizing and native dialog styles.
- `jobforge/api.py` serves explicit workspace routes and authenticated original resume downloads. The API contract and route matrix are in [the integration audit](UI_INTEGRATION_AUDIT.md).
- `tests/test_workspace_e2e.py` drives FastAPI and the real browser bundle using a temporary database and local mock employer. The legacy browser suite runs at `/legacy`.

## Operations and recovery

A secure submission uses the prepared application ID and exact hash shown on the confirmation screen. Queue acceptance and verification are separate statuses. Local simulation receipts and user-recorded external evidence have separate labels. No build or startup command enables submission settings.

Analytics use saved job and application records and the most recent backend run and log history. Interview and offer counts are current recorded outcomes. A run can report as active before its stage is available. Resume comparison shows saved source excerpts and supports downloading the entire original. Browser PDF preview depends on the installed browser's PDF viewer.

The recovery ref is `recovery/pre-lovable-ui`. Use [the original dashboard](http://127.0.0.1:8000/legacy) for immediate fallback. To run the pre-integration code, stop the dashboard task, switch the code to the recovery branch after preserving any working edits, then start the dashboard task again. The database, generated documents, settings and worker installation use the original paths.
