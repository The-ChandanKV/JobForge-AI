# Scheduler and recovery

## Windows launcher

JobForge uses Windows Task Scheduler with separate dashboard and worker tasks under the installing account. The actions call the workspace virtual environment's `pythonw.exe` from the workspace directory. They use limited privileges, IgnoreNew for overlaps, no execution deadline, and five configured restart attempts at one-minute intervals. A repeating one-minute watchdog starts an exited process even when a hard kill fails to invoke the restart setting. Creation is separate from `-Start` so startup can be inspected first. Existing task names are preserved. Rotating task logs are under `data/windows-api.log` and `data/windows-worker.log`. [Microsoft Task Scheduler settings](https://learn.microsoft.com/en-us/powershell/module/scheduledtasks/new-scheduledtasksettingsset)

Interactive tasks start on account logon and run outside Codex and the development terminal. Boot tasks use the provisioning Windows account with password logon, because the workload needs network access and the account's compiler cache. An elevated PowerShell and that account's password are required. The account also needs the OS permissions for unattended task logon and access to the workspace, dependencies, and cache. Boot registration on this host stopped at the privilege check. A physical reboot, logout, and sleep cycle were not performed. [Windows setup commands](SETUP.md#windows)

## Schedule semantics

- The worker polls SQL every three seconds and renews an active lease every twenty seconds. A lease expires after two minutes. A heartbeat older than 45 seconds indicates a stopped or unreachable worker in the dashboard.
- Restart or wake-up coalesces overdue slots into one due run, records how many intervals were coalesced, and resumes the original interval cadence. A heartbeat gap is recorded as downtime without inferring its cause. Neither the worker nor the supplied tasks keep the machine awake.
- A process crash leaves an unfinished run until its lease expires. The next worker retries the same run ID once, subject to cancellation. The run and attempt counters are durable.
- Internal job attempts are reserved before the slow stage. Failed attempts wait for a later run and back off from two minutes to a capped hour. The application reuses still-valid PDFs, and resumes interrupted form preparation where safe. Exhaustion goes to the Exception Queue. Resetting a retry budget is an explicit operator action.
- Pause stops scheduled admission and cooperatively cancels a running scheduled run between bounded stages. Run Now can still prepare work while paused. Cancel applies to a specific run. An in-flight compiler, form operation or HTTP request completes or times out before its stage can stop.
- A dispatch checkpoint is committed before sending. The worker reconciles the stored receipt, or queues uncertainty if no evidence arrives. Recovery cannot replay a dispatch that may already have reached the employer.

The model heartbeat reports the installed local model or its absence. A worker with no model available can still run the deterministic workflow.
