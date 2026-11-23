import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest
from playwright.sync_api import expect, sync_playwright

from test_dashboard_e2e import wait_for_health


@pytest.mark.e2e
def test_workspace_routes_resume_and_authenticated_approval(tmp_path):
    if not Path("frontend/dist/index.html").is_file():
        pytest.skip("Build the frontend before running the React workspace browser test.")
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    origin = f"http://127.0.0.1:{port}"
    token = "workspace-test-token"
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{(tmp_path / 'workspace.sqlite3').as_posix()}",
           "JOBFORGE_MOCK_ORIGIN": origin, "JOBFORGE_DATA": str(tmp_path), "LLM_PROVIDER": "rules",
           "JOBFORGE_ACCESS_TOKEN": token}
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], env=env, check=True)
    with (tmp_path / "workspace-server.log").open("w") as server_log:
        server = subprocess.Popen([sys.executable, "-m", "uvicorn", "jobforge.api:app", "--port", str(port)],
                                  env=env, stdout=server_log, stderr=subprocess.STDOUT)
        worker = None
        try:
            wait_for_health(origin)
            with sync_playwright() as pw:
                exe = os.getenv("JOBFORGE_BROWSER_EXECUTABLE")
                browser = pw.chromium.launch(**({"executable_path": exe} if exe else {}))
                page = browser.new_page(viewport={"width": 1440, "height": 960})
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.on("console", lambda item: errors.append(item.text) if item.type == "error" else None)

                assert page.request.get(origin + "/api/state").status == 401
                login = page.goto(origin + "/history")
                assert "script-src 'self'" in login.headers["content-security-policy"]
                page.locator('input[name="token"]').fill(token)
                page.locator('button[type="submit"]').click()
                expect(page.get_by_role("heading", name="Overview")).to_be_visible()
                expect(page.get_by_text("Backend connected")).to_be_visible()
                assert page.request.get(origin + "/api/missing").status == 404
                assert page.request.get(origin + "/ui-assets/missing.js").status == 404
                assert page.request.post(origin + "/api/runs", headers={"Origin": "https://invalid.example"}).status == 403

                for route, heading in {
                    "/jobs": "Job discovery", "/pipeline": "Application pipeline",
                    "/resume-studio": "AI Resume Studio", "/approvals": "Approval queue",
                    "/exceptions": "Exception queue", "/automation": "Automation center",
                    "/history": "Application history", "/analytics": "Analytics", "/settings": "Settings",
                    "/profile": "Candidate profile", "/notifications": "Notifications",
                }.items():
                    page.goto(origin + route)
                    expect(page.get_by_role("heading", name=heading, exact=True)).to_be_visible()
                page.keyboard.press("Control+k")
                search = page.get_by_role("searchbox", name="Search pages, jobs, and applications")
                search.fill("Overview")
                search.press("Enter")
                expect(page.get_by_role("heading", name="Overview")).to_be_visible()
                page.get_by_role("button", name="Switch to light mode").click()
                expect(page.locator("html")).to_have_attribute("data-theme", "light")
                page.reload()
                expect(page.locator("html")).to_have_attribute("data-theme", "light")
                page.get_by_role("button", name="Switch to dark mode").click()

                response = page.request.post(origin + "/api/demo")
                assert response.ok, response.text()
                page.goto(origin + "/jobs")
                page.get_by_role("button", name="Add posting").click()
                page.get_by_label("Company", exact=True).last.fill("Example Studio")
                page.get_by_label("Role", exact=True).last.fill("API Developer")
                page.get_by_label("Job description").fill("Required skills: Python, FastAPI.")
                page.get_by_role("button", name="Save posting").click()
                drawer = page.get_by_role("dialog", name="Job details")
                expect(drawer.get_by_text("API Developer", exact=True)).to_be_visible()
                drawer.get_by_role("button", name="Shortlist").click()
                expect(drawer.get_by_text("Shortlisted", exact=True)).to_be_visible()
                drawer.get_by_role("link", name="Prepare resume").click()

                original = b"Sample Candidate\nSkills: Python, SQL\nBuilt a FastAPI service."
                page.get_by_label("Original resume").set_input_files({"name": "original.txt", "mimeType": "text/plain", "buffer": original})
                page.get_by_role("button", name="Import resume").click()
                expect(page.get_by_text("draft facts imported", exact=False)).to_be_visible()
                page.get_by_label("Template").select_option("compact")
                page.get_by_role("button", name="Generate resume").click()
                preview = page.locator('iframe[title="Tailored resume PDF"]')
                expect(preview).to_be_visible(timeout=45000)
                assert page.request.get(origin + preview.get_attribute("src")).body().startswith(b"%PDF-")
                with page.expect_download() as download:
                    page.get_by_role("link", name="Download PDF", exact=True).click()
                assert download.value.suggested_filename == "resume.pdf"
                page.get_by_role("button", name="Compare original").click()
                original_url = page.get_by_role("link", name="Download original").get_attribute("href")
                assert page.request.get(origin + original_url).body() == original
                page.get_by_role("button", name="Prepare selected version").click()
                expect(page.get_by_role("link", name="Open application review")).to_be_visible(timeout=20000)
                page.get_by_role("link", name="Open application review").click()
                expect(page.get_by_role("heading", name="Prepared application")).to_be_visible()
                expect(page.get_by_role("button", name="Approve & submit")).to_have_count(0)

                worker = subprocess.Popen([sys.executable, "-m", "jobforge.worker"], env=env,
                                          stdout=server_log, stderr=subprocess.STDOUT)
                deadline = time.monotonic() + 60
                mock = None
                while mock is None and time.monotonic() < deadline:
                    snapshot = page.request.get(origin + "/api/state").json()
                    mock = next((item for item in snapshot["applications"]
                                 if item["status"] == "APPLICATION_PREPARED" and item["summary"].get("browser")), None)
                    if mock is None:
                        time.sleep(0.4)
                assert mock is not None, snapshot["runs"]
                page.goto(origin + "/approvals?app=" + mock["id"])
                approval = page.get_by_role("dialog", name="Application details")
                approval.get_by_role("button", name="Approve & submit").click()
                confirm = page.get_by_role("dialog", name="Confirm final approval")
                digest = page.request.get(origin + "/api/applications/" + mock["id"] + "/review").json()["payload_hash"]
                expect(confirm.get_by_text(digest, exact=True)).to_be_visible()
                with page.expect_response(lambda item: item.url.endswith("/approve-submit")) as accepted:
                    confirm.get_by_role("button", name="Confirm approval and queue submission").click()
                assert accepted.value.status == 202, accepted.value.text()
                assert accepted.value.request.post_data_json == {"application_id": mock["id"], "payload_hash": digest}
                expect(approval.get_by_text("Final approval recorded", exact=False)).to_be_visible()
                expect(approval.get_by_text("Simulation receipt", exact=True)).to_be_visible(timeout=45000)
                approval.get_by_role("button", name="Close").click()
                page.goto(origin + "/notifications")
                button = page.get_by_role("button", name="Mark all as read")
                expect(button).to_be_enabled()
                button.click()
                expect(button).to_be_disabled()
                page.goto(origin + "/settings")
                page.get_by_label("Interval minutes", exact=True).fill("120")
                page.get_by_role("button", name="Save settings").click()
                expect(page.get_by_text("Settings saved.", exact=True)).to_be_visible()
                assert page.request.get(origin + "/api/state").json()["options"]["interval_minutes"] == 120

                page.goto(origin + "/jobs")
                page.get_by_label("Search jobs", exact=True).fill("no matching job")
                expect(page.get_by_text("No jobs match the selected filters.")).to_be_visible()
                page.goto(origin)
                expect(page.get_by_role("heading", name="Overview")).to_be_visible()
                page.screenshot(path=str(tmp_path / "workspace-desktop.png"), full_page=True)
                page.set_viewport_size({"width": 390, "height": 844})
                page.get_by_role("button", name="Open navigation").click()
                page.get_by_role("navigation", name="Main navigation").get_by_role("link", name="Pipeline").click()
                expect(page.get_by_role("heading", name="Application pipeline")).to_be_visible()
                page.get_by_role("button", name="Table").click()
                expect(page.get_by_role("table")).to_be_visible()
                assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
                page.screenshot(path=str(tmp_path / "workspace-mobile.png"), full_page=True)
                assert not errors, errors
                browser.close()
        finally:
            if worker is not None:
                worker.terminate()
                worker.wait(timeout=15)
            server.terminate()
            server.wait(timeout=15)
