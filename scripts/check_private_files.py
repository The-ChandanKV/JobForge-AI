"""Check tracked files and historical paths without printing file contents."""
import re
import subprocess
from pathlib import Path, PurePosixPath


PATTERNS = {
    "private key": rb"-----BEGIN (?:[A-Z]+ )*PRIVATE KEY-----",
    "GitHub token": rb"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})\b",
    "OpenAI token": rb"\bsk-(?:proj-)?[A-Za-z0-9_-]{35,}\b",
    "AWS key ID": rb"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b",
    "credential assignment": rb"(?im)^(?:JOBFORGE_ACCESS_TOKEN|JOBFORGE_GREENHOUSE_KEY|JOBFORGE_SMTP_PASSWORD|OPENAI_API_KEY|ANTHROPIC_API_KEY)\s*=\s*[^\s#]{8,}",
}


def git(*args):
    return subprocess.check_output(["git", *args])


def names(data):
    return {value.strip() for value in data.decode("utf-8", errors="replace").split("\0") if value.strip()}


def private_path(name):
    path = PurePosixPath(name)
    return (
        any(part in {"data", "private", "resumes", "logs", "node_modules", ".venv"} for part in path.parts[:-1])
        or (path.name.startswith(".env") and path.name != ".env.example")
        or bool(re.search(r"\.(?:sqlite3?|db)(?:-wal|-shm)?$|\.(?:pdf|log|pem|key|pfx)$", path.name, re.I))
    )


def main():
    tracked = names(git("ls-files", "-z"))
    history = names(git("log", "--all", "--format=", "--name-only", "-z"))
    problems = {("private path", path) for path in tracked | history if private_path(path)}
    for name in sorted(tracked):
        path = Path(name)
        if not path.is_file() or path.stat().st_size > 5_000_000:
            continue
        contents = path.read_bytes()
        for kind, pattern in PATTERNS.items():
            if re.search(pattern, contents):
                problems.add((kind, name))
    if problems:
        for kind, path in sorted(problems):
            print(kind + " detected at " + path)
        raise SystemExit(1)
    print(f"Checked {len(tracked)} tracked files and {len(history)} historical paths. No flagged paths or token patterns.")


if __name__ == "__main__":
    main()
