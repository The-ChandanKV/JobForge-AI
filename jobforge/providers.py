import hashlib
import json
import os
import re
import subprocess
from threading import Lock
from time import monotonic, sleep
from xml.etree import ElementTree
from datetime import UTC, datetime
from html import unescape
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx
from bs4 import BeautifulSoup
from pydantic import ValidationError
from sqlalchemy import or_, select

from .config import ROOT
from .models import Job, JobDescription, JobSource, now
from .schemas import Intake, Posting, Source

API = {
    "greenhouse": "https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true",
    "lever": "https://api.lever.co/v0/postings/{board}?mode=json",
    "ashby": "https://api.ashbyhq.com/posting-api/job-board/{board}?includeCompensation=true",
    "smartrecruiters": "https://api.smartrecruiters.com/v1/companies/{board}/postings",
    "recruitee": "https://{board}.recruitee.com/api/feeds/offers.xml",
}


_rate_lock = Lock()
_next_request = {}
MIN_SPACING = {"greenhouse": .5, "lever": .5, "ashby": .5, "smartrecruiters": .75, "recruitee": 1.0}


def read_feed(provider, url, params=None):
    for attempt in range(2):
        with _rate_lock:
            moment = monotonic()
            next_at = max(moment, _next_request.get(provider, moment))
            _next_request[provider] = next_at + MIN_SPACING[provider]
        if next_at > moment:
            sleep(next_at - moment)
        try:
            kwargs = {"timeout": 12, "follow_redirects": False}
            if params is not None:
                kwargs["params"] = params
            with httpx.stream("GET", url, **kwargs) as response:
                response.raise_for_status()
                data = bytearray()
                for block in response.iter_bytes():
                    data.extend(block)
                    if len(data) > 30_000_000:
                        raise ValueError("Board response exceeds size limit")
                return bytes(data)
        except httpx.HTTPStatusError as exc:
            if attempt or exc.response.status_code not in {429, 502, 503, 504}:
                raise
            retry_after = exc.response.headers.get("Retry-After", "")
            if retry_after and (not retry_after.isdecimal() or int(retry_after) > 3):
                raise
            sleep(int(retry_after) if retry_after else 1)
        except httpx.TransportError:
            if attempt:
                raise
            sleep(1)
    raise RuntimeError("Provider retry policy exhausted")


def clean_html(value):
    if "&lt;" in (value or ""):
        value = unescape(value)
    soup = BeautifulSoup(value or "", "html.parser")
    for tag in soup(["script", "style", "template", "iframe"]):
        tag.decompose()
    for element in soup.find_all(["p", "li", "br", "div", "h1", "h2", "h3", "h4"]):
        element.insert_after("\n")
    return "\n".join(" ".join(line.split()) for line in soup.get_text().splitlines() if line.strip())


def safe_url(value):
    if not value or any(character.isspace() or ord(character) < 32 or character == "\\" for character in value):
        return None
    try:
        parts = urlsplit(value)
        return value if parts.scheme == "https" and parts.hostname and parts.username is None and parts.port in (None, 443) else None
    except ValueError:
        return None


def normalize(source, raw):
    provider = source.provider
    posted = None
    mode = ""
    salary = {}
    if provider == "greenhouse":
        description = raw.get("content")
        location = (raw.get("location") or {}).get("name")
        url = raw.get("absolute_url")
        application = url
        employment = ""
        posted = raw.get("first_published")
    elif provider == "lever":
        description = " ".join(
            str(fragment or "")
            for fragment in [
                raw.get("description"),
                *[item.get("content") for item in raw.get("lists") or []],
                raw.get("additional"),
            ]
        )
        categories = raw.get("categories") or {}
        location = ", ".join(dict.fromkeys(filter(None, [categories.get("location"), *(categories.get("allLocations") or [])])))
        url, application = raw.get("hostedUrl"), raw.get("applyUrl")
        employment = categories.get("commitment")
        mode = (raw.get("workplaceType") or "").lower()
        if raw.get("createdAt"):
            posted = datetime.fromtimestamp(raw["createdAt"] / 1000, UTC).isoformat()
        salary = raw.get("salaryRange") or {}
    elif provider == "smartrecruiters":
        sections = (raw.get("jobAd") or {}).get("sections") or {}
        description = "".join("<h2>" + title + "</h2>" + (sections.get(key) or {}).get("text", "")
                              for key, title in (("jobDescription", "Responsibilities"), ("qualifications", "Qualifications"),
                                                 ("additionalInformation", "Additional Information")))
        places = raw.get("location") or {}
        location = places.get("fullLocation") or ", ".join(filter(None, (places.get("city"), places.get("country"))))
        mode = "remote" if places.get("remote") else "hybrid" if places.get("hybrid") else ""
        company = raw.get("company") or {}
        if company.get("identifier", "").casefold() != source.board.casefold():
            raise ValueError("Posting company does not match the verified board")
        if not any((sections.get(key) or {}).get("text") for key in ("jobDescription", "qualifications")):
            raise ValueError("Posting detail has no description")
        url = raw.get("postingUrl") or raw.get("applyUrl")
        application = raw.get("applyUrl") or url
        employment, posted = (raw.get("typeOfEmployment") or {}).get("label"), raw.get("releasedDate")
    elif provider == "recruitee":
        description = (raw.get("description") or "") + "<h2>Requirements</h2>" + (raw.get("requirements") or "")
        location = raw.get("location") or raw.get("city")
        mode = next((value for key, value in (("remote", "remote"), ("hybrid", "hybrid"), ("on_site", "onsite"))
                     if raw.get(key) == "true"), "")
        slug = raw.get("slug") or ""
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,200}", slug):
            raise ValueError("Invalid offer slug")
        url = application = f"https://{source.board}.recruitee.com/o/{slug}"
        employment, posted = (raw.get("employment_type_code") or "").replace("_", " "), raw.get("published_at")
    else:
        description = raw.get("descriptionHtml") or raw.get("descriptionPlain")
        location = ", ".join(dict.fromkeys(filter(None, [
            raw.get("location"), *[entry.get("location") for entry in raw.get("secondaryLocations") or []]
        ])))
        url, application = raw.get("jobUrl"), raw.get("applyUrl")
        employment, posted = raw.get("employmentType"), raw.get("publishedAt")
        mode = (raw.get("workplaceType") or ("remote" if raw.get("isRemote") else "")).lower()
        compensation = raw.get("compensation") or {}
        annual = [
            row for row in compensation.get("summaryComponents") or []
            if row.get("compensationType") == "Salary" and row.get("interval") == "1 YEAR"
        ]
        if len(annual) == 1:
            salary = {"min": annual[0].get("minValue"), "max": annual[0].get("maxValue"),
                      "currency": annual[0].get("currencyCode"), "interval": "year"}
    raw_id = raw.get("id") or url
    if not raw_id:
        raise ValueError("Listing has no identifier")
    identifier = str(raw_id)
    if len(identifier) > 150:
        identifier = hashlib.sha256(identifier.encode()).hexdigest()
    if not mode and location and re.match(r"(?i)^remote\b", location):
        mode = "remote"
    mode = {"on-site": "onsite", "on site": "onsite", "unspecified": ""}.get(mode, mode)
    employment = re.sub(r"([a-z])([A-Z])", r"\1 \2", employment or "")
    annual = str(salary.get("interval", "")).lower() in {"year", "yearly", "annual", "per-year"}
    return Posting(
        source_key=f"{provider}:{source.board.lower()}:{identifier}", source=provider, company=source.company,
        role=raw.get("title") or raw.get("text") or raw.get("name") or "", location=location or "",
        employment=employment, work_mode=mode, posted=posted,
        deadline=raw.get("application_deadline") if provider == "greenhouse" else None, url=safe_url(url),
        apply_url=safe_url(application), description=clean_html(description)[:100_000],
        original_description=(description or "")[:500_000],
        salary_min=salary.get("min") if annual else None,
        salary_max=salary.get("max") if annual else None,
        salary_currency=salary.get("currency") or "",
    )


def fetch_board(source):
    if source.provider == "mock":
        return [Posting(
            source_key=f"mock:{source.board}:backend", source="mock", company=source.company,
            role="Graduate Backend Engineer", location="Remote", work_mode="remote", employment="Full-time",
            description="Synthetic employer fixture. Required skills: Python, SQL, FastAPI.\n"
                        "Build reliable services and improve API testing. Open to graduates.",
        )], True
    url = API[source.provider].format(board=source.board)
    complete = True
    if source.provider == "smartrecruiters":
        page = json.loads(read_feed(source.provider, url, {"limit": 12, "offset": 0, "q": source.search}))
        entries = page["content"]
        complete = not source.search.strip() and page.get("totalFound") == len(entries)
        rows = []
        for entry in entries[:12]:
            identifier = str(entry.get("id") or "")
            if not re.fullmatch(r"[A-Za-z0-9-]{1,80}", identifier):
                complete = False
                continue
            try:
                row = json.loads(read_feed(source.provider, url + "/" + identifier))
                if row.get("active") is True and row.get("visibility", "").upper() == "PUBLIC":
                    rows.append(row)
                else:
                    complete = False
            except (httpx.HTTPError, ValueError):
                complete = False
    elif source.provider == "recruitee":
        data = read_feed(source.provider, url).decode("utf-8-sig")
        if re.search(r"<!\s*(?:DOCTYPE|ENTITY)", data, re.I):
            raise ValueError("Unsafe board XML")
        root = ElementTree.fromstring(data)
        if root.tag != "offers":
            raise ValueError("Unexpected job feed XML")
        rows = [{field.tag: field.text or "" for field in offer} for offer in root.findall("offer")]
    else:
        payload = json.loads(read_feed(source.provider, url))
        rows = payload if source.provider == "lever" else payload["jobs"]
    if not isinstance(rows, list):
        raise ValueError("Expected a list of postings")
    result = []
    for raw in rows:
        if source.provider == "ashby" and raw.get("isListed") is False:
            continue
        try:
            result.append(normalize(source, raw))
        except (ValidationError, ValueError, OverflowError, TypeError, AttributeError):
            continue
    expected = sum(row.get("isListed") is not False for row in rows) if source.provider == "ashby" else len(rows)
    return result, complete and len(result) == expected


def canonicalize(url):
    if not url:
        return None
    parts = urlsplit(str(url))
    query = sorted(
        (k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if not k.lower().startswith("utm_") and k.lower() not in {"gh_src", "gclid", "fbclid"}
    )
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), urlencode(query), ""))


def fold(text):
    return " ".join(re.findall(r"\w+", text.casefold()))


def save_job(db, posting):
    canonical = canonicalize(posting.url)
    key = hashlib.sha256("|".join(map(fold, [posting.company, posting.role, posting.location])).encode()).hexdigest()
    source = db.get(JobSource, posting.source_key)
    job = db.get(Job, source.job_id) if source else None
    if job is None and canonical:
        job = db.scalar(select(Job).join(JobSource).where(
            or_(Job.canonical_url == canonical, JobSource.canonical_url == canonical)
        ).order_by(Job.created).limit(1))
    if not job and posting.location:
        # Independent postings from the same board can share title and location.
        same = db.scalars(select(Job).where(Job.fingerprint == key)).all()
        job = next((row for row in same if row.detail["source"] != posting.source
                    and fold(row.detail["description"]) == fold(posting.description)), None)
    if job is None:
        job = Job(source_key=posting.source_key, canonical_url=canonical, fingerprint=key,
                  company=posting.company, role=posting.role, detail={})
        db.add(job)
        db.flush()
    if job.source_key == posting.source_key or job.detail.get("source") == "manual":
        job.detail = posting.model_dump(mode="json", exclude={"original_description"})
        job.role, job.company, job.fingerprint = posting.role, posting.company, key
    job.available, job.verified = True, now()
    if source is None:
        source = JobSource(key=posting.source_key, job_id=job.id)
        db.add(source)
    source.canonical_url, source.verified, source.available = canonical, job.verified, True
    original = posting.original_description or posting.description
    digest = hashlib.sha256(original.encode()).hexdigest()
    if not db.scalar(select(JobDescription.id).where(JobDescription.job_id == job.id, JobDescription.digest == digest)):
        db.add(JobDescription(job_id=job.id, digest=digest, description=original))
    return job


def intake(payload: Intake, sources):
    if payload.description.strip():
        value = payload.description.strip()
        identity = hashlib.sha256(f"{payload.company}|{payload.role}|{value}".encode()).hexdigest()
        return Posting(source_key=f"manual:{identity}", source="manual", company=payload.company,
                       role=payload.role, description=value, url=payload.url, apply_url=payload.url)
    if not payload.url:
        raise ValueError("Paste a description or provide a supported job URL.")
    url = str(payload.url)
    script = ROOT / "vendor" / "route.mjs"
    try:
        vendor = subprocess.check_output([os.getenv("JOBFORGE_NODE_BIN", "node"), str(script), url],
                                         timeout=5, text=True,
                                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).strip()
    except (OSError, subprocess.SubprocessError) as exc:
        raise ValueError("Node.js is required to route job URLs.") from exc
    parts = urlsplit(url)
    segments = parts.path.strip("/").split("/")
    if vendor not in API or len(segments) < 2:
        raise ValueError("Use a Greenhouse, Lever, or Ashby job URL, or paste the description.")
    board = segments[0]
    source = next((src for src in sources if src.provider == vendor and src.board.lower() == board.lower()), None)
    if source is None:
        company = board if payload.company == "Manual entry" else payload.company
        source = Source(provider=vendor, board=board, company=company)
    identifier = segments[2] if vendor == "greenhouse" and len(segments) >= 3 else segments[1]
    postings, _ = fetch_board(source)
    for posting in postings:
        if canonicalize(posting.url) == canonicalize(url) or posting.source_key.rsplit(":", 1)[-1] == identifier:
            return posting
        if vendor == "ashby" and posting.url and urlsplit(str(posting.url)).path.split("/")[-1] == identifier:
            return posting
    raise ValueError("This posting was not found in the public board feed.")
