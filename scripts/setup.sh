#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")/.."
"${JOBFORGE_PYTHON:-python3}" -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m playwright install chromium
.venv/bin/python -m jobforge.resumes
.venv/bin/python -m alembic upgrade head
