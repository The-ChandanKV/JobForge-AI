import os
import sys
import tempfile
from pathlib import Path

import pytest


TEST_DATA = tempfile.TemporaryDirectory(prefix="jobforge-tests-")


def pytest_configure():
    os.environ["JOBFORGE_DATA"] = TEST_DATA.name
    os.environ["DATABASE_URL"] = f"sqlite:///{Path(TEST_DATA.name).as_posix()}/unit.sqlite3"
    os.environ["LLM_PROVIDER"] = "rules"
    os.environ["JOBFORGE_ACCESS_TOKEN"] = ""
    os.environ["JOBFORGE_GREENHOUSE_AUTHORIZED"] = "false"
    os.environ["JOBFORGE_EMAIL_ENABLED"] = "false"
    os.environ["JOBFORGE_DISABLE_DESKTOP_NOTIFICATIONS"] = "true"


def pytest_sessionfinish():
    models = sys.modules.get("jobforge.models")
    if models:
        models.engine.dispose()
    TEST_DATA.cleanup()


@pytest.fixture(scope="session")
def db_ready():
    from alembic import command
    from alembic.config import Config
    from jobforge.worker import initialize

    command.upgrade(Config("alembic.ini"), "head")
    initialize()
