from types import SimpleNamespace

import httpx
import pytest

from jobforge.greenhouse import authorized_board, dispatch, endpoint, preflight
from jobforge.schemas import Fact

ALLOWED = "fixture"


@pytest.fixture
def board(monkeypatch):
    monkeypatch.setenv("JOBFORGE_GREENHOUSE_AUTHORIZED", "true")
    monkeypatch.setenv("JOBFORGE_GREENHOUSE_KEY", "synthetic-only")
    monkeypatch.setenv("JOBFORGE_GREENHOUSE_BOARD", ALLOWED)
    return SimpleNamespace(source_key="greenhouse:fixture:9", role="API Engineer", detail={"source": "greenhouse"})


def question(name, kind="input_text", required=True):
    return {"required": required, "fields": [{"name": name, "type": kind}]}


def applicant():
    return SimpleNamespace(facts=[
        Fact(category="personal", label=label, value=value, verified=True).model_dump()
        for label, value in [("First name", "Jordan"), ("Last name", "Rao"), ("Email", "jordan@example.test")]
    ])


def test_requires_explicit_board_credentials(board, monkeypatch):
    assert authorized_board() == ALLOWED
    assert endpoint(board) is not None
    monkeypatch.setenv("JOBFORGE_GREENHOUSE_BOARD", "some_other_company")
    assert endpoint(board) is None
    monkeypatch.setenv("JOBFORGE_GREENHOUSE_AUTHORIZED", "false")
    assert authorized_board() is None


def test_authorized_adapter_validates_required_fields_and_receipt(board):
    def http(request):
        assert request.url.host == "boards-api.greenhouse.io"
        if request.method == "POST":
            assert request.headers["Authorization"].startswith("Basic ")
            assert b"application/pdf" in request.content and b"synthetic PDF" in request.content
            assert b"jordan@example.test" in request.content and b"question_9" not in request.content
            return httpx.Response(200, json={"application_id": "fixture-200"})
        assert request.url.params["questions"] == "true"
        return httpx.Response(200, json={
            "id": 9, "title": "API Engineer", "questions": [
                question("first_name"), question("last_name"), question("email"),
                question("resume", "input_file"), question("question_9", required=False),
            ],
        })

    with httpx.Client(transport=httpx.MockTransport(http)) as client:
        url, values, summary = preflight(client, board, applicant())
        assert not summary["missing"] and "Resume PDF" in summary["filled"]
        assert dispatch(client, url, values, b"synthetic PDF") == "Greenhouse application fixture-200"


def test_authorized_adapter_flags_ambiguous_form_and_acknowledgement(board):
    def http(request):
        if request.method == "POST":
            return httpx.Response(200, json={})
        return httpx.Response(200, json={
            "id": 9, "title": "API Engineer",
            "questions": [question("question_9", "multi_value_single_select")],
            "data_compliance": [{"requires_processing_consent": True}],
        })

    with httpx.Client(transport=httpx.MockTransport(http)) as client:
        url, values, summary = preflight(client, board, applicant())
        assert "Employer-specific required field" in summary["missing"]
        assert "Employer consent or attestation" in summary["missing"]
        assert dispatch(client, url, values, b"synthetic PDF") is None
