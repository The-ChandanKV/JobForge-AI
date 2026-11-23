# Backup and restore

Run these commands from the JobForge project directory in PowerShell. The database recovery utility works with the configured file-backed SQLite database. It checks SQLite integrity, foreign keys, and the recorded migration revision without printing row contents.

## Back up and verify

```powershell
.\.venv\Scripts\python.exe -m scripts.database_backup check
.\.venv\Scripts\python.exe -m scripts.database_backup backup --encrypt
.\.venv\Scripts\python.exe -m scripts.database_backup check '.\data\backups\<backup>.jfb'
```

SQLite's online backup API captures a consistent snapshot while the dashboard and worker are running, including committed WAL changes. The command verifies the archive before publishing it. Default filenames are timestamped under the ignored data directory. To choose a destination, pass `--to` with a new file path in an existing private directory on a filesystem that supports hard links, such as NTFS. Use encrypted backups for personal data. A plain backup uses SQLite format and relies on the destination's access controls and storage encryption.

`--encrypt` uses Windows DPAPI under the current Windows user. The tool protects the archive before writing it to disk. The signed-in Windows account and its DPAPI keys are needed to decrypt the backup, so test access before changing accounts or replacing the computer. The encrypted snapshot is processed in memory. A file alone is insufficient for disaster recovery unless the decrypting account or key recovery method remains available. Keep backups and the local `.env` out of Git and review access to the backups directory. [Microsoft DPAPI](https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata)

## Restore into an isolated file

```powershell
.\.venv\Scripts\python.exe -m scripts.database_backup restore '.\data\backups\<backup>.jfb' --to '.\data\restore-test.sqlite3'
.\.venv\Scripts\python.exe -m scripts.database_backup check '.\data\restore-test.sqlite3'
```

The destination must be new. The tool refuses the configured live database, existing files, and SQLite sidecar collisions. It verifies the isolated database before publication. The archive and live database remain available.

For incident recovery, keep the live database and its sidecars together, stop both scheduled tasks using the operations guide, and point a foreground dashboard at the recovered path. Keep the worker stopped during review. Check the migration revision and apply any needed migrations to the recovered copy. Review the saved profile and application timeline. Confirm dry-run in Settings before starting a worker from the recovered database. An older snapshot may precede a real dispatch or receipt. Reconcile affected records with the employer before issuing any new approval or re-enabling an authorized integration.

## Export and retention

Use **Settings → Review and system health** to export a readable copy. It contains personal information and does not replace a full database snapshot. The app preserves records and versions until you explicitly erase data. Backups and exports have their own retention. Review and remove copies under your own retention policy. For PostgreSQL use its native backup tooling and test restoration separately.
