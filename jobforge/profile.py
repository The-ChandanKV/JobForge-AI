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
    "internships": "experience", "achievements": "other", "awards": "other",
}


def readiness(facts):
    verified = [fact for fact in facts if fact["verified"] and not fact.get("unsupported")]
    contacts = {fact["label"].casefold(): fact["value"].strip() for fact in verified if fact["category"] == "personal"}
    checks = {"Name": bool(contacts.get("name")),
              "Email": bool(re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", contacts.get("email", ""))),
              "Career evidence": any(fact["category"] in {"education", "experience", "project", "skill", "certification"}
                                     and fact["value"].strip() for fact in verified)}
    return {"ready": all(checks.values()), "checks": checks}


def parse_file(name, data, *, activation_review=False):
    return candidates(extract_text(name, data, include_pdf_links=activation_review), date_ranges=activation_review)


def extract_text(name, data, *, include_pdf_links=False):
    suffix = Path(name).suffix.lower()
    if not data or len(data) > MAX_UPLOAD:
        raise ValueError("Provide a non-empty file under 4 MB.")
    if suffix == ".pdf" and data.startswith(b"%PDF-"):
        with TemporaryDirectory(prefix="jobforge-import-") as tmp:
            file = Path(tmp) / "resume.pdf"
            file.write_bytes(data)
            try:
                command = [sys.executable, "-I", str(ROOT / "pdf_worker.py"), str(file)]
                if include_pdf_links:
                    command.append("--contact-links")
                result = subprocess.run(command,
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
    return text[:100_000]


def candidates(text, source="text", *, date_ranges=False):
    facts = []
    section = "other"
    seen = set()
    heading = ""
    for line in text.splitlines()[:300]:
        if len(facts) >= 146:
            break
        value = line.strip(" \t•–")
        if not value:
            continue
        prefix, separator, content = value.partition(":")
        if prefix.lower() in SECTIONS and (separator or not content):
            heading = prefix.lower()
            section = SECTIONS[heading]
            if not content.strip():
                continue
            value = content.strip()
        if heading == "education":
            cgpa = re.search(r"(?i)\b(?:CGPA|GPA)\s*[:=]?\s*(\d{1,2}(?:\.\d+)?(?:\s*/\s*\d{1,2}(?:\.\d+)?)?)", value)
            graduation = re.search(r"(?i)\b(?:graduation(?: year)?|graduat(?:ed|ing)(?: in)?|expected)\s*[:=]?\s*(20\d{2})\b", value)
            if not graduation and cgpa and date_ranges:
                graduation = re.search(r"\b20\d{2}\s*[-–—−\ufffd]\s*(20\d{2})\b", value)
            for title, match in (("CGPA", cgpa), ("Graduation year", graduation)):
                if match and (title, match[1]) not in seen:
                    seen.add((title, match[1]))
                    facts.append(Fact(category="education", label=title, value=match[1], source=source, excerpt=value[:1500]))
        if section == "other":
            for url in re.findall(r"https?://[^\s<>]+", value):
                url = url.rstrip(",.;)")
                if re.match(r"https?://(?:www\.)?github\.com/", url, re.I):
                    title = "GitHub"
                elif re.match(r"https?://(?:[a-z]{2,3}\.)?linkedin\.com/", url, re.I):
                    title = "LinkedIn"
                else:
                    title = "Portfolio"
                if (title, url) not in seen:
                    seen.add((title, url))
                    facts.append(Fact(category="personal", label=title, value=url[:1500], source=source, excerpt=value[:1500]))
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
                facts.append(Fact(category=section, label={"internships": "Internship", "awards": "Achievement", "achievements": "Achievement"}.get(heading, section.title()), value=part.strip()[:1500],
                                  source=source, excerpt=value[:1500]))
    return facts[:150]
