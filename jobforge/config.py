import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
ROOT = Path(__file__).resolve().parent
DATA = Path(os.getenv("JOBFORGE_DATA", "data")).resolve()
DATA.mkdir(mode=0o700, parents=True, exist_ok=True)
DATABASE = os.getenv("DATABASE_URL", f"sqlite:///{DATA.as_posix()}/jobforge.sqlite3")
ACCESS_TOKEN = os.getenv("JOBFORGE_ACCESS_TOKEN", "")
TECTONIC = os.getenv("TECTONIC_BIN", "tectonic")
MAX_UPLOAD = 4 * 1024 * 1024
