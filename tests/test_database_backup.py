import sqlite3
import sys
from contextlib import closing

import pytest

from scripts import database_backup
from jobforge.models import engine


@pytest.mark.parametrize("encrypt", [False, pytest.param(True, marks=pytest.mark.skipif(
    sys.platform != "win32", reason="Windows DPAPI is unavailable"))])
def test_online_wal_backup_verifies_and_restores_without_overwriting(tmp_path, encrypt):
    live = tmp_path / "live.sqlite3"
    archive = tmp_path / "snapshot.jfb"
    restored = tmp_path / "restore-test.sqlite3"
    with closing(sqlite3.connect(live)) as writer:
        writer.execute("PRAGMA journal_mode=WAL")
        writer.executescript("""
            CREATE TABLE alembic_version (version_num TEXT NOT NULL);
            INSERT INTO alembic_version VALUES ('0004');
            CREATE TABLE profiles (id INTEGER PRIMARY KEY, facts TEXT NOT NULL);
            CREATE TABLE resumes (id INTEGER PRIMARY KEY, profile_id INTEGER REFERENCES profiles(id), pdf BLOB);
            INSERT INTO profiles VALUES (1, 'synthetic facts');
            INSERT INTO resumes VALUES (1, 1, X'255044462D');
        """)
        assert database_backup.backup(live, archive, encrypt=encrypt) == "0004"
        assert archive.read_bytes().startswith(database_backup.ENCRYPTED_HEADER if encrypt else database_backup.SQLITE_HEADER)
        assert database_backup.verify_path(archive) == "0004"
        writer.execute("UPDATE profiles SET facts='newer live state'")
        writer.commit()
        assert database_backup.restore(archive, restored, live=live) == "0004"
        with closing(sqlite3.connect(restored)) as isolated:
            assert isolated.execute("SELECT facts FROM profiles").fetchone() == ("synthetic facts",)
            assert isolated.execute("SELECT pdf FROM resumes").fetchone() == (b"%PDF-",)
        assert writer.execute("SELECT facts FROM profiles").fetchone() == ("newer live state",)
        with pytest.raises(ValueError, match="configured live database"):
            database_backup.restore(archive, live, live=live)
        with pytest.raises(FileExistsError):
            database_backup.restore(archive, restored, live=live)


def test_invalid_backup_never_publishes_a_restore(tmp_path):
    bad = tmp_path / "corrupt.sqlite3"
    bad.write_bytes(database_backup.SQLITE_HEADER + b"invalid")
    target = tmp_path / "recover.sqlite3"
    with pytest.raises((sqlite3.DatabaseError, ValueError)):
        database_backup.restore(bad, target, live=tmp_path / "live.sqlite3")
    assert not target.exists() and not list(tmp_path.glob(".jobforge-*.tmp"))


def test_sqlite_pool_reconnects_with_foreign_keys_after_a_closed_connection(db_ready):
    with engine.connect() as connection:
        raw = connection.connection.driver_connection
    raw.close()
    with engine.connect() as connection:
        assert connection.connection.driver_connection is not raw
        assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1
        assert connection.exec_driver_sql("SELECT COUNT(*) FROM profiles").scalar_one() == 1
