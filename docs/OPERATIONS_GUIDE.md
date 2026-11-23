# Daily operations

## Start and stop JobForge

From PowerShell in the project directory, start the two existing tasks. Open the dashboard after both show Running.

```powershell
$jobforgeTasks = 'JobForge AI Dashboard','JobForge AI Worker'
foreach ($taskName in $jobforgeTasks) {
    Enable-ScheduledTask -TaskName $taskName
    Start-ScheduledTask -TaskName $taskName
}
Get-ScheduledTask -TaskName $jobforgeTasks
```

The interactive tasks use the account that installed JobForge. They persist with the browser and Codex closed while Windows and required services remain available. For first installation and the elevated boot procedure, see the setup guide. [Dashboard](http://127.0.0.1:8000) · [Windows setup](SETUP.md#windows)

For normal maintenance, click **Pause schedule** in Automation and wait until **Queued or running** is zero. Disable the tasks before stopping them so the watchdog cannot relaunch them.

```powershell
foreach ($taskName in @('JobForge AI Dashboard','JobForge AI Worker')) {
    Disable-ScheduledTask -TaskName $taskName
    Stop-ScheduledTask -TaskName $taskName
}
```

Restart the tasks, then click **Resume schedule**. Check the next execution time and heartbeat. [Automation](http://127.0.0.1:8000/automation)

## Profile, boards, and discovery

1. Use **Profile** to import a PDF, TXT or TEX resume and maintain verified facts, contact details, and job preferences. Use **Activation** for the initial combined review. Correct unverified, stale, or conflicting facts there.
2. Choose and verify boards in **Activation** or **Settings → Discover employers**. Enable only boards you want monitored. Check **Source health** in Automation for complete, partial, or failed checks.
3. Save **Interval minutes** as **60** in Settings. Click **Run now** in Automation for one immediate pass. Use **Job discovery** to browse saved jobs and **Job Intelligence** to inspect eligibility.

[Profile](http://127.0.0.1:8000/profile) · [Activation](http://127.0.0.1:8000/activation) · [Settings](http://127.0.0.1:8000/settings)

## Resumes and applications

- **Resume Studio** shows each job's version history and exact PDF preview. Check the verified facts, page layout and contact links. Download the PDF or selected LaTeX version there.
- In **Approval queue**, inspect the current PDF, eligibility, answers, and destination. For the current dry-run workspace use the manual handoff. Click **Review & open application**, upload the inspected PDF on the employer's site, review and submit there yourself, and record the actual confirmation in JobForge.
- For a separately authorized, enabled Greenhouse integration, **Approve & submit** authorizes the displayed application only. If the PDF or answers change, inspect and approve the new version. For uncertain outcomes, verify with the employer before taking further action.
- Use **History** for recorded receipts, application timelines, interviews, offers, and rejections.

[Resume Studio](http://127.0.0.1:8000/resume-studio) · [Approval queue](http://127.0.0.1:8000/approvals) · [History](http://127.0.0.1:8000/history) · [Submission permissions](SUBMISSION_PERMISSIONS.md)

## Diagnose and recover

- Start in **Automation**. Check worker status, next execution, source health, run measurements, retry checkpoints, and execution logs. If a run saved zero eligible jobs, inspect **Exceptions** and **Job Intelligence** for specific requirements.
- If Ollama is unavailable, check the configured local service and model. If Tectonic cannot compile, check the executable path and run `python -m jobforge.resumes` in the project virtual environment to refresh the trusted template cache.
- Windows task logs are `data/windows-api.log` and `data/windows-worker.log`. The app's Notifications inbox groups health and application events. Treat log copies as private.
- Run the verified backup command periodically and before migrations. Test restore into an isolated file before relying on it for recovery.

[Exceptions](http://127.0.0.1:8000/exceptions) · [Notifications](http://127.0.0.1:8000/notifications) · [Backup and restore](BACKUP_AND_RESTORE.md)
