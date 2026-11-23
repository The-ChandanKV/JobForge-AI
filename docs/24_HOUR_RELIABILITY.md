# 24-hour reliability

Visit **Automation → 24-hour reliability** or run the CLI from the installed project:

```powershell
.\.venv\Scripts\python.exe -m scripts.reliability_report
```

The report uses persisted scheduler cadence, scheduled run records, worker starts, heartbeat gaps and model health events. It counts schedule slots only from the captured baseline and incorporates recorded pauses and interval changes. Missed slots distinguish elapsed schedule time from admitted work. Job counts represent recorded run counters. Worker CPU excludes compiler and Ollama child processes. Peak RSS is the process high-water value recorded at run completion, when supported.

The real window began November 23, 2026 at 07:11 UTC. Both existing Windows Task Scheduler tasks were observed running, and the worker heartbeat advanced after the test browser closed. The live dashboard reported a partial observation window. There were zero scheduled runs in the first read after startup. This installation had no enabled employer boards during verification. Synthetic fixtures separately exercised the scheduling, preparation, and reporting code. The application continues collecting evidence so the rolling window can mature without an open browser or Codex session.

The elapsed observation, expected runs, actual runs, missed slots, success and failure counts, and workload metrics are displayed live. Physical sleep, reboot, and a complete 24-hour runtime remain outside this verification.
