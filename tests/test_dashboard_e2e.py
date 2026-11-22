import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest
from playwright.sync_api import expect, sync_playwright


def wait_for_health(base):
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        try:
            if httpx.get(base + "/health", timeout=1).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.4)
    raise AssertionError("Uvicorn did not start")


@pytest.mark.e2e
def test_dashboard_manual_studio_and_scheduled_mock_application(tmp_path):
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    origin = f"http://127.0.0.1:{port}"
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{(tmp_path / 'e2e.sqlite3').as_posix()}",
           "JOBFORGE_MOCK_ORIGIN": origin, "JOBFORGE_DATA": str(tmp_path), "LLM_PROVIDER": "rules"}
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], env=env, check=True)
    with (tmp_path / "server.log").open("w") as server_log, (tmp_path / "worker.log").open("w") as worker_log:
        server = subprocess.Popen([sys.executable, "-m", "uvicorn", "jobforge.api:app", "--port", str(port)],
                                  env=env, stdout=server_log, stderr=subprocess.STDOUT)
        worker = None
        try:
            wait_for_health(origin)
            with sync_playwright() as pw:
                exe = os.getenv("JOBFORGE_BROWSER_EXECUTABLE")
                browser = pw.chromium.launch(**({"executable_path": exe} if exe else {}))
                page = browser.new_page()
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(origin)
                expect(page.get_by_role("heading", name="Overview")).to_be_visible()
                page.get_by_role("link", name="Settings").click()
                page.get_by_role("button", name="Load synthetic test profile").click()
                expect(page.get_by_role("status")).to_contain_text("Synthetic profile loaded")
                with httpx.Client(base_url=origin, timeout=25) as client:
                    seeded = client.get("/api/state").json()
                    profile = seeded["profile"]
                    manual = next(run["id"] for run in seeded["runs"] if run["trigger"] == "manual")
                    assert client.post(f"/api/runs/{manual}/cancel").status_code == 200
                    without_answer = [fact for fact in profile["facts"] if fact["label"] != "Mock screening answer"]
                    assert client.put("/api/profile", json={**profile, "facts": without_answer}).status_code == 200
                worker = subprocess.Popen([sys.executable, "-m", "jobforge.worker"], env=env,
                                          stdout=worker_log, stderr=subprocess.STDOUT)
                with httpx.Client(base_url=origin, timeout=50) as client:
                    deadline = time.monotonic() + 65
                    while True:
                        state = client.get("/api/state").json()
                        if state["applications"]:
                            break
                        assert time.monotonic() < deadline, state["runs"]
                        time.sleep(0.6)
                    app = state["applications"][0]
                    while app["status"] == "NEEDS_REVIEW" and not app["summary"].get("missing"):
                        assert time.monotonic() < deadline
                        time.sleep(0.6)
                        app = client.get("/api/state").json()["applications"][0]
                    assert app["status"] == "NEEDS_REVIEW", app
                    assert "Resume PDF" in app["summary"]["filled"]
                    assert "Mock screening answer" in app["summary"]["missing"]
                    assert client.post(f"/api/applications/{app['id']}/decision", json={"action": "approve"}).status_code == 422
                    assert client.put("/api/profile", json=profile).status_code == 200
                    prepared = client.post(f"/api/jobs/{app['job_id']}/prepare", json={"resume_id": app["resume_id"]})
                    assert prepared.json()["status"] == "APPLICATION_PREPARED", prepared.text
                    assert client.post(f"/api/applications/{app['id']}/decision", json={"action": "simulate"}).status_code == 422

                page.get_by_role("button", name="Refresh").click()
                page.get_by_role("link", name="Approval Queue").click()
                expect(page.get_by_role("button", name="Approve", exact=True)).to_be_visible()
                page.get_by_role("button", name="Approve", exact=True).click()
                expect(page.get_by_text("No applications yet")).to_be_visible()
                page.get_by_role("link", name="Applications", exact=False).click()
                page.get_by_role("button", name="Submit simulation").click()
                expect(page.get_by_text("Mock confirmation")).to_be_visible(timeout=30_000)
                expect(page.get_by_text("MOCK-", exact=False)).to_be_visible()
                page.get_by_role("button", name="Show timeline").click()
                expect(page.get_by_text("Verified receipt from the local mock employer.")).to_be_visible()
                with httpx.Client(base_url=origin, timeout=25) as client:
                    replay = client.post(f"/api/applications/{app['id']}/decision", json={"action": "simulate"})
                    assert replay.status_code == 200 and replay.json()["confirmation"].startswith("MOCK-")
                    deadline = time.monotonic() + 18
                    while True:
                        state = client.get("/api/state").json()
                        if any(run["trigger"] == "scheduled" and run["status"] == "COMPLETED"
                               and run["report"].get("compiled") == 1 and run["report"].get("prepared") == 1
                               for run in state["runs"]):
                            break
                        assert time.monotonic() < deadline, state["runs"]
                        time.sleep(0.5)
                    assert len(state["applications"]) == 1

                page.get_by_role("link", name="Resume Studio").click()
                page.get_by_label("Company").fill("Manual example")
                page.get_by_label("Role", exact=True).fill("API Developer")
                page.get_by_label("Job description").fill("Required skills: Python, FastAPI.")
                page.get_by_role("button", name="Analyze posting").click()
                expect(page.get_by_role("button", name="Generate PDF")).to_be_visible()
                page.get_by_role("button", name="Generate PDF").click()
                expect(page.locator("iframe[title='Resume PDF preview']")).to_be_visible(timeout=30_000)
                pdf_url = page.locator("iframe[title='Resume PDF preview']").get_attribute("src")
                assert page.request.get(origin + pdf_url).body().startswith(b"%PDF-")
                expect(page.get_by_role("link", name="Download .tex")).to_be_visible()
                page.get_by_label("LaTeX source").fill(page.get_by_label("LaTeX source").input_value().replace("0.75in", "0.85in"))
                page.get_by_role("button", name="Compile", exact=True).click()
                expect(page.locator("iframe[title='Resume PDF preview']")).not_to_have_attribute("src", pdf_url, timeout=30_000)
                page.get_by_role("link", name="Overview").click()
                expect(page.get_by_text("1 confirmed simulation", exact=True)).to_be_visible()
                page.screenshot(path=str(tmp_path / "dashboard.png"), full_page=True)
                with httpx.Client(base_url=origin, timeout=30) as client:
                    state = client.get("/api/state").json()
                    assert state["worker"]["last_heartbeat"] and state["daily"]["compiled"] >= 1
                    variants = ["fixture-textarea", "fixture-challenge", "fixture-consent", "fixture-receipt-only"]
                    sources = state["options"]["sources"] + [
                        {"provider": "mock", "board": board, "company": board} for board in variants
                    ]
                    assert client.put("/api/settings", json={**state["options"], "sources": sources}).status_code == 200
                    assert client.post("/api/runs").status_code == 200
                    deadline = time.monotonic() + 60
                    while True:
                        state = client.get("/api/state").json()
                        companies = {job["id"]: job["company"] for job in state["jobs"]}
                        found = {companies[row["job_id"]]: row for row in state["applications"]
                                 if row["summary"].get("checkpoint") == "FORM_PREPARED"}
                        if all(board in found for board in variants):
                            break
                        assert time.monotonic() < deadline, state["runs"]
                        time.sleep(0.5)
                    assert found["fixture-textarea"]["status"] == "APPLICATION_PREPARED"
                    assert "Mock screening answer" in found["fixture-textarea"]["summary"]["filled"]
                    assert found["fixture-challenge"]["status"] == "NEEDS_REVIEW"
                    assert found["fixture-consent"]["status"] == "NEEDS_REVIEW"
                    assert client.post(f"/api/applications/{found['fixture-consent']['id']}/decision",
                                       json={"action": "approve"}).status_code == 422
                    recovered = found["fixture-receipt-only"]["id"]
                    url = f"/api/applications/{recovered}/decision"
                    assert client.post(url, json={"action": "approve"}).status_code == 200
                    assert client.post(url, json={"action": "simulate"}).json()["status"] == "SUBMITTED"
                page.get_by_role("button", name="Refresh").click()
                page.get_by_role("link", name="Exception Queue").click()
                expect(page.get_by_text("Employer verification challenge requires manual action.", exact=False)).to_be_visible()
                page.get_by_role("link", name="Approval Queue").click()
                one_click_card = page.get_by_role("heading", name="Graduate Backend Engineer · fixture-textarea").locator("..").locator("..")
                one_click_card.get_by_role("button", name="Review application").click()
                expect(one_click_card.get_by_role("heading", name="Application preview")).to_be_visible()
                expect(one_click_card.get_by_title("Application resume PDF preview")).to_be_visible()
                expect(one_click_card.get_by_text("Mock screening answer", exact=True)).to_be_visible()
                exact = found["fixture-textarea"]["id"]
                review_path = f"/api/applications/{exact}/review"
                payload = page.request.get(origin + review_path).json()
                one_click_card.get_by_role("button", name="Approve & Submit", exact=True).click()
                expect(page.get_by_role("heading", name="Applications", exact=True)).to_be_visible()
                expect(page.get_by_text("Mock confirmation", exact=True).last).to_be_visible(timeout=30_000)
                deadline = time.monotonic() + 25
                while True:
                    final = page.request.get(origin + review_path).json()
                    if final["task"] and final["task"]["status"] == "SUBMITTED":
                        break
                    assert time.monotonic() < deadline, final
                    time.sleep(0.6)
                assert final["application"]["confirmation"].startswith("MOCK-")
                duplicate = page.request.post(origin + f"/api/applications/{exact}/approve-submit",
                                              data={"application_id": exact, "payload_hash": payload["payload_hash"]})
                assert duplicate.status == 202 and duplicate.json()["id"] == final["task"]["id"]
                page.get_by_role("link", name="Notifications").click()
                expect(page.get_by_text("Provider confirmation recorded.", exact=True)).to_be_visible()
                assert not errors, errors
                browser.close()
        finally:
            for process in [worker, server]:
                if process is not None:
                    process.terminate()
                    try:
                        process.wait(timeout=8)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
