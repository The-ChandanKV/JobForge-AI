import hashlib
import json
import os
import re
import subprocess
import unicodedata
from pathlib import Path
from tempfile import TemporaryDirectory

from jinja2 import Environment, FileSystemLoader, StrictUndefined
from pypdf import PdfReader

from .config import ROOT, TECTONIC
from .llm import select_facts
from .matching import contains, has_skill, profile_field
from .models import Log, Resume, Job

LATEX_CHARACTERS = {
    "\\": r"\textbackslash{}", "{": r"\{", "}": r"\}", "%": r"\%", "#": r"\#", "&": r"\&",
    "_": r"\_", "$": r"\$", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}",
    "<": r"\textless{}", ">": r"\textgreater{}",
}
SECTIONS = {
    "experience": "Experience", "project": "Projects", "education": "Education",
    "skill": "Skills", "certification": "Certifications", "other": "Additional Information",
}
CONTACT = {"email", "phone", "city", "country", "linkedin", "github", "portfolio"}
LAYOUT = re.compile(r"(?m)^(\\geometry\{margin=)(?:0\.[4-9]\d?|1(?:\.[0-2]\d?)?)in(\})$")
TEMPLATES = Environment(loader=FileSystemLoader(ROOT / "templates"), undefined=StrictUndefined,
                        autoescape=False, keep_trailing_newline=True)


def escape_latex(value):
    text = " ".join(str(value).split())
    return "".join(LATEX_CHARACTERS.get(char, char) for char in text if not unicodedata.category(char).startswith("C"))


TEMPLATES.filters["tex"] = escape_latex


def word_key(value):
    return "".join(ch for ch in unicodedata.normalize("NFKC", value).casefold() if ch.isalnum())


def edit_bullet(source):
    """Remove list markers and first-person boilerplate while preserving the remaining literal evidence."""
    text = " ".join(source.split())
    text = re.sub(r"^(?:[-*•]\s+)+", "", text)
    text = re.sub(r"^(?:I was |I am )(?=responsible for\b)", "", text, flags=re.I)
    text = re.sub(r"^I (?=(?:built|developed|implemented|designed|created|maintained|tested|deployed|wrote|"
                  r"improved|reduced|optimized|automated|contributed|supported|led|collaborated)\b)", "", text, flags=re.I)
    if re.match(r"^(?:responsible|built|developed|implemented|designed|created|maintained|tested|deployed|"
                r"wrote|improved|reduced|optimized|automated|contributed|supported|led|collaborated)\b", text):
        text = text[0].upper() + text[1:]
    return text or source


def compile_claims(claims, bullets):
    support = {fact["id"]: fact for fact in claims if fact["verified"]}
    rendered = {}
    for bullet in bullets:
        fact = support.get(bullet["fact_id"])
        if (not fact or fact["id"] in rendered or fact["category"] not in {"experience", "project"}
                or bullet["text"] != edit_bullet(fact["value"])):
            raise ValueError("Resume contains an unsupported bullet or changed source claim.")
        rendered[fact["id"]] = bullet["text"]
    return [{**f, "value": rendered.get(f["id"], f["value"])} for f in claims]


def posting_digest(job):
    fields = [job.role, job.company, job.detail.get("location"), job.detail["description"]]
    return hashlib.sha256(json.dumps(fields, ensure_ascii=False).encode("utf-8")).hexdigest()


def quality_report(job, rendered, bullets, checks):
    corpus = "\n".join(fact["value"] for fact in rendered)
    skills = job.match.get("matching_skills", [])
    return {
        "compile_status": "PASSED", "text_extractable": bool(checks["text_length"]),
        "represented_skills": [skill for skill in skills if has_skill(corpus, skill)],
        "missing_requirements": [skill for skill in job.match.get("required_skills", [])
                                 if skill not in skills or not has_skill(corpus, skill)],
        "eligibility_review": job.match.get("concerns", []),
        "unsupported_claims": 0,
        "long_bullets": sum(len(bullet["text"].split()) > 32 for bullet in bullets),
        "page_overflow": checks["pages"] > 1,
        "formatting_warnings": checks["warnings"],
        "sections_present": [title for category, title in SECTIONS.items() if any(fact["category"] == category for fact in rendered)],
        "page_count": checks["pages"], "fonts_detected": checks.get("fonts", []),
        "pdf_link_annotations": checks.get("links", 0),
    }


def compile_pdf(tex, expected, bootstrap=False):
    with TemporaryDirectory(prefix="jobforge-tex-") as folder:
        work = Path(folder)
        source = work / "resume.tex"
        source.write_text(tex, encoding="utf-8")
        args = [TECTONIC, "--untrusted", "--keep-logs", "--outdir", str(work)]
        bundle = os.getenv("TECTONIC_BUNDLE")
        if bundle:
            args.extend(["--bundle", bundle])
        if not bootstrap:
            args.append("--only-cached")
        args.append(str(source))
        env = {k: v for k, v in os.environ.items() if k.upper() in {
            "PATH", "HOME", "USERPROFILE", "LOCALAPPDATA", "SYSTEMROOT", "TEMP", "TMP",
            "FONTCONFIG_PATH", "XDG_CACHE_HOME", "TECTONIC_CACHE_DIR",
        }}
        try:
            completed = subprocess.run(args, cwd=work, env=env, capture_output=True, encoding="utf-8",
                                       errors="replace", timeout=70, check=False,
                                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except FileNotFoundError as exc:
            raise ValueError("Tectonic is missing. Install it and run the compiler bootstrap.") from exc
        except subprocess.TimeoutExpired as exc:
            raise ValueError("Tectonic compilation exceeded 70 seconds.") from exc
        document = work / "resume.pdf"
        if completed.returncode or not document.is_file():
            raise ValueError("Compilation failed. Run the compiler bootstrap if the cache is missing.")
        if document.stat().st_size > 5_000_000:
            raise ValueError("PDF exceeds 5 MB.")
        reader = PdfReader(document)
        page_count = len(reader.pages)
        if not 1 <= page_count <= 5:
            raise ValueError("Resume PDF must contain between one and five pages.")
        extracted = "\n".join(page.extract_text() or "" for page in reader.pages)
        normalized = word_key(extracted)
        if not normalized:
            raise ValueError("Generated PDF contains no extractable text.")
        missing = [f["id"] for f in expected if word_key(f["value"]) and word_key(f["value"]) not in normalized]
        if missing:
            raise ValueError("The PDF lost or altered verified text. Review facts " + ", ".join(missing[:6]))
        warnings = []
        if page_count > 1:
            warnings.append(f"Resume spans {page_count} pages.")
        log = work / "resume.log"
        if log.exists() and "Overfull" in log.read_text(encoding="utf-8", errors="replace"):
            warnings.append("Tectonic reported overfull content. Inspect the PDF margins.")
        font_names = set()
        links = 0
        for page in reader.pages:
            resources = page.get("/Resources")
            if resources:
                font_table = resources.get_object().get("/Font")
                if font_table:
                    for reference in font_table.get_object().values():
                        name = reference.get_object().get("/BaseFont")
                        if name:
                            font_names.add(str(name).lstrip("/").split("+")[-1])
            links += sum(ref.get_object().get("/Subtype") == "/Link" for ref in page.get("/Annots", []))
        if not font_names:
            warnings.append("No named fonts were detected in the PDF resources.")
        return document.read_bytes(), {"pages": page_count, "warnings": warnings, "text_length": len(extracted),
                                       "fonts": sorted(font_names), "links": links}


def generate(db, job, facts, options, request):
    name = profile_field(facts, "Name", "personal")
    if not name:
        raise ValueError("Verify a Name fact before generating a resume.")
    verified = [f for f in facts if f["verified"]]
    name_fact = next(f for f in verified if f["category"] == "personal" and f["label"].casefold() == "name")
    contact = [f for f in verified if f["category"] == "personal" and f["label"].casefold() in CONTACT]
    candidates = [f for f in verified if f["category"] in SECTIONS and f["id"] != name_fact["id"]]
    jd = job.detail["description"]
    keywords = job.match.get("matching_skills", [])
    candidates.sort(key=lambda f: -sum(contains(f["value"], word) for word in keywords))
    chosen, meta = select_facts(options, jd, candidates, request.instructions)
    meta = {**meta, "ranked_fact_ids": chosen or []}
    order = {identity: index for index, identity in enumerate(chosen or [])}
    ranked = sorted(candidates, key=lambda f: (-sum(has_skill(f["value"], skill) for skill in keywords),
                                                not f.get("prioritized"), order.get(f["id"], len(order))))
    selected = []
    limits = {"experience": 7, "project": 6, "skill": 24, "education": 6, "certification": 5}
    for category in SECTIONS:
        rows = [f for f in ranked if f["category"] == category]
        if category in {"experience", "project"} and keywords:
            relevant = [f for f in rows if any(has_skill(f["value"], skill) for skill in keywords)]
            if relevant:
                rows = relevant
        selected.extend(rows[:limits.get(category, 6)])
    claims = [name_fact, *contact, *selected]
    bullets = [{"fact_id": f["id"], "text": edit_bullet(f["value"]),
                "reason": "Removed first-person or list formatting without changing claims."
                          if edit_bullet(f["value"]) != f["value"] else "Retained verified source wording.",
                "skills": [skill for skill in keywords if has_skill(f["value"], skill)]} for f in selected
               if f["category"] in {"experience", "project"}]
    rendered = compile_claims(claims, bullets)
    sections = [(title, [f for f in rendered if f["category"] == category])
                for category, title in SECTIONS.items()]
    if not candidates:
        raise ValueError("Verify at least one education, experience, skill, or project fact.")
    tex = TEMPLATES.get_template(request.template + ".tex").render(name=name, contact=contact, sections=sections)
    pdf, checks = compile_pdf(tex, rendered)
    requirements = {key: job.match.get(key, []) for key in
                    ("required_skills", "preferred_skills", "matching_skills", "missing_skills", "alternative_skill_groups")}
    requirements["posting_requirements"] = job.match.get("requirement_evidence", {}).get("required", [])
    version = Resume(job_id=job.id, parent_id=request.parent_id, template=request.template, tex=tex, pdf=pdf,
                     report={**checks, "claims": claims, "bullets": bullets, "ai": meta, "posting_digest": posting_digest(job),
                             "target_requirements": requirements,
                             "quality": quality_report(job, rendered, bullets, checks)})
    db.add(version)
    db.add(Log(kind="resume", message="Resume PDF validated", detail={"job_id": job.id, "ai": meta, "pages": checks["pages"]}))
    if meta.get("reason"):
        db.add(Log(kind="provider", message="AI provider unavailable; rules selected resume ordering", detail=meta))
    db.flush()
    return version


def recompile(db, previous, tex):
    # Only the approved layout parameter can vary. The trusted preamble, claim
    # corpus and all TeX commands remain byte-identical to a generated version.
    def skeleton(value):
        return LAYOUT.sub(r"\1<margin>\2", value.replace("\r\n", "\n").strip())

    if skeleton(tex) != skeleton(previous.tex):
        raise ValueError("The editor accepts margin adjustments from 0.4 to 1.29 inches. Edit verified claims in Profile.")
    claims = previous.report["claims"]
    rendered = compile_claims(claims, previous.report.get("bullets", []))
    pdf, checks = compile_pdf(tex, rendered)
    quality = {**previous.report.get("quality", {}), "text_extractable": bool(checks["text_length"]),
               "page_overflow": checks["pages"] > 1, "formatting_warnings": checks["warnings"]}
    version = Resume(job_id=previous.job_id, parent_id=previous.id, template=previous.template, tex=tex, pdf=pdf,
                     report={**previous.report, **checks, "quality": quality})
    db.add(version)
    db.flush()
    return version


def cover_letter(job: Job, facts):
    name = profile_field(facts, "Name", "personal")
    if not name:
        raise ValueError("Verify a Name fact first.")
    skills = job.match.get("matching_skills", [])
    projects = job.match.get("relevant_projects", [])
    evidence = []
    if skills:
        evidence.append("My relevant skills include " + ", ".join(skills) + ".")
    evidence.extend(projects[:2])
    body = "\n\n".join(evidence)
    return f"Dear Hiring Team,\n\nI am applying for the {job.role} role at {job.company}.\n\n{body}\n\nSincerely,\n{name}"


def bootstrap():
    for style in ("classic", "compact"):
        tex = TEMPLATES.get_template(style + ".tex").render(
            name="Compiler bootstrap", contact=[], sections=[("Skills", [{"value": "Python and SQL"}])]
        )
        compile_pdf(tex, [], bootstrap=True)


if __name__ == "__main__":
    bootstrap()
