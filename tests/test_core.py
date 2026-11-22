import io
import json

import httpx
import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader
from sqlalchemy import select

from jobforge import llm
from jobforge.api import app
from jobforge.applications import expected_pdf, still_verified
from jobforge.matching import analyze, shortlist
from jobforge.models import JobDescription, Profile, Run, Session
from jobforge.profile import parse_file
from jobforge.providers import canonicalize, fetch_board, normalize, save_job
from jobforge.resumes import compile_pdf, escape_latex, generate, recompile
from jobforge.schemas import Fact, Generation, Options, Posting, Preferences, Source
from jobforge.worker import lease, queue


def fact(category, value, label="Fact", verified=True):
    return Fact(category=category, label=label, value=value, verified=verified).model_dump()


def posting(**fields):
    values = {"source_key": "test:1", "source": "test", "role": "Backend Engineer",
              "company": "Fixture Inc", "description": "Required skills: Python, SQL."}
    return Posting(**{**values, **fields})


def test_profile_extract_and_provenance():
    result = parse_file("profile.txt", b"Jordan Rao\njordan@example.test\nSkills\nPython, SQL\nProjects\nAPI tests")
    assert [(item.category, item.value) for item in result] == [
        ("personal", "Jordan Rao"), ("personal", "jordan@example.test"),
        ("skill", "Python"), ("skill", "SQL"), ("project", "API tests"),
    ]
    assert not any(item.verified for item in result)
    assert result[2].excerpt == "Python, SQL"
    tex = br"\documentclass{article}\begin{document}Jordan Rao" + b"\n" + br"\section{Skills}" + b"\nPython"
    assert parse_file("profile.tex", tex)[1].category == "skill"
    with pytest.raises(ValueError, match="Supported files"):
        parse_file("resume.pdf", b"<script>invalid</script>")


@pytest.mark.parametrize(("provider", "raw"), [
    ("greenhouse", {"id": 123, "title": "Engineer", "content": "<p>API work</p>",
                    "location": {"name": "Remote"}, "absolute_url": "https://boards.greenhouse.io/org/jobs/123"}),
    ("lever", {"id": "123", "text": "Engineer", "description": "<p>API work</p>",
               "categories": {"location": "Remote"}, "hostedUrl": "https://jobs.lever.co/org/123"}),
    ("ashby", {"title": "Engineer", "descriptionHtml": "<p>API work</p>",
               "location": "Remote", "jobUrl": "https://jobs.ashbyhq.com/org/123"}),
])
def test_public_board_normalization(provider, raw):
    parsed = normalize(Source(provider=provider, board="org", company="Fixture Inc"), raw)
    assert parsed.description == "API work" and parsed.location == "Remote"
    assert parsed.role == "Engineer" and parsed.source == provider
    assert parsed.posted is None and parsed.salary_min is None


def test_ashby_normalizes_structured_annual_salary_and_work_mode():
    source = Source(provider="ashby", board="fixture", company="Fixture")
    normalized = normalize(source, {
        "title": "Engineer", "descriptionHtml": "<p>API work</p>", "location": "Toronto",
        "secondaryLocations": [{"location": "Ottawa"}], "workplaceType": "On-site", "employmentType": "FullTime",
        "jobUrl": "https://jobs.ashbyhq.com/fixture/123",
        "compensation": {"summaryComponents": [
            {"compensationType": "Salary", "interval": "1 YEAR", "minValue": 70000, "maxValue": 89000,
             "currencyCode": "CAD"},
            {"compensationType": "Bonus", "interval": "1 YEAR", "minValue": 5000, "maxValue": 5000},
        ]},
    })
    assert (normalized.salary_min, normalized.salary_max, normalized.salary_currency) == (70000, 89000, "CAD")
    assert normalized.work_mode == "onsite" and normalized.employment == "Full Time"
    assert shortlist(normalized, Preferences(locations=["Ottawa"], min_salary=85000, salary_currency="CAD"))
    assert not shortlist(normalized, Preferences(min_salary=90000, salary_currency="CAD"))


def test_dedup_preserves_history_and_distinct_role(db_ready):
    assert canonicalize("https://example.com/jobs/1?utm_source=alert&gh_jid=4#x") == "https://example.com/jobs/1?gh_jid=4"
    with Session.begin() as db:
        origin = posting(url="https://example.com/jobs/a?utm_source=mail", location="Remote")
        first = save_job(db, origin)
        again = save_job(db, posting(description="Required skills: Python.",
                                     url="https://example.com/jobs/a", location="Remote"))
        distinct = save_job(db, posting(source_key="test:2", location="Remote", url="https://example.com/jobs/b"))
        assert first.id == again.id != distinct.id
        assert len(db.scalars(select(JobDescription).where(JobDescription.job_id == first.id)).all()) == 2


def test_eligibility_and_explainable_score():
    desired = Preferences(roles=["Backend Engineer"])
    facts = [fact("skill", "Python"), fact("skill", "SQL", verified=False),
             fact("project", "Designed Python APIs."), fact("experience", "2", "Years of experience")]
    results = analyze(posting(), facts, desired, 80)
    assert results["eligibility"] == "NEEDS_REVIEW"
    assert results["missing_skills"] == ["SQL"]
    assert results["match_score"] == sum(results["components"].values())
    too_senior = posting(description="Must have at least 5 years of professional experience.")
    assert analyze(too_senior, facts, desired, 80)["eligibility"] == "INELIGIBLE"
    assert analyze(too_senior, facts[:-1], desired, 80)["eligibility"] == "NEEDS_REVIEW"
    assert not shortlist(posting(), Preferences(recent_days=5))
    assert shortlist(posting(), desired)


def test_tex_escapes_all_control_characters():
    rendered = escape_latex(r"Use \input{private} & 20% #_ ^ ~$")
    for marker in (r"\textbackslash{}", r"\{private\}", r"\&", r"\%", r"\#", r"\_",
                   r"\textasciicircum{}", r"\textasciitilde{}", r"\$"):
        assert marker in rendered
    assert r"\input" not in rendered


@pytest.mark.parametrize("template", ["classic", "compact"])
def test_real_pdf_provenance_and_editor(db_ready, template):
    name = fact("personal", "Jordan Rao", "Name")
    project = fact("project", "Built 2 FastAPI services & improved coverage by 15%.")
    unverified = fact("project", "Operated a secret spacecraft.", verified=False)
    with Session.begin() as db:
        job = save_job(db, posting(source_key="pdf:" + template, role="PDF " + template))
        job.match = {"matching_skills": ["FastAPI"]}
        version = generate(db, job, [name, project, unverified], Options(provider="rules"), Generation(template=template))
        pdf = PdfReader(io.BytesIO(version.pdf))
        text = pdf.pages[0].extract_text()
        assert "FastAPI services & improved coverage by 15%" in text
        assert "spacecraft" not in version.tex
        assert [claim["id"] for claim in version.report["claims"]] == [name["id"], project["id"]]
        assert all(not item.verified for item in parse_file("resume.pdf", version.pdf))
        assert still_verified(Profile(facts=[name, project]), version)
        assert not still_verified(Profile(facts=[name]), version)
        assert expected_pdf(version.pdf, version.pdf) and not expected_pdf(b"another", version.pdf)
        edited = recompile(db, version, version.tex.replace("margin=0.75in", "margin=0.91in").replace("margin=0.60in", "margin=0.91in"))
        assert edited.parent_id == version.id and edited.report["claims"] == version.report["claims"]
        with pytest.raises(ValueError, match="margin adjustments"):
            recompile(db, version, version.tex.replace("Jordan", r"\input{secrets}"))
        with pytest.raises(ValueError, match="lost or altered"):
            compile_pdf(version.tex.replace("15", "99"), [project])


def test_ollama_shape_and_unknown_fact_rejection(monkeypatch):
    fact_row = fact("skill", "Python")
    requests = []

    def handler(request):
        payload = json.loads(request.content)
        requests.append(payload)
        if request.url.path == "/api/show":
            return httpx.Response(200, json={"capabilities": ["completion"]})
        assert payload["format"]["properties"]["fact_ids"]
        return httpx.Response(200, json={"message": {"content": json.dumps({"fact_ids": [fact_row["id"]]})},
                                       "eval_count": 12})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result, usage = llm.completion(client, "ollama", "qwen-test", "instructions", "candidate")
    assert len(requests) == 2 and usage["output_tokens"] == 12
    assert llm.Selection.model_validate_json(result).fact_ids == [fact_row["id"]]
    monkeypatch.setattr(llm, "completion", lambda *args: ('{"fact_ids":["invented"]}', {}))
    selection, meta = llm.select_facts(Options(provider="ollama", model="fake"), "https://bad.example", [fact_row], "")
    assert selection is None and meta["provider"] == "rules"


def test_lease_and_duplicate_queue(db_ready):
    assert lease("owner1")
    assert not lease("owner2")
    assert lease("owner1", renew=True)
    with Session.begin() as db:
        first = queue(db, "manual")
        assert queue(db, "manual").id == first.id
        first.status = "COMPLETED"
    with Session.begin() as db:
        scheduled = queue(db, "scheduled")
        assert scheduled.trigger == "scheduled"
        assert queue(db, "manual").id == scheduled.id
        scheduled.status = "COMPLETED"
    with Session.begin() as db:
        assert queue(db, "scheduled") is None


def test_api_profile_job_and_invalid_submission_settings(db_ready):
    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "ok"}
        assert client.get("/").status_code == 200
        assert client.put("/api/settings", json={"auto_submit": True}).status_code == 422
        uploaded = client.post("/api/profile/upload", files={"file": ("resume.txt", b"Jordan Rao\nSkills\nSQL")})
        assert uploaded.status_code == 200 and uploaded.json()["imported"] == 2
        state = client.get("/api/state").json()
        assert not any(f["verified"] for f in state["profile"]["facts"])
        job = client.post("/api/jobs", json={"role": "Analyst", "description": "Required skills: SQL."}).json()
        assert job["match"]["eligibility"] == "NEEDS_REVIEW"
        invalid = client.post(f"/api/jobs/{job['id']}/prepare", json={"resume_id": "missing"})
        assert invalid.status_code == 422
        assert client.get("/api/export").headers["content-disposition"].endswith('jobforge-export.json"')


def test_local_token_cross_site_rejection_export_and_deletion(db_ready, monkeypatch):
    from jobforge import api as api_module

    monkeypatch.setattr(api_module, "ACCESS_TOKEN", "fixture-authentication")
    with TestClient(app) as client:
        assert client.get("/api/state").status_code == 401
        assert "Sign in to JobForge" in client.get("/").text
        login = client.post("/login", data={"token": "fixture-authentication"}, follow_redirects=False)
        assert login.status_code == 303 and "HttpOnly" in login.headers["set-cookie"]
        assert client.get("/api/state").status_code == 200
        assert client.post("/api/profile/upload", files={"file": ("private.txt", b"Jordan Rao")}).status_code == 200
        assert client.get("/api/export").json()["originals"]
        assert client.delete("/api/data", headers={"Sec-Fetch-Site": "cross-site"}).status_code == 403
        assert client.delete("/api/data", headers={"Origin": "http://testserver:1234"}).status_code == 403
        assert client.delete("/api/data").json() == {"deleted": True}
        state = client.get("/api/state").json()
        assert state["profile"]["facts"] == [] and state["jobs"] == [] and not state["options"]["enabled"]
