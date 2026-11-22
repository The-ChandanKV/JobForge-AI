import re
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from .config import MAX_UPLOAD, ROOT
from .schemas import Fact

SECTIONS = {
    "education": "education", "experience": "experience", "work experience": "experience",
    "professional experience": "experience", "employment": "experience", "skills": "skill",
    "technical skills": "skill", "projects": "project", "certifications": "certification",
}


def parse_file(name, data):
    suffix = Path(name).suffix.lower()
    if not data or len(data) > MAX_UPLOAD:
        raise ValueError("Provide a non-empty file under 4 MB.")
    if suffix == ".pdf" and data.startswith(b"%PDF-"):
        with TemporaryDirectory(prefix="jobforge-import-") as tmp:
            file = Path(tmp) / "resume.pdf"
            file.write_bytes(data)
            try:
                result = subprocess.run([sys.executable, "-I", str(ROOT / "pdf_worker.py"), str(file)],
                                        cwd=tmp, capture_output=True, timeout=15, check=True)
                text = result.stdout.decode()
            except (OSError, subprocess.SubprocessError) as exc:
                raise ValueError("Could not extract text from this PDF.") from exc
    elif suffix in {".txt", ".tex"}:
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValueError("Text and LaTeX uploads must use UTF-8.") from exc
        if "\x00" in text:
            raise ValueError("Invalid text file.")
        if suffix == ".tex":
            text = re.sub(r"(?m)(?<!\\)%.*$", "", text)
            if r"\begin{document}" in text:
                text = text.split(r"\begin{document}", 1)[1]
            text = re.sub(r"\\(?:begin|end)\{[^{}]*\}", "", text)
            text = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^]\n]*\])?", "", text)
            text = text.replace("{", "").replace("}", "")
    else:
        raise ValueError("Supported files are PDF, UTF-8 TXT, and TEX.")
    if not text.strip():
        raise ValueError("No selectable text found. Provide a text or LaTeX copy.")
    return candidates(text)


def candidates(text, source="text"):
    facts = []
    section = "other"
    for line in text.splitlines()[:300]:
        value = line.strip(" \t•–")
        if not value:
            continue
        if value.rstrip(":").lower() in SECTIONS:
            section = SECTIONS[value.rstrip(":").lower()]
            continue
        if section == "other" and not facts and len(value.split()) <= 6 and value.replace(" ", "").isalpha():
            facts.append(Fact(category="personal", label="Name", value=value[:1500], source=source, excerpt=value[:1500]))
            continue
        email = re.search(r"[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}", value)
        if email and section == "other":
            facts.append(Fact(category="personal", label="Email", value=email[0], source=source, excerpt=value[:1500]))
            continue
        if section == "other" and re.fullmatch(r"(?:phone:\s*)?\+?[\d() .-]{8,24}", value, flags=re.I):
            facts.append(Fact(category="personal", label="Phone", value=value.removeprefix("Phone:").strip(), source=source, excerpt=value))
            continue
        parts = re.split(r"[,;]", value) if section == "skill" else [value]
        for part in parts:
            if part.strip() and len(facts) < 150:
                facts.append(Fact(category=section, label=section.title(), value=part.strip()[:1500],
                                  source=source, excerpt=value[:1500]))
    return facts
