# 24-hour reliability

Visit **Automation → 24-hour reliability** or run the CLI from the installed project:

```powershell
.\.venv\Scripts\python.exe -m scripts.reliability_report
```

The report uses persisted scheduler cadence, scheduled run records, worker starts, heartbeat gaps and model health events. It counts schedule slots only from the captured baseline and incorporates recorded pauses and interval changes. Missed slots distinguish elapsed schedule time from admitted work. Job counts represent recorded run counters. Worker CPU excludes compiler and Ollama child processes. Peak RSS is the process high-water value recorded at run completion, when supported.

The observed window began November 23, 2026 at 12:41 IST. At 23:16 IST, the live dashboard showed 10.584 of 24 hours observed, 11 expected slots, six scheduled runs that all completed, and five missed slots. It recorded six worker starts, eight heartbeat gaps, and zero Ollama unavailable transitions. Starts include validation reloads. The causes of the missed slots were not established.

The scheduled records reported zero newly saved jobs, eligible jobs, PDFs, and prepared applications in the observed window. The separate activation run saved one real job for eligibility review. Two later controlled public-board runs each scanned 2,357 listings and saved no duplicate records. Scheduled runs averaged 4.30 seconds across the window, which includes early runs with boards disabled. The scheduled records accumulated 6.09 worker CPU seconds and reached 136.00 MiB peak worker RSS. The later instrumented manual run reached 200.04 MiB peak worker RSS. [Phase 9 validation](PHASE_9_VALIDATION.md)

Both existing Windows Task Scheduler tasks were running and one worker process tree advanced its heartbeat. The application continues collecting observations without an open browser or Codex session. Isolated fault-injection tests covered process crash, lease expiry, restart recovery, source failures, and preparation retry budgets.

The elapsed observation, expected runs, actual runs, missed slots, success and failure counts, and workload metrics are displayed live. Physical sleep, reboot, and a complete 24-hour runtime remain outside this verification.
