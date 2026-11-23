# Setup

## First real preparation

Open Activation after starting the installed application. Review the existing original resume facts, save target preferences, and verify and enable the boards you choose. The first real run stays in dry-run. [Activation guide](PHASE_7_ACTIVATION.md)


## Enable intelligent discovery

Verify career evidence and set preferences in Profile. Open Settings → Discover employers, preview a verified source, then enable monitoring. Optional local model names configure semantic ranking and tailoring. The rules path remains available if a model is absent. [Discovery workflow](INTELLIGENT_JOB_DISCOVERY.md)


## Prepare a real workspace

Import and verify name, email, and at least one career fact in Profile. Configure and enable employer boards in Settings. The desktop notification channel runs through the native Windows shell in an interactive session. Run the privacy check before pushing and check the observation window from Automation. [Readiness](REAL_WORLD_READINESS.md) · [Privacy audit](SECURITY_AUDIT.md)


Build the React workspace before starting FastAPI on a non-Docker installation. The [frontend integration guide](FRONTEND_INTEGRATION.md) has the build and restart commands. Docker builds the workspace automatically.

For a verified employer integration, configure server credentials and enable individually approved Greenhouse submission in Settings. Follow the [provider authorization and dry-run instructions](SUBMISSION_PERMISSIONS.md).

## Prerequisites

Install Python 3.11 or newer, Node.js 20 or newer for supported URL intake, and put the Tectonic binary on PATH. For assisted simulations install Playwright Chromium or set `JOBFORGE_BROWSER_EXECUTABLE` to an installed Chromium-based browser. The setup script downloads dependencies and a TeX bundle once. Application compiles use the cached bundle. [Tectonic releases](https://github.com/tectonic-typesetting/tectonic/releases)

## Windows

Back up an existing workspace before updating it. Run the database integrity check and keep the verified backup private. The setup script preloads the trusted Tectonic template cache, including hyperref for new PDF contact links. [Backup commands](BACKUP_AND_RESTORE.md) · [Daily operations](OPERATIONS_GUIDE.md)

From PowerShell in the project directory:

```powershell
if (-not (Test-Path -LiteralPath .env)) { Copy-Item .env.example .env }
./scripts/setup.ps1
```

If Python resolves to the Microsoft Store alias, supply your Python executable using `-Python PATH`. If using installed Chrome, set its path in `.env` or in both shells and pass `-UseInstalledBrowser` to setup.

For an unattended install, keep using the Windows account that ran setup. If Node or Tectonic is only visible in the development shell, put its absolute executable path in `.env` as `JOBFORGE_NODE_BIN` or `TECTONIC_BIN`. Set `JOBFORGE_BROWSER_EXECUTABLE` to a local Chromium path when using a system browser. Migrate the existing workspace database before launching the updated tasks.

```powershell
Set-Location -LiteralPath 'D:\JOBFORGE AI'
./.venv/Scripts/python.exe -m alembic upgrade head
./scripts/install-windows-tasks.ps1 -Plan | Format-List
./scripts/install-windows-tasks.ps1 -Start
Get-ScheduledTask -TaskName 'JobForge AI Dashboard','JobForge AI Worker'
Get-ScheduledTaskInfo -TaskName 'JobForge AI Worker'
Invoke-RestMethod http://127.0.0.1:8000/health
Get-Content ./data/windows-worker.log -Tail 30
```

The installer preserves existing task names. Update a matching logon installation with `./scripts/install-windows-tasks.ps1 -Repair -Start`. Use `Start-ScheduledTask -TaskName 'JobForge AI Dashboard'` and `Start-ScheduledTask -TaskName 'JobForge AI Worker'` to start existing enabled entries directly. Stop foreground copies before starting their replacements. To shut down the task processes, call `Disable-ScheduledTask` then `Stop-ScheduledTask` with each exact name, otherwise the watchdog can relaunch them. Restore with `Enable-ScheduledTask` followed by `Start-ScheduledTask`. The dashboard Pause control leaves the worker online and stops scheduled work.

For a boot-start installation, use an elevated PowerShell under the same Windows account. Preview using `./scripts/install-windows-tasks.ps1 -Boot -Plan`. Install using `./scripts/install-windows-tasks.ps1 -Boot -Start`, then supply that account's password to the native prompt. For an existing logon install, inspect and stop the two exact tasks first. After confirming you intend to replace them, unregister both entries from Task Scheduler before registering the boot versions. The database is independent of task registration. An interactive logon task starts again at the next logon, while a boot task requires the computer and its configured account permissions to support unattended startup. [Scheduler recovery](SCHEDULER_RECOVERY.md)

To replace the existing JobForge logon entries with boot entries after reviewing the plan:

```powershell
foreach ($task in @('JobForge AI Dashboard', 'JobForge AI Worker')) {
    Disable-ScheduledTask -TaskName $task
    Stop-ScheduledTask -TaskName $task
    Unregister-ScheduledTask -TaskName $task -Confirm
}
./scripts/install-windows-tasks.ps1 -Boot -Start
```

For foreground development, use two terminals:

```powershell
# Terminal 1
./.venv/Scripts/python.exe -m uvicorn jobforge.api:app --host 127.0.0.1 --port 8000
# Terminal 2
./.venv/Scripts/python.exe -m jobforge.worker
```

## macOS and Linux

```sh
[ -f .env ] || cp .env.example .env
sh scripts/setup.sh
# Terminal 1
.venv/bin/python -m uvicorn jobforge.api:app --host 127.0.0.1 --port 8000
# Terminal 2
.venv/bin/python -m jobforge.worker
```

On supported Linux distributions missing Chromium libraries, use `.venv/bin/python -m playwright install --with-deps chromium`. Start services from the project directory so the same environment and database are used. For server ports other than 8000, set `JOBFORGE_MOCK_ORIGIN` to the actual local URL before starting both processes.

## Docker Compose

```sh
docker compose up -d --build
docker compose ps
docker compose logs -f backend worker
```

The backend serves both the API and dashboard on loopback port 8000. The same image runs the separate worker service. PostgreSQL holds the queue, schedule, records and private documents. Redis and a separate scheduler container are unnecessary because the worker and SQL transactions provide the queue and scheduling. Compose starts the backend after PostgreSQL becomes ready and starts the worker after the backend health check passes. Test the Compose build in your target environment before relying on it.

Optional containerized Ollama:

```sh
# Set COMPOSE_OLLAMA_BASE_URL=http://ollama:11434 in .env
docker compose --profile local-ai up -d --build
docker compose exec ollama ollama pull qwen2.5:1.5b
```

The default Compose Ollama address is the host gateway. Native host Ollama must listen on the interface the container can reach. Keep it accessible only to trusted local clients.

## Re-run tests

After native setup, install `requirements-dev.txt` using the virtual environment Python. Run `python -m pytest -q` with that interpreter. The browser test starts an isolated SQLite database, a backend and a worker. It uses Playwright Chromium or the browser executable configured in your shell. The [test report](TEST_REPORT.md) shows how to opt in to the local Ollama integration test.

## Configure native Ollama

Install [Ollama](https://ollama.com/download), start its local server and pull the same model configured in JobForge:

```sh
ollama serve
# In a separate terminal
ollama pull qwen2.5:1.5b
ollama list
```

Set `LLM_PROVIDER=ollama`, `OLLAMA_BASE_URL=http://127.0.0.1:11434` and `OLLAMA_MODEL=qwen2.5:1.5b` in `.env`. If compute or disk is constrained, `LLM_PROVIDER=rules` retains the core workflow. Model IDs are editable in Settings. Inference failures appear in Automation logs and trigger the rules fallback. Paid provider adapters require selecting the provider and supplying its API key and model explicitly. With these providers, job text and the relevant verified career facts can leave the device.

## Unattended runs and logs

Use Windows Task Scheduler, a separate service manager, or Compose to give the worker a lifecycle independent of Codex. If you require inference after a reboot, provision Ollama to start independently under the selected deployment account. A temporarily unavailable model falls back to Python rules. Use **Automation Control Center** for pause, resume, cancellation, worker and model status, daily summary, and execution history.

Local notifications appear in Automation logs. To opt in to a run-count email, configure the SMTP and recipient variables in the environment and set `JOBFORGE_EMAIL_ENABLED=true`. The SMTP server must support TLS from connection start. Each completed run attempts one summary delivery, with no attachments or personal data.

## Authorized employer integration

Use the submission permissions guide for employer evidence, credential setup, individual approval, caps, and reconciliation. Standard profile labels are **First name**, **Last name**, **Email** and, if required, **Phone**. The current installation remains in dry-run. [Submission permissions](SUBMISSION_PERMISSIONS.md)

For an upgrade, stop the previous dashboard and worker commands or tasks, back up the SQLite database, and run `./.venv/Scripts/python.exe -m alembic upgrade head` before starting both services. Migration `0004` preserves existing applications and disables standing dispatch settings. Refresh preparation from a legacy application review to capture an exact payload for the new workflow. [Approval workflow](APPROVAL_AND_SUBMISSION.md)

## Private deployment

The supplied configuration is a single-user, loopback deployment. Use `JOBFORGE_ACCESS_TOKEN` for a login on the loopback UI. Remote access requires a private tunnel that exposes the app through a local address on the client. There is no multi-user provisioning. Use separate instances and databases for separate users. Restrict filesystem and database permissions to the service account and manage credentials in the deployment environment.
