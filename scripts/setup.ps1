param(
    [string]$Python = "python",
    [switch]$UseInstalledBrowser
)
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
& $Python -m venv .venv
if ($LASTEXITCODE) { exit $LASTEXITCODE }
$JobForgePython = ".venv/Scripts/python.exe"
& $JobForgePython -m pip install -r requirements.txt
if ($LASTEXITCODE) { exit $LASTEXITCODE }
if (-not $UseInstalledBrowser) {
    & $JobForgePython -m playwright install chromium
    if ($LASTEXITCODE) { exit $LASTEXITCODE }
}
& $JobForgePython -m jobforge.resumes
if ($LASTEXITCODE) { exit $LASTEXITCODE }
& $JobForgePython -m alembic upgrade head
exit $LASTEXITCODE
