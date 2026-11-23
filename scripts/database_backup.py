"""Create, verify, and restore local SQLite snapshots without replacing live data."""
import argparse
import os
import sqlite3
import sys
from contextlib import closing, contextmanager
from datetime import UTC, datetime
from pathlib import Path
from tempfile import mkstemp
from time import monotonic

from sqlalchemy.engine import make_url

from jobforge.config import DATA, DATABASE

ENCRYPTED_HEADER = b"JobForge SQLite DPAPI 1\n"
SQLITE_HEADER = b"SQLite format 3\x00"


def database_path():
    url = make_url(DATABASE)
    if url.get_backend_name() != "sqlite" or not url.database or url.database == ":memory:" or url.query:
        raise ValueError("This command requires a file-backed SQLite DATABASE_URL.")
    return Path(url.database).resolve()


def open_readonly(path):
    return sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=10)


def copy_snapshot(source, destination):
    deadline = monotonic() + 60

    def progress(status, _remaining, _total):
        if status != sqlite3.SQLITE_DONE and monotonic() >= deadline:
            raise TimeoutError("The database snapshot did not complete within 60 seconds.")

    source.backup(destination, pages=128, progress=progress)


def verify(db):
    contents = db.execute("PRAGMA integrity_check").fetchall()
    if contents != [("ok",)]:
        raise ValueError("SQLite integrity check failed.")
    if db.execute("PRAGMA foreign_key_check").fetchone() is not None:
        raise ValueError("SQLite foreign key check failed.")
    revision = db.execute("SELECT version_num FROM alembic_version").fetchall()
    if len(revision) != 1:
        raise ValueError("The database must contain one JobForge migration revision.")
    return revision[0][0]


def dpapi(data, *, encrypt):
    if sys.platform != "win32":
        raise ValueError("DPAPI encryption requires the Windows account that protects the backup.")
    import ctypes
    from ctypes import wintypes

    class Blob(ctypes.Structure):
        _fields_ = [("size", wintypes.DWORD), ("data", ctypes.POINTER(ctypes.c_ubyte))]

    buffer = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
    incoming = Blob(len(data), buffer)
    outgoing = Blob()
    crypt = ctypes.WinDLL("Crypt32", use_last_error=True)
    kernel = ctypes.WinDLL("Kernel32", use_last_error=True)
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    transform = crypt.CryptProtectData if encrypt else crypt.CryptUnprotectData
    transform.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                          ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    transform.restype = wintypes.BOOL
    if not transform(ctypes.byref(incoming), None, None, None, None, 1, ctypes.byref(outgoing)):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return ctypes.string_at(outgoing.data, outgoing.size)
    finally:
        kernel.LocalFree(outgoing.data)


def verify_path(path):
    with path.open("rb") as stream:
        header = stream.read(len(ENCRYPTED_HEADER))
    if header == ENCRYPTED_HEADER:
        image = dpapi(path.read_bytes()[len(ENCRYPTED_HEADER):], encrypt=False)
        if not image.startswith(SQLITE_HEADER):
            raise ValueError("Decrypted backup does not contain a SQLite database.")
        with closing(sqlite3.connect(":memory:")) as db:
            db.deserialize(image)
            return verify(db)
    if not header.startswith(SQLITE_HEADER):
        raise ValueError("Unrecognized backup format.")
    with closing(open_readonly(path)) as db:
        return verify(db)


@contextmanager
def new_destination(destination):
    destination = destination.resolve()
    if any(path.exists() for path in (destination, Path(str(destination) + "-wal"), Path(str(destination) + "-shm"))):
        raise FileExistsError("Destination or its SQLite sidecar already exists.")
    descriptor, name = mkstemp(prefix=".jobforge-", suffix=".tmp", dir=destination.parent)
    os.close(descriptor)
    temporary = Path(name)
    try:
        yield temporary
        with temporary.open("rb+") as stream:
            os.fsync(stream.fileno())
        # Link publication is atomic and fails if another process created the destination.
        os.link(temporary, destination)
    finally:
        temporary.unlink()


def backup(source, destination, *, encrypt=False):
    with closing(open_readonly(source)) as live, new_destination(destination) as temporary:
        name = ":memory:" if encrypt else temporary
        with closing(sqlite3.connect(name)) as snapshot:
            copy_snapshot(live, snapshot)
            if encrypt:
                # A WAL snapshot needs a rollback-format header before deserialize().
                snapshot.execute("PRAGMA temp_store=MEMORY")
                snapshot.execute("VACUUM")
                revision = verify(snapshot)
                temporary.write_bytes(ENCRYPTED_HEADER + dpapi(snapshot.serialize(), encrypt=True))
            else:
                snapshot.execute("PRAGMA journal_mode=DELETE")
                revision = verify(snapshot)
        if verify_path(temporary) != revision:
            raise ValueError("Backup verification found a migration mismatch.")
    return revision


def restore(source, destination, *, live):
    if destination.resolve() == live.resolve():
        raise ValueError("Restore into a new isolated path. The configured live database is protected.")
    with source.open("rb") as stream:
        prefix = stream.read(len(ENCRYPTED_HEADER))
    with new_destination(destination) as temporary:
        if prefix == ENCRYPTED_HEADER:
            temporary.write_bytes(dpapi(source.read_bytes()[len(ENCRYPTED_HEADER):], encrypt=False))
        elif prefix.startswith(SQLITE_HEADER):
            with closing(open_readonly(source)) as original, closing(sqlite3.connect(temporary)) as target:
                copy_snapshot(original, target)
                target.execute("PRAGMA journal_mode=DELETE")
        else:
            raise ValueError("Unrecognized backup format.")
        revision = verify_path(temporary)
    return revision


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("backup", help="Snapshot the configured SQLite database.")
    create.add_argument("--to", type=Path)
    create.add_argument("--encrypt", action="store_true", help="Protect with current-user Windows DPAPI.")
    check = commands.add_parser("check", help="Check SQLite integrity and foreign keys.")
    check.add_argument("file", nargs="?", type=Path)
    recover = commands.add_parser("restore", help="Verify and restore into a new isolated SQLite file.")
    recover.add_argument("file", type=Path)
    recover.add_argument("--to", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "check":
            revision = verify_path(args.file or database_path())
        elif args.command == "restore":
            revision = restore(args.file, args.to, live=database_path())
        else:
            destination = args.to
            if destination is None:
                folder = DATA / "backups"
                folder.mkdir(mode=0o700, exist_ok=True)
                stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
                extension = ".jfb" if args.encrypt else ".sqlite3"
                destination = folder / ("jobforge-" + stamp + extension)
            revision = backup(database_path(), destination, encrypt=args.encrypt)
            print(f"Backup created: {destination}")
        print(f"Integrity and foreign keys verified. Migration: {revision}.")
    except (OSError, ValueError, sqlite3.Error) as exc:
        parser.exit(1, f"Database recovery command failed: {exc}\n")


if __name__ == "__main__":
    main()
