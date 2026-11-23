from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter
from pypdf.annotations import Link
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from jobforge import activation, api, applications, employers, matching, profile, submission, worker
from jobforge.models import Application, Base, Log, Profile, Resume, Run, Settings, Upload
from jobforge.schemas import Fact, Options, Posting, Preferences, Source


@pytest.fixture
def sessions(tmp_path, monkeypatch):
    engine = create_engine("sqlite:///" + (tmp_path / "activation.sqlite3").as_posix())
    Base.metadata.create_all(engine)
    session = sessionmaker(engine, expire_on_commit=False)
    for module in (api, applications, submission, worker):
        monkeypatch.setattr(module, "Session", session)
    worker.initialize()
    yield session
    engine.dispose()


def test_upload_replay_and_atomic_verification_preserve_original(sessions):
    original = b"Test Candidate\nLinkedIn: https://www.linkedin.com/in/synthetic-test\nSkills: Python, SQL\n"
    with TestClient(api.app) as client:
        saved = client.post("/api/profile/upload", files={"file": ("original.txt", original)}).json()
        repeat = client.post("/api/profile/upload", files={"file": ("renamed.txt", original)}).json()
        assert repeat == {"imported": 0, "upload": saved["upload"], "already_imported": True}
        assert client.get("/api/profile/uploads/" + saved["upload"]).content == original
        state = client.get("/api/state").json()
        assert any(fact["label"] == "LinkedIn" for fact in state["profile"]["facts"])
        skills = [fact for fact in state["profile"]["facts"] if fact["category"] == "skill"]
        assert len(skills) == 2 and all(not fact["verified"] for fact in skills)
        changed = {**skills[-1], "excerpt": "Changed source"}
        assert client.post("/api/profile/verify", json={"facts": [skills[0], changed]}).status_code == 409
        assert all(not fact["verified"] for fact in client.get("/api/state").json()["profile"]["facts"])
        assert client.post("/api/profile/verify", json={"facts": skills}).json() == {"verified": 2}
        assert client.post("/api/profile/verify", json={"facts": skills}).json() == {"verified": 0}
    with sessions() as db:
        assert db.scalar(select(func.count()).select_from(Upload)) == 1
        saved_facts = db.get(Profile, 1).facts
        assert [fact["excerpt"] for fact in saved_facts if fact["verified"]] == [fact["excerpt"] for fact in skills]


def test_verified_board_selection_is_atomic(sessions, monkeypatch):
    def feed(source):
        return [Posting(source_key=source.provider + ":" + source.board + ":1", source=source.provider,
                        company=source.company, role="Backend Engineer", description="Required skills: Python",
                        url="https://boards.greenhouse.io/datadog/jobs/1" if source.board == "datadog"
                            else "https://boards.greenhouse.io/another-employer/jobs/1")], True

    monkeypatch.setattr(employers, "fetch_board", feed)
    with TestClient(api.app) as client:
        proofs = client.post("/api/employers/verify-selected", json={"keys": ["datadog", "stripe"]}).json()
        assert proofs["datadog"]["jobs"][0]["role"] == "Backend Engineer"
        assert "expected employer" in proofs["stripe"]["error"]
        failed = client.post("/api/employers/enable-selected", json={"keys": ["datadog", "stripe"]})
        assert failed.status_code == 422
        assert not client.get("/api/state").json()["options"]["sources"]
        assert client.post("/api/employers/enable-selected", json={"keys": ["datadog"]}).json() == {"enabled": 1}
        saved = next(row for row in client.get("/api/employers").json() if row["key"] == "datadog")
        assert saved["enabled"] and saved["preview"]["jobs"] == proofs["datadog"]["jobs"]


def fixture_fact(category, label, value):
    return Fact(category=category, label=label, value=value, verified=True).model_dump()


def test_activation_extracts_profile_links_without_project_links():
    pdf = PdfWriter()
    pdf.add_blank_page(width=300, height=300)
    for url in ("https://github.com/synthetic-profile", "https://github.com/synthetic-profile/project",
                "https://www.linkedin.com/in/synthetic-profile"):
        pdf.add_annotation(0, Link(rect=(0, 0, 100, 100), url=url))
    data = BytesIO()
    pdf.write(data)
    facts = profile.parse_file("fixture.pdf", data.getvalue(), activation_review=True)
    links = [fact for fact in facts if fact.category == "personal"]
    assert [fact.label for fact in links] == ["GitHub", "LinkedIn"]
    assert all(not fact.verified and fact.excerpt.startswith("PDF hyperlink on page 1") for fact in links)


def test_personal_activation_rolls_back_then_confirms_selected_evidence(sessions):
    with sessions.begin() as db:
        profile = db.get(Profile, 1)
        profile.facts = [fixture_fact("personal", "Name", "Synthetic Candidate"),
                         fixture_fact("personal", "Email", "sample@example.test")]
        profile.preferences = Preferences(min_salary=123, salary_currency="USD").model_dump()
        for board in ("datadog", "stripe"):
            db.add(Log(kind="board_verified", message="Test verification",
                       detail={"provider": "greenhouse", "board": board}))

    with TestClient(api.app) as client:
        for name, cgpa in (("first.txt", "8.2"), ("second.txt", "8.3")):
            original = f"Skills: Python, SQL\nEducation:\nCGPA: {cgpa}\n".encode()
            assert client.post("/api/profile/upload", files={"file": (name, original)}).status_code == 200
        evidence = client.get("/api/activation/review").json()
        assert len(evidence["originals"]) == 2
        groups = evidence["groups"]
        python = next(group for group in groups if group["value"] == "Python")
        assert {item["original"]["name"] for item in python["evidence"]} == {"first.txt", "second.txt"}
        conflicts = [group["id"] for group in groups if group["conflict"] == "cgpa"]
        assert len(conflicts) == 2
        payload = {"revision": evidence["revision"], "fact_ids": [python["id"]], "board_keys": ["datadog"],
                   "maximum_mandatory_years": 2, "preferences": {"roles": ["Backend Engineer"],
                   "locations": ["Bengaluru"], "work_modes": ["remote"], "employment": []}}
        assert client.post("/api/activation/confirm", json={**payload, "revision": "0" * 64}).status_code == 409
        assert client.post("/api/activation/confirm", json={**payload, "fact_ids": conflicts}).status_code == 422
        assert client.post("/api/activation/confirm", json={**payload, "board_keys": ["datadog", "unknown"]}).status_code == 422
        state = client.get("/api/state").json()
        assert not state["options"]["sources"] and not state["profile"]["preferences"]["roles"]
        assert not state["profile_readiness"]["ready"] and state["worker"]["pending"] == 0
        result = client.post("/api/activation/confirm", json=payload)
        assert result.status_code == 202, result.text
        assert client.post("/api/activation/confirm", json=payload).status_code == 409
        state = client.get("/api/state").json()
        assert state["profile_readiness"]["ready"] and state["worker"]["pending"] == 1
        assert [source["board"] for source in state["options"]["sources"]] == ["datadog"]
        preferences = Preferences.model_validate(state["profile"]["preferences"])
        assert preferences.salary_currency == "USD" and preferences.min_salary == 123
        assert preferences.maximum_mandatory_years == 2 and preferences.activation_confirmed
        for location, mode, fits in (("Bengaluru", "onsite", True), ("Remote", "remote", True),
                                     ("Paris", "onsite", False)):
            posting = Posting(source_key="greenhouse:datadog:1", source="greenhouse", company="Datadog",
                              role="Backend Engineer", location=location, work_mode=mode, description="Write Python.")
            assert matching.shortlist(posting, preferences) == fits
            assert matching.analyze(posting, state["profile"]["facts"], preferences, 0)["eligibility"] == "NEEDS_REVIEW"
    with sessions() as db:
        assert db.get(Run, result.json()["id"]).report["activation_boards"] == [["greenhouse", "datadog"]]
        assert [fact["value"] for fact in db.get(Profile, 1).facts if fact["verified"]] == [
            "Synthetic Candidate", "sample@example.test", "Python"]


def test_first_activation_is_gated_and_prepares_at_most_five(sessions, monkeypatch):
    called = []
    def feed(source):
        called.append(source.provider)
        return [Posting(source_key=f"greenhouse:datadog:{i}", source="greenhouse", company="Datadog",
                        role=f"Backend Engineer {i}", location="Remote",
                        description="Required skills: Python, SQL, FastAPI",
                        url=f"https://boards.greenhouse.io/{'different-board' if i == 0 else 'datadog'}/jobs/{i}")
                for i in range(7)], True

    monkeypatch.setattr(worker, "fetch_board", feed)
    with TestClient(api.app) as client:
        assert client.post("/api/activation/run").status_code == 422
        with sessions.begin() as db:
            settings = db.get(Settings, 1)
            next_run = settings.next_run
            settings.options = Options(provider="rules", max_applications_per_day=10, sources=[
                Source(provider="mock", board="demo", company="Synthetic fixture"),
            ]).model_dump(mode="json")
            profile = db.get(Profile, 1)
            profile.preferences = Preferences(salary_currency="USD").model_dump()
            profile.facts = [
                fixture_fact("personal", "Name", "Synthetic Candidate"),
                fixture_fact("personal", "Email", "sample@example.test"),
                *[fixture_fact("skill", skill, skill) for skill in ("Python", "SQL", "FastAPI")],
                fixture_fact("project", "API", "Built a Python FastAPI student project."),
                fixture_fact("project", "Database", "Built a SQL reporting project."),
                fixture_fact("experience", "Experience", "Maintained a Python API."),
                fixture_fact("education", "Degree", "Completed Python coursework."),
            ]
            db.add(Log(kind="board_verified", message="Test verification", detail={"provider": "greenhouse", "board": "datadog"}))
        preferences = {"roles": ["Backend Engineer"], "locations": [], "work_modes": ["remote"], "employment": []}
        review = client.get("/api/activation/review").json()
        response = client.post("/api/activation/confirm", json={"revision": review["revision"],
                               "preferences": preferences, "board_keys": ["datadog"]})
        assert response.status_code == 202, response.text
        setup = client.get("/api/activation").json()
        assert setup["ready"] and setup["verified_enabled_boards"] == 1
        run_id = response.json()["id"]
        assert client.post("/api/activation/run").status_code == 409
        worker.step()
        result = client.get("/api/activation").json()["latest_run"]
        assert result["status"] == "COMPLETED"
        assert result["selected"] == result["compiled"] == result["prepared"] == 5
        assert result["discovered"] == 6
        assert called == ["greenhouse"]
    with sessions.begin() as db:
        assert db.get(Settings, 1).next_run == next_run
        assert db.get(Profile, 1).preferences["salary_currency"] == "USD"
        row = db.get(Run, run_id)
        assert not activation.reserve(db, run_id, "unreserved")
        assert activation.reserve(db, run_id, row.report["activation_jobs"][0])
        assert db.scalar(select(func.count()).select_from(Resume)) == 5
        applications_saved = db.scalars(select(Application)).all()
        assert all(app.status == "APPLICATION_PREPARED" and not app.confirmation for app in applications_saved)
        assert all(app.prepared_payload["provider"] == "manual" for app in applications_saved)
