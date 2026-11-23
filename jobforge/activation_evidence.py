"""Build a private, non-mutating evidence review from saved original resumes."""
import hashlib
import json
from functools import lru_cache

from sqlalchemy import select

from .models import Upload
from .profile import parse_file

STRUCTURED = {"CGPA", "Graduation year", "GitHub", "LinkedIn", "Portfolio", "Internship", "Achievement"}
SINGLETON = {"cgpa", "graduation year", "github", "linkedin", "portfolio"}
CAREER = {"education", "experience", "project", "skill", "certification"}
GROUPS = {"education": "Education", "skill": "Skills and technologies", "experience": "Professional experience",
          "project": "Projects", "certification": "Certifications", "other": "Other resume evidence", "personal": "Links"}


def key(value):
    return " ".join(value.casefold().split())


@lru_cache(maxsize=8)
def structured_facts(upload_id, name, blob):
    values = []
    try:
        facts = parse_file(name, blob, activation_review=True)
    except ValueError:
        return values
    for item in facts:
        if item.label in STRUCTURED:
            fact = item.model_dump()
            identity = hashlib.sha256(f"{upload_id}:{item.label}:{item.value}:{item.excerpt}".encode()).hexdigest()[:32]
            values.append({**fact, "id": identity, "source": "upload:" + upload_id})
    return values


def review(db, profile):
    uploads = db.scalars(select(Upload).order_by(Upload.created, Upload.id)).all()
    originals = {f"upload:{row.id}": {"id": row.id, "name": row.name} for row in uploads}
    groups = {}
    seen_ids = set()
    extra = {}
    for fact in [*profile.facts, *(fact for row in uploads for fact in structured_facts(row.id, row.name, row.blob))]:
        identity = fact["id"]
        label = fact["label"]
        if (identity in seen_ids or fact.get("unsupported") or
                (fact["category"] == "personal" and label not in {"GitHub", "LinkedIn", "Portfolio"})):
            continue
        original = originals.get(fact["source"])
        if not fact["verified"] and (not original or not fact.get("excerpt")):
            continue
        seen_ids.add(identity)
        category = fact["category"]
        tag = label if label in STRUCTURED else GROUPS.get(category, "Other resume evidence")
        group_key = (category, key(label), key(fact["value"]))
        if group_key not in groups:
            groups[group_key] = {"id": identity, "category": tag, "label": label, "value": fact["value"],
                                 "verified": fact["verified"], "career": category in CAREER,
                                 "conflict": key(label) if key(label) in SINGLETON else None, "evidence": []}
            extra[identity] = fact
        item = groups[group_key]
        item["verified"] |= fact["verified"]
        if original and fact.get("excerpt"):
            evidence = {"original": original, "excerpt": fact["excerpt"]}
            if evidence not in item["evidence"]:
                item["evidence"].append(evidence)
    counts = {}
    for item in groups.values():
        if item["conflict"]:
            counts[item["conflict"]] = counts.get(item["conflict"], 0) + 1
    for item in groups.values():
        if counts.get(item["conflict"], 0) < 2:
            item["conflict"] = None
    # Bind confirmation to the stored facts, preferences, and original IDs.
    snapshot = [profile.facts, profile.preferences, sorted(originals)]
    revision = hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()
    return {"revision": revision, "originals": list(originals.values()), "groups": list(groups.values())}, extra
