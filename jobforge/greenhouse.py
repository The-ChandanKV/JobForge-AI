"""Employer-authorized Greenhouse Job Board API integration."""
import hashlib
import json
import os
import re

import httpx

from .matching import profile_field

CONTACT_FIELDS = {"first_name": "First name", "last_name": "Last name", "email": "Email", "phone": "Phone"}
API_ORIGIN = "https://boards-api.greenhouse.io"


def authorized_board():
    board = os.getenv("JOBFORGE_GREENHOUSE_BOARD", "").lower()
    if (os.getenv("JOBFORGE_GREENHOUSE_AUTHORIZED") == "true" and os.getenv("JOBFORGE_GREENHOUSE_KEY")
            and re.fullmatch(r"[a-z0-9_-]{1,80}", board) and board != "internal"):
        return board
    return None


def verified_board():
    """Production access requires an operator-recorded employer authorization and sandbox evidence reference."""
    evidence = os.getenv("JOBFORGE_GREENHOUSE_VERIFICATION_REFERENCE", "").strip()
    return authorized_board() if 8 <= len(evidence) <= 200 else None


def verification_reference():
    return os.environ["JOBFORGE_GREENHOUSE_VERIFICATION_REFERENCE"].strip() if verified_board() else None


def endpoint(job):
    source_key = job.detail.get("source_key", job.source_key)
    match = re.fullmatch(r"greenhouse:([a-z0-9_-]{1,80}):([0-9]{1,18})", source_key)
    if job.detail["source"] == "greenhouse" and match and match[1] == authorized_board():
        return f"{API_ORIGIN}/v1/boards/{match[1]}/jobs/{match[2]}"


def digest(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


def preflight(client, job, profile):
    url = endpoint(job)
    if not url:
        raise ValueError("The exact employer board is outside the authorized integration.")
    response = client.get(url, params={"questions": "true"})
    response.raise_for_status()
    form = response.json()
    if str(form.get("id")) != url.split("/")[-1] or form.get("title") != job.role:
        raise ValueError("The employer job identity or title has changed.")
    questions = form.get("questions")
    if not isinstance(questions, list):
        raise ValueError("The employer form did not provide a question schema.")
    supported = {key: profile_field(profile.facts, label, "personal") for key, label in CONTACT_FIELDS.items()}
    fields = {field["name"] for question in questions for field in question.get("fields", [])}
    missing = []
    for key, value in supported.items():
        if key != "phone" or value:
            if value is not None and (len(value) > 255 or re.search(r"https?://", value, re.I)):
                missing.append(CONTACT_FIELDS[key])
    if not supported["email"] or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", supported["email"]):
        missing.append("Email")
    for key in ("first_name", "last_name", "email"):
        if not supported[key] or key not in fields:
            missing.append(CONTACT_FIELDS[key])
    if "resume" not in fields:
        missing.append("Resume attachment field")
    for question in questions:
        if question.get("required") is not True:
            continue
        if not any(field["name"] == "resume" and field.get("type") == "input_file"
                   or field.get("type") == "input_text" and supported.get(field["name"])
                   for field in question.get("fields", [])):
            missing.append("Employer-specific required field")
    compliance = form.get("data_compliance") or []
    if not isinstance(compliance, list) or any(not isinstance(row, dict) or
            any(row.get(key) for key in ("requires_consent", "requires_processing_consent",
                                         "requires_retention_consent", "requires_demographic_data_consent",
                                         "demographic_data_consent_applies"))
            for row in compliance):
        missing.append("Employer consent or attestation")
    for group in ("location_questions", "compliance", "education", "demographic_questions"):
        controls = form.get(group)
        if controls and (group != "demographic_questions" or isinstance(controls, dict) and controls.get("required")):
            missing.append("Additional employer requirements")
    payload = {key: val.strip() for key, val in supported.items() if key in fields and val and val.strip()}
    return url, payload, {
        "filled": [CONTACT_FIELDS[key] for key in payload] + (["Resume PDF"] if "resume" in fields else []),
        "missing": list(dict.fromkeys(missing)),
        "form_digest": digest({k: form.get(k) for k in (
            "id", "title", "updated_at", "questions", "data_compliance", "location_questions",
            "compliance", "education", "demographic_questions",
        )}),
        "answers_digest": digest(payload),
    }


def dispatch(client, url, payload, pdf):
    """Return transport evidence only when the provider explicitly acknowledges."""
    response = client.post(url, auth=(os.environ["JOBFORGE_GREENHOUSE_KEY"], ""),
                           data=payload, files={"resume": ("resume.pdf", pdf, "application/pdf")})
    response.raise_for_status()
    body = response.json()
    if not isinstance(body, dict):
        return None
    identity = str(body.get("application_id") or "")
    if re.fullmatch(r"[A-Za-z0-9_-]{1,90}", identity):
        return f"Greenhouse application {identity}"
    if body.get("success") is True:
        return f"Greenhouse acknowledgement SHA-256 {digest(body)}"
    return None
