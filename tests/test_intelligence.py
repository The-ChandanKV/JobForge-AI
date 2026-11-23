import json
from contextlib import contextmanager
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient

from jobforge import api, employers, llm, providers
from jobforge.intelligence import application_readiness
from jobforge.matching import analyze
from jobforge.schemas import Fact, Posting, Preferences, Source


def test_public_feed_retry_respects_server_wait_and_excludes_redirects(monkeypatch):
    endpoint = providers.API["lever"].format(board="fixture")
    calls = []
    waits = []
    responses = iter([(429, "2"), (200, ""), (429, "120")])

    @contextmanager
    def stream(method, url, **kwargs):
        assert (method, url) == ("GET", endpoint) and kwargs["follow_redirects"] is False
        calls.append(url)
        status, retry = next(responses)
        yield httpx.Response(status, request=httpx.Request(method, url),
                             headers={"Retry-After": retry}, content=b"[]")

    monkeypatch.setattr(providers.httpx, "stream", stream)
    monkeypatch.setattr(providers, "sleep", waits.append)
    monkeypatch.setattr(providers, "_next_request", {})
    assert providers.read_feed("lever", endpoint) == b"[]"
    with pytest.raises(httpx.HTTPStatusError):
        providers.read_feed("lever", endpoint)
    assert len(calls) == 3 and 2 in waits and 120 not in waits


def test_public_providers_normalize_confirmed_details_and_xml(monkeypatch):
    root = providers.API["smartrecruiters"].format(board="KnownEmployer")
    detail = {"id": "123", "name": "Backend Engineer", "active": True, "visibility": "PUBLIC",
              "company": {"identifier": "KnownEmployer"}, "location": {"city": "Dublin", "country": "ie", "hybrid": True},
              "jobAd": {"sections": {"qualifications": {"text": "<p>Required skills: Python</p>"}}},
              "postingUrl": "https://jobs.smartrecruiters.com/KnownEmployer/123"}
    calls = []
    def get(provider, url, params=None):
        calls.append((provider, url))
        if url == root:
            assert params == {"limit": 12, "offset": 0, "q": "software"}
            return json.dumps({"totalFound": 20, "content": [{"id": "123", "ref": "https://invalid.test"}]}).encode()
        if url == root + "/123":
            return json.dumps(detail).encode()
        return (b"<offers><offer><id>5</id><slug>backend</slug><title>Backend</title>"
                b"<remote>true</remote><description>Build systems.</description>"
                b"<requirements>Python</requirements></offer></offers>")
    monkeypatch.setattr(providers, "read_feed", get)
    smart, complete = providers.fetch_board(Source(provider="smartrecruiters", board="KnownEmployer", company="Example"))
    assert not complete and len(smart) == 1 and smart[0].work_mode == "hybrid"
    assert calls[-1][1] == root + "/123"
    rows, complete = providers.fetch_board(Source(provider="recruitee", board="known", company="Known"))
    assert complete and str(rows[0].url) == "https://known.recruitee.com/o/backend"
    assert rows[0].posted is None and "Python" in rows[0].description


def test_employer_verification_precedes_enable_and_feedback_persists(db_ready, monkeypatch):
    monkeypatch.setattr(employers, "fetch_board", lambda source: ([Posting(source_key="recruitee:thecodest:5",
        source="recruitee", company=source.company, role="Backend", description="Build systems.",
        url="https://thecodest.recruitee.com/o/backend")], True))
    with TestClient(api.app) as http:
        monitor = "/api/employers/the-codest/monitor"
        assert http.put(monitor, json={"enabled": True, "group": "priority"}).status_code == 422
        assert http.post("/api/employers/the-codest/verify").json()["jobs"][0]["role"] == "Backend"
        assert http.put(monitor, json={"enabled": True, "group": "priority"}).status_code == 200
        options = http.get("/api/state").json()["options"]
        assert any(row["provider"] == "recruitee" and row["enabled"] for row in options["sources"])
        assert http.put(monitor, json={"enabled": False, "group": "regular"}).status_code == 200

        job = http.post("/api/jobs", json={"company": "Synthetic Phase Six", "role": "Backend",
                                         "description": "Required skills: Python"}).json()
        job_path = "/api/jobs/" + job["id"]
        assert http.post(job_path + "/feedback", json={"value": "already_applied"}).status_code == 200
        intel = http.get(job_path + "/intelligence").json()
        assert intel["job"]["status"] == "SKIPPED" and intel["feedback"] == "already_applied"
        assert intel["readiness"]["category"] == "ALREADY_APPLIED"


def test_alternative_requirements_and_semantic_output_remain_independent(monkeypatch):
    job = Posting(source_key="manual:1", source="manual", role="Developer", company="Example",
                  description="Required skills:\nAt least one of Python or Java")
    fact = Fact(category="skill", label="Python", value="Python", verified=True).model_dump()
    result = analyze(job, [fact], Preferences(), 80)
    assert result["eligibility"] == "ELIGIBLE" and result["alternative_skill_groups"] == [["Python", "Java"]]
    assert analyze(job, [], Preferences(), 80)["eligibility"] == "NEEDS_REVIEW"
    monkeypatch.setattr(llm, "completion", lambda client, provider, *args: ('{"relevance":8}', {}))
    assert llm.semantic_relevance("local", job.role, job.description, [fact]) == 8
    monkeypatch.setattr(llm, "completion", lambda *args: ('{"relevance":8,"eligibility":"ELIGIBLE"}', {}))
    assert llm.semantic_relevance("local", job.role, job.description, [fact]) is None


def test_readiness_distinguishes_manual_handoff_from_verified_form():
    facts = [Fact(category=category, label=label, value=value, verified=True).model_dump()
             for category, label, value in (("personal", "Name", "Synthetic Candidate"),
                                            ("personal", "Email", "sample@example.test"),
                                            ("skill", "Skill", "Python"))]
    profile = SimpleNamespace(facts=facts)
    job = SimpleNamespace(available=True, match={"eligibility": "ELIGIBLE"},
                          detail={"url": "https://example.test/jobs/1"})
    resume = SimpleNamespace(pdf=b"%PDF-fixture", report={"claims": [facts[-1]]})
    app = SimpleNamespace(prepared_payload={"provider": "manual"}, summary={}, status="APPLICATION_PREPARED", confirmation=None)
    summary = application_readiness(job, profile, resume, app)
    assert summary["category"] == "MANUAL_HANDOFF" and summary["checks"]["Screening completeness"] is None
    app.prepared_payload = {"provider": "greenhouse", "form_digest": "fixture", "pending": ["Consent required"]}
    assert application_readiness(job, profile, resume, app, can_dispatch=True)["category"] == "NEEDS_INFORMATION"
