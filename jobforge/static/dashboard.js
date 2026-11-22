const content = document.querySelector("#content");
const title = document.querySelector("#crumb");
let state;
let selectedJob = "";
let jobDescription = "";
let studioJob = "";
let versions = [];
let currentVersion;
let messageTimer;
let busy = false;
const reviews = new Map();
const selection = new Set();
let reviewFilter = "ready";
let reviewSort = "score";
let notices = [];

const pages = {
  overview: "Overview", jobs: "Job Discovery", studio: "Resume Studio",
  applications: "Applications", approvals: "Approval Queue", exceptions: "Exception Queue", notifications: "Notifications",
  automation: "Automation", profile: "Profile", settings: "Settings",
};

const escape = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
})[char]);
const status = (value) => String(value ?? "unknown").replaceAll("_", " ").toLowerCase()
  .replace(/^\w/, (char) => char.toUpperCase());
const badge = (value) => {
  const color = ["ELIGIBLE", "COMPLETED", "SUBMITTED", "APPROVED", "INTERVIEW", "OFFER"].includes(value) ? "good"
    : ["FAILED", "INELIGIBLE", "REJECTED"].includes(value) ? "bad"
      : ["NEEDS_REVIEW", "SUBMISSION_UNCERTAIN", "APPLICATION_PREPARED", "QUEUED"].includes(value) ? "warn" : "";
  return `<span class="badge ${color}">${escape(status(value))}</span>`;
};
const button = (label, action, id = "", css = "") =>
  `<button type="button" class="${css}" data-action="${action}" data-id="${escape(id)}">${escape(label)}</button>`;
const link = (label, url, css = "button") => {
  if (!url) return "";
  try {
    const parsed = new URL(url, window.location.origin);
    if (parsed.protocol !== "https:" && parsed.origin !== window.location.origin) return "";
    return `<a class="${css}" href="${escape(parsed.href)}" rel="noopener noreferrer" target="_blank">${escape(label)}</a>`;
  } catch {
    return "";
  }
};
const nowPage = () => Object.hasOwn(pages, location.hash.slice(1)) ? location.hash.slice(1) : "overview";
const selected = (left, right) => left === right ? "selected" : "";
const checked = (value) => value ? "checked" : "";
const formData = (form) => Object.fromEntries(new FormData(form));
const showDate = (value) => value ? new Intl.DateTimeFormat(undefined, {
  dateStyle: "medium", timeStyle: "short", timeZone: state.options.timezone,
}).format(new Date(value)) : "—";

function notify(value, error = false) {
  const output = document.querySelector("#message");
  output.hidden = false;
  output.textContent = value;
  output.classList.toggle("error", error);
  clearTimeout(messageTimer);
  messageTimer = setTimeout(() => { output.hidden = true; }, error ? 12000 : 4500);
}

async function api(path, method = "GET", body) {
  const options = { method };
  if (body instanceof FormData) {
    options.body = body;
  } else if (body !== undefined) {
    options.headers = { "Content-Type": "application/json" };
    options.body = JSON.stringify(body);
  }
  const response = await fetch(`/api${path}`, options);
  if (response.status === 401) {
    window.location.assign("/");
    throw new Error("Sign in to continue.");
  }
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || "The request failed.");
  return data;
}

async function refresh(renderPage = true) {
  state = await api("/state");
  if (renderPage) render();
}

function heading(name, subtitle, actions = "") {
  return `<div class="heading"><div><h1>${escape(name)}</h1><p>${escape(subtitle)}</p></div><div class="actions">${actions}</div></div>`;
}

function panel(name, body, actions = "") {
  return `<section class="panel"><div class="section-head"><h2>${escape(name)}</h2>${actions}</div>${body}</section>`;
}

function list(items) {
  return items.length ? `<ul class="list">${items.map((item) => `<li>${item}</li>`).join("")}</ul>`
    : `<p class="muted">No records yet.</p>`;
}

function render() {
  const page = nowPage();
  title.textContent = pages[page];
  document.querySelectorAll("[data-page]").forEach((item) => {
    if (item.dataset.page === page) item.setAttribute("aria-current", "page");
    else item.removeAttribute("aria-current");
  });
  const count = state.applications.filter(needsApproval).length;
  document.querySelector("#queue-count").textContent = count || "";
  document.querySelector("#notification-count").textContent = state.unread_notifications || "";
  content.innerHTML = ({
    overview, jobs, studio, applications: () => applications("all"), approvals: () => applications("approval"),
    exceptions: () => applications("exceptions"),
    automation, profile, settings, notifications,
  })[page]();
}

function overview() {
  const prepared = state.applications.filter((app) => app.summary.checkpoint === "FORM_PREPARED"
    || ["APPLICATION_PREPARED", "APPROVED", "SUBMITTED"].includes(app.status)).length;
  const matching = state.jobs.filter((job) => job.available && job.match.recommendation === "PREPARE_APPLICATION").length;
  const confirmed = state.applications.filter((app) => app.confirmation && !app.summary.simulation).length;
  const simulations = state.applications.filter((app) => app.confirmation && app.summary.simulation).length;
  const last = state.runs.find((r) => r.finished);
  const metrics = [
    ["Jobs discovered today", state.daily.new_jobs], ["Eligible jobs", state.jobs.filter((job) => job.available && job.match.eligibility === "ELIGIBLE").length],
    ["High-match jobs", matching], ["Resumes generated", state.resume_count], ["Applications prepared", prepared],
    ["Awaiting approval", state.applications.filter(needsApproval).length],
    ["Approved applications", state.applications.filter((app) => app.status === "APPROVED").length],
    ["Applications requiring manual action", state.applications.filter(hasException).length],
    ["Employer submissions", confirmed, `${simulations} confirmed simulation${simulations === 1 ? "" : "s"}`],
    ["Failed applications", state.applications.filter((row) => row.status === "FAILED").length],
  ];
  const activity = list(state.logs.slice(0, 6).map((log) =>
    `<strong>${escape(log.message)}</strong><br><span class="muted small">${escape(showDate(log.created))}</span>`));
  return heading("Overview", "Track your job search, resume drafts, and applications in one place.") +
    `<section class="hero"><div><h2>Hourly automation ${state.options.enabled ? "enabled" : "paused"}</h2>
      <p>${state.next_run ? `Next run ${escape(showDate(state.next_run))}` : "Run manually whenever you’re ready."}</p></div>
      ${button("Run now", "run", "", "primary")}</section>
      <div class="card-grid">${metrics.map(([label, value, detail]) =>
        `<article class="metric"><span>${escape(label)}</span><strong>${value}</strong>${detail ? `<span>${escape(detail)}</span>` : ""}</article>`).join("")}</div>
      <div class="split">${panel("Recent activity", activity, '<a href="#automation">Run history →</a>')}
      ${panel("Workspace status", list([
        `<strong>Scheduler</strong><br>${badge(state.worker.status)} <span class="muted">${last ? `${escape(status(last.status))} · ${escape(showDate(last.finished))}` : "No completed runs yet"}</span>`,
        `<strong>Resume provider</strong><br><span class="muted">${escape(state.provider)} ${escape(state.model)}</span>`,
        `<strong>Profile</strong><br><a href="#profile">${state.profile.facts.filter((f) => f.verified).length} verified facts</a>`,
        `<strong>Submission mode</strong><br><span class="muted">${escape(status(state.options.mode))} · ${state.options.dry_run ? "dry run" : "employer submission enabled"}</span>`,
      ]))}</div>`;
}

function jobDetails(job) {
  const match = job.match;
  const concerns = match.concerns || [];
  return panel(`${job.role} · ${job.company}`, `<div class="stack">
    <p>${badge(match.eligibility)} ${badge(job.status)} <strong>${match.match_score ?? 0}/100 relevance</strong></p>
    <p class="muted">${escape(job.location || "Location unavailable")} · ${escape(job.employment || "Employment type unavailable")}
      · ${escape(job.source === "mock" ? "Synthetic listing" : job.source)} ${job.available ? "" : "· Closed or removed"}</p>
    <p class="muted">Salary ${escape(job.salary_min == null ? "unavailable" : `${job.salary_currency} ${job.salary_min}–${job.salary_max ?? job.salary_min}`)}
      · Posting date ${escape(job.posted ? showDate(job.posted) : "unavailable")}</p>
    <p>${escape(match.reason)}</p>
    ${concerns.length ? `<div><h3>Eligibility concerns</h3>${list(concerns.map(escape))}</div>` : ""}
    <p><strong>Matching skills</strong> ${escape((match.matching_skills || []).join(", ") || "None detected")}</p>
    <p><strong>Required skills to verify</strong> ${escape((match.missing_skills || []).join(", ") || "None detected")}</p>
    <p><strong>Score breakdown</strong> ${escape(Object.entries(match.components || {}).map(([key, score]) => `${key} ${score}`).join(" · "))}</p>
    <div class="actions">${button("Open in Resume Studio", "studio-job", job.id, "primary")}
      ${button("Shortlist", "job-status", `${job.id}|SHORTLISTED`)}
      ${button("Skip", "job-status", `${job.id}|SKIPPED`)}
      ${link("Official listing ↗", job.url)}</div>
    <details open><summary>Job description</summary><p class="pre">${escape(jobDescription)}</p></details>
  </div>`);
}

function jobs() {
  const active = state.jobs.find((job) => job.id === selectedJob);
  return heading("Job Discovery", "Browse public listings and review the evidence behind each match.", button("Run discovery", "run", "", "primary")) +
    `<div class="sidebar-grid">${panel("Filters", `<form id="job-filters">
      <label>Role or company<input name="query" placeholder="Search listings"></label>
      <label>Location<input name="location" placeholder="e.g. Remote"></label>
      <label>Eligibility<select name="eligibility"><option value="">All</option><option>ELIGIBLE</option><option>NEEDS_REVIEW</option><option>INELIGIBLE</option></select></label>
      <label>Minimum score<input type="number" name="minimum" min="0" max="100" value="0"></label>
      <label class="inline"><input name="available" type="checkbox" checked> Available only</label>
    </form>`)}<div>${panel("Listings", '<div id="job-table" class="table-wrap"></div>')}${active ? jobDetails(active) : ""}</div></div>`;
}

function filterJobs() {
  const form = document.querySelector("#job-filters");
  if (!form) return;
  const filters = formData(form);
  const visible = state.jobs.filter((job) =>
    (!filters.available || job.available) && `${job.role} ${job.company}`.toLowerCase().includes(filters.query.toLowerCase())
    && job.location.toLowerCase().includes(filters.location.toLowerCase())
    && (!filters.eligibility || job.match.eligibility === filters.eligibility)
    && (job.match.match_score || 0) >= Number(filters.minimum));
  visible.sort((a, b) => (b.match.match_score || 0) - (a.match.match_score || 0));
  document.querySelector("#job-table").innerHTML = visible.length ? `<table><thead><tr><th>Role</th><th>Company</th><th>Location</th><th>Score</th><th>Eligibility</th></tr></thead><tbody>
    ${visible.slice(0, 150).map((job) => `<tr><td>${button(job.role, "job-details", job.id, "link")}</td>
      <td>${escape(job.company)}</td><td>${escape(job.location || "—")}</td>
      <td>${job.match.match_score || 0}</td><td>${badge(job.match.eligibility)}</td></tr>`).join("")}
    </tbody></table><p class="muted small">Showing ${Math.min(150, visible.length)} of ${visible.length}</p>`
    : '<p class="muted">No listings match these filters. Add a board in Settings or paste a description in Resume Studio.</p>';
}

const uploadForm = () => `<form data-form="upload">
  <label>Master resume <input aria-label="Master resume" name="file" type="file" accept=".pdf,.tex,.txt" required></label>
  <div> <button type="submit">Import draft facts</button></div>
</form>`;

function studio() {
  const job = state.jobs.find((row) => row.id === studioJob);
  const jobSelect = `<label>Target role<select id="studio-job"><option value="">Choose a saved role</option>
    ${state.jobs.map((row) => `<option value="${row.id}" ${selected(studioJob, row.id)}>${escape(row.role)} · ${escape(row.company)}</option>`).join("")}
  </select></label>`;
  const version = versions.find((row) => row.id === currentVersion);
  return heading("Resume Studio", "Turn verified profile facts into a job-specific LaTeX resume and PDF.") +
    `<div class="split">${panel("Analyze a posting", `<form data-form="job">
      <div class="fields"><label>Company<input name="company" maxlength="240" placeholder="Employer name"></label>
      <label>Role<input name="role" maxlength="300" placeholder="e.g. Backend Engineer"></label></div>
      <label>Official job URL<input type="url" name="url" placeholder="https://…"></label>
      <label>Job description<textarea name="description" maxlength="100000" placeholder="Paste the full job description"></textarea></label>
      <div><button type="submit" class="primary">Analyze posting</button></div>
    </form>`)}
    ${panel("Resume input", uploadForm() + `<hr>${jobSelect}${job ? `<hr><p>${badge(job.match.eligibility)} <strong>${job.match.match_score}/100 relevance</strong></p>
      <p class="muted">${escape((job.match.concerns || []).join(" ") || job.match.reason)}</p>
      <form data-form="generate"><label>Template<select name="template"><option value="classic">Classic serif</option><option value="compact">Compact sans</option></select></label>
      <label>Tailoring instructions<input name="instructions" maxlength="1200" placeholder="e.g. Prioritize relevant API projects"></label>
      <div class="actions"><button type="submit" class="primary">Generate PDF</button>${button("Draft cover letter", "letter", job.id)}</div></form>` : ""}`)}
    </div>${version ? studioVersion(version, job) : ""}`;
}

function studioVersion(version, job) {
  const report = version.report;
  return panel("Resume versions", `<div class="fields"><label>Current version<select id="version-select">
    ${versions.map((row) => `<option value="${row.id}" ${selected(currentVersion, row.id)}>${escape(showDate(row.created))} · ${escape(row.template)} · ${row.id.slice(0, 6)}</option>`).join("")}
    </select></label><label>Compare with<select id="compare-version"><option value="">Select a version</option>
    ${versions.filter((row) => row.id !== currentVersion).map((row) => `<option value="${row.id}">${escape(showDate(row.created))} · ${row.id.slice(0, 6)}</option>`).join("")}</select></label></div>
    <div id="comparison"></div><hr>
    <div class="studio-grid"><div class="stack"><form data-form="compile">
    <label>LaTeX source<textarea class="code" name="tex" spellcheck="false" required>${escape(version.tex)}</textarea></label>
    <p class="muted small">Change the geometry margin from 0.4 to 1.29 inches. Edit resume wording through verified facts in Profile.</p>
    <div class="actions"><button type="submit" class="primary">Compile</button>${button("Restore this version", "restore", version.id)}
      ${link("Download .tex", `/api/resumes/${version.id}/tex?download=true`)}
      ${link("Download PDF", `/api/resumes/${version.id}/pdf?download=true`)}</div></form>
    <p class="muted">${report.pages} page(s) · ${report.claims.length} verified facts · ${escape(report.ai.provider)}</p>
    ${(report.warnings || []).map((warning) => `<p>${escape(warning)}</p>`).join("")}
    ${report.quality?.compile_status ? `<details><summary>Resume quality</summary>${list([
      `${escape(report.quality.compile_status)} compilation · ${report.quality.text_extractable ? "selectable text" : "text extraction unavailable"}`,
      `Represented skills ${escape(report.quality.represented_skills.join(", ") || "None listed")}`,
      `Missing requirements ${escape(report.quality.missing_requirements.join(", ") || "None identified")}`,
      `${report.quality.unsupported_claims} unsupported claims · ${report.quality.long_bullets} long bullets · ${report.quality.page_overflow ? "Multiple pages" : "Single page"}`,
    ])}</details>` : ""}
    ${report.bullets?.length ? `<details><summary>Edited bullets and source facts</summary>${list(report.bullets.map((bullet) => {
      const fact = report.claims.find((item) => item.id === bullet.fact_id);
      return `${escape(bullet.text)}<br><span class="muted small">Source ${escape(fact?.value || "")}</span>`;
    }))}</details>` : ""}
    <details><summary>Content provenance</summary>${list(report.claims.map((fact) =>
      `<strong>${escape(fact.label)}</strong> ${escape(fact.value)}<br><span class="muted small">${escape(fact.source)}</span>`))}</details>
    <form data-form="prepare">${job.match.eligibility === "NEEDS_REVIEW" ? '<label class="inline"><input type="checkbox" name="review" required> I reviewed the eligibility concerns</label>' : ""}
      ${job.match.eligibility === "INELIGIBLE" ? "<p>Current eligibility blocks preparation.</p>" :
        '<div><button type="submit">Prepare application</button></div>'}</form>
    </div><iframe title="Resume PDF preview" src="/api/resumes/${version.id}/pdf"></iframe></div>`);
}

function needsApproval(row) {
  return row.review_status === "READY_FOR_REVIEW" && !row.summary.exception;
}

function hasException(row) {
  if (["SUBMITTED", "REJECTED", "REJECTED_BY_USER", "SKIPPED", "INTERVIEW", "OFFER", "CLOSED"].includes(row.status)) return false;
  return Boolean(row.summary.exception) || ["NEEDS_REVIEW", "NEEDS_MANUAL_ACTION", "FAILED", "SUBMISSION_UNCERTAIN"].includes(row.status)
    && row.summary.checkpoint !== "PREPARING";
}

function reviewControls() {
  return panel("Review controls", `<div class="stack"><div class="fields">
    <label>Filter applications<select id="review-filter">${Object.entries({
      ready: "Ready for review", missing: "Missing information", unsupported: "Unsupported portal",
      rejected: "Previously rejected", failed: "Submission failed", submitted: "Submitted", all: "All applications",
    }).map(([key, label]) => `<option value="${key}" ${selected(reviewFilter, key)}>${label}</option>`).join("")}</select></label>
    <label>Sort applications<select id="review-sort">${Object.entries({
      score: "Match score", discovered: "Discovery date", company: "Company", posted: "Job posting date",
    }).map(([key, label]) => `<option value="${key}" ${selected(reviewSort, key)}>${label}</option>`).join("")}</select></label>
    </div><div class="actions"><span>${selection.size} selected</span>
    ${selection.size ? button("Review selected submissions", "bulk-approve") + button("Reject selected", "bulk-reject") : ""}
    </div></div>`);
}

function reviewRows() {
  const jobs = new Map(state.jobs.map((job) => [job.id, job]));
  const rows = state.applications.filter((row) => ({
    ready: needsApproval(row), missing: Boolean(row.summary.missing?.length),
    unsupported: Boolean(row.summary.exception) || (row.review_status === "READY_FOR_REVIEW" && !row.summary.browser && !row.summary.integration),
    rejected: ["SKIPPED", "REJECTED_BY_USER", "REJECTED"].includes(row.status),
    failed: ["FAILED", "SUBMISSION_UNCERTAIN"].includes(row.status), submitted: row.status === "SUBMITTED", all: true,
  })[reviewFilter]);
  return rows.sort((a, b) => {
    const left = jobs.get(a.job_id) || {};
    const right = jobs.get(b.job_id) || {};
    if (reviewSort === "company") return (left.company || "").localeCompare(right.company || "");
    if (reviewSort === "posted") return (Date.parse(right.posted) || -Infinity) - (Date.parse(left.posted) || -Infinity);
    if (reviewSort === "discovered") return (right.created || "").localeCompare(left.created || "");
    return (right.match?.match_score ?? -1) - (left.match?.match_score ?? -1);
  });
}

const reviewFieldLabels = {name: "Name", email: "Email", phone: "Phone", first_name: "First name",
  last_name: "Last name", authorization: "Mock screening answer"};

function applicationReview(details, row) {
  const p = details.payload;
  const match = p.match || details.job.match || {};
  const task = details.task;
  const reviewOpen = ["APPLICATION_PREPARED", "READY_FOR_REVIEW", "NEEDS_REVIEW", "NEEDS_MANUAL_ACTION", "APPROVED", "FAILED"].includes(row.status);
  const official = p.job?.apply_url || p.job?.url || details.job.apply_url || details.job.url;
  const answers = p.saved_answers || {};
  return `<div class="stack application-review"><h3>Application preview</h3>
    <p>${escape(details.job.location || "Location unavailable")} · ${escape(details.job.employment || "Employment type unavailable")}
      · ${match.match_score == null ? "Score unavailable" : escape(match.match_score) + "/100 match"} · ${badge(match.eligibility)}</p>
    ${list([["Required skills", match.required_skills], ["Matching skills", match.matching_skills], ["Missing skills", match.missing_skills]]
      .map(([label, values]) => `<strong>${label}</strong> ${escape(values?.join(", ") || "None identified")}`))}
    <details><summary>Original job description</summary><p class="pre">${escape(details.original_description || p.job?.description || details.job.description)}</p></details>
    <section class="stack"><h3>Resume version</h3><p>${escape(details.resume.id)} · ${escape(details.resume.template)} · ${escape(showDate(details.resume.created))}</p>
      <iframe title="Application resume PDF preview" loading="lazy" src="/api/resumes/${escape(details.resume.id)}/pdf"></iframe></section>
    ${p.cover_letter ? `<details><summary>Cover letter draft for manual use</summary><p class="pre">${escape(p.cover_letter)}</p></details>` : ""}
    <h3>Completed fields and screening answers</h3>
    ${list(Object.entries(p.fields || {}).map(([key, value]) => `<strong>${escape(reviewFieldLabels[key] || key)}</strong> ${escape(value)}`)
      .concat(Object.entries(answers).filter(([key]) => key !== "authorization").map(([key, value]) => `<strong>${escape(key)}</strong> ${escape(value)}`)))}
    ${p.pending?.length ? `<p><strong>Missing information</strong> ${escape(p.pending.join(", "))}</p>` : ""}
    ${p.destination ? `<p><strong>Destination</strong> <span class="pre">${escape(p.destination)}</span></p>` : ""}
    ${details.refusal ? `<p class="muted">${escape(details.refusal)}</p>` : ""}
    ${task ? `<p><strong>Submission task</strong> ${badge(task.status)} · approved ${escape(showDate(task.approved_at))}
      ${task.attempted_at ? ` · attempted ${escape(showDate(task.attempted_at))}` : ""}
      ${task.finished_at ? ` · updated ${escape(showDate(task.finished_at))}` : ""}
      · ${escape(task.provider)} · ${task.preflight_attempts} validation attempts
      ${task.result ? ` · ${escape(status(task.result))}` : ""}</p>` : ""}
    <div class="actions">
      ${details.approvable && needsApproval(row) ? button("Approve & Submit", "approve-submit", row.id, "primary") : ""}
      ${reviewOpen ? button("Reject Application", "decision", `${row.id}|reject`) : ""}
      ${reviewOpen ? button("Edit Resume", "edit-reviewed-resume", row.id) + button("Edit Application Answers", "show-answers", row.id) : ""}
      ${link("Open Original Job", official)}
      ${link("Download Resume", `/api/resumes/${details.resume.id}/pdf?download=true`)}
      ${reviewOpen ? button("Refresh preparation", "refresh-preparation", row.id) : ""}
    </div>
    ${details.payload_hash && reviewOpen ? `<label class="inline"><input type="checkbox" data-review-selection="${row.id}" ${checked(selection.has(row.id))}> Select for bulk review</label>` : ""}
    <div id="answers-${row.id}"></div></div>`;
}

function applications(view) {
  const rows = view === "approval" ? reviewRows()
    : view === "exceptions" ? state.applications.filter(hasException) : state.applications;
  const cards = rows.map((row) => {
    const job = state.jobs.find((item) => item.id === row.job_id);
    const review = ["APPLICATION_PREPARED", "READY_FOR_REVIEW", "NEEDS_REVIEW", "NEEDS_MANUAL_ACTION", "FAILED"].includes(row.status);
    const details = reviews.get(row.id);
    const buttonFor = (label, action, css) => button(label, "decision", `${row.id}|${action}`, css);
    return panel(job ? `${job.role} · ${job.company}` : "Application", `<div class="stack">
      <p>${badge(row.review_status)} <span class="muted">${row.summary.simulation ? "Synthetic employer" : row.summary.integration ? "Authorized employer API" : "Manual handoff"}</span></p>
      ${job ? `<p class="muted">${escape(job.location || "Location unavailable")} · ${escape(job.employment || "Employment type unavailable")}
        · ${job.match?.match_score == null ? "Score unavailable" : escape(job.match.match_score) + "/100"}</p>` : ""}
      <p><strong>Prepared fields</strong> ${escape((row.summary.filled || []).join(", ") || "Pending")}</p>
      ${row.summary.missing?.length ? `<p><strong>Missing</strong> ${escape(row.summary.missing.join(", "))}</p>` : ""}
      ${row.summary.exception ? `<p><strong>Exception</strong> ${escape(row.summary.exception)}</p>` : ""}
      ${job?.match.concerns?.length ? `<p><strong>Eligibility</strong> ${escape(job.match.concerns.join(" "))}</p>` : ""}
      ${row.confirmation ? `<p><strong>${row.summary.simulation ? "Mock confirmation" : row.summary.external_confirmation ? "User submitted externally" : "Employer confirmation"}</strong> ${escape(row.confirmation)}</p>` : ""}
      <div class="actions">${button(details ? "Close preview" : row.summary.browser || row.summary.integration ? "Review application" : "Review & Open Application",
        "open-review", row.id, "primary")}${link("Review PDF", `/api/resumes/${row.resume_id}/pdf`)}
        ${row.status === "APPLICATION_PREPARED" && row.summary.browser && !row.summary.custom_answers ? buttonFor("Approve", "approve") : ""}
        ${review ? buttonFor("Reject", "reject") + buttonFor("Request changes", "changes") : ""}
        ${row.status === "APPROVED" && row.summary.browser && !row.summary.durable_approval ? buttonFor("Submit simulation", "simulate", "primary") : ""}
        ${row.status === "APPROVED" ? buttonFor("Request changes", "changes") : ""}
        ${["SUBMISSION_UNCERTAIN", "SUBMITTING"].includes(row.status) ? buttonFor("Reconcile receipt", "reconcile") : ""}
        ${review && job ? button("Review in Studio", "studio-job", job.id) : ""}
        ${link("Open official application ↗", row.summary.official_url)}
        ${button("Show timeline", "timeline", row.id)}</div>
      ${["APPROVED", "SUBMITTED", "INTERVIEW", "OFFER"].includes(row.status) ? `<form class="row" data-form="tracking" data-id="${row.id}">
        <label>Employer update<select name="action"><option value="interview">Interview</option><option value="offer">Offer</option>
          <option value="employer_rejection">Rejection</option><option value="closed">Closed</option></select></label>
        <label>Optional note<input name="note" maxlength="240"></label><button type="submit">Record update</button></form>` : ""}
      ${!row.summary.simulation && ["APPROVED", "APPLICATION_PREPARED", "READY_FOR_REVIEW", "NEEDS_MANUAL_ACTION", "SUBMISSION_UNCERTAIN"].includes(row.status) ? `<form class="row" data-form="tracking" data-id="${row.id}">
        <input name="action" type="hidden" value="record_confirmation">
        <label>Employer confirmation reference<input name="note" minlength="3" maxlength="175" required></label>
        <button type="submit">Record receipt</button></form>` : ""}
      ${details ? applicationReview(details, row) : ""}
      <div id="timeline-${row.id}"></div></div>`);
  });
  const jobExceptions = view === "exceptions" ? state.jobs.filter((job) => job.available &&
    (job.automation?.state === "EXCEPTION" || (job.match.eligibility === "NEEDS_REVIEW" &&
      job.match.match_score >= state.options.min_match_score && !state.applications.some((app) => app.job_id === job.id))))
    .map((job) => panel(`${job.role} · ${job.company}`,
      `<p>${escape(job.automation?.reason || job.match.concerns.join(" "))}</p><div class="actions">
      ${button("Review in Studio", "studio-job", job.id)}
      ${job.automation?.state === "EXCEPTION" ? button("Reset internal retry", "retry-job", job.id) : ""}</div>`)) : [];
  return heading(view === "approval" ? "Approval Queue" : view === "exceptions" ? "Exception Queue" : "Applications",
    view === "approval" ? "Approve external actions and simulations that require an individual decision."
      : view === "exceptions" ? "Resolve missing information, unsupported forms, and exhausted retries."
      : "Track drafts, decisions, and confirmation evidence.") + (view === "approval" ? reviewControls() : "") + (cards.concat(jobExceptions).join("") ||
    panel("No applications yet", '<p class="muted">Prepare an application from a resume version in Resume Studio.</p>'));
}

function notifications() {
  return heading("Notifications", "Review ready applications and submission updates.",
    button("Mark all read", "read-notifications")) + panel("Activity", list(notices.map((notice) =>
    `<strong>${escape(notice.message)}</strong> <span class="muted small">${escape(showDate(notice.created))}${notice.read ? "" : " · Unread"}</span>
    <div><a href="${notice.kind === "ready" ? "#approvals" : "#applications"}">${notice.kind === "ready" ? "Open Approval Queue" : "Open Applications"}</a></div>`)));
}

function automation() {
  const opt = state.options;
  const runs = state.runs.map((run) => `<tr><td>${escape(showDate(run.created))}</td><td>${escape(status(run.trigger))}</td>
    <td>${badge(run.status)}</td><td>${escape(showDate(run.finished))}</td>
    <td><details><summary>View</summary><p class="pre">${escape(JSON.stringify(run.report, null, 2))}</p></details></td>
    <td>${["QUEUED", "RUNNING"].includes(run.status) && !run.canceled ? button("Cancel", "cancel", run.id) : ""}</td></tr>`);
  const worker = state.worker;
  const model = worker.model || {};
  return heading("Automation Control Center", "Schedule discovery and resume preparation independently of this dashboard.", button("Run now", "run", "", "primary")) +
    panel("Worker health", list([`${badge(worker.status)} · ${worker.pending} pending runs`,
      `Last heartbeat ${escape(showDate(worker.last_heartbeat))} · last success ${escape(showDate(worker.last_success))}`,
      `Next run ${escape(showDate(state.next_run))} · model ${escape(status(model.status))} ${escape(model.name || "")}`,
      `${state.jobs.filter((job) => job.status === "FAILED").length} failed jobs ·
        ${state.jobs.filter((job) => job.automation?.state === "RETRY_WAIT").length} retries waiting · <a href="#exceptions">Exception Queue</a>`])) +
    panel("Daily summary", list([
      `${state.daily.runs} completed or failed runs · ${state.daily.failed_runs} failed runs`,
      `${state.daily.scanned} observations scanned · ${state.daily.filtered} filtered · ${state.daily.new_jobs} new job records`,
      `${state.daily.compiled} resumes compiled · ${state.daily.prepared} forms prepared · ${state.daily.submitted} confirmed scheduled submissions`])) +
    panel("Schedule and limits", `<form data-form="automation"><div class="fields">
    <label class="inline"><input type="checkbox" name="enabled" ${checked(opt.enabled)}> Hourly automation enabled</label>
    <label class="inline"><input type="checkbox" name="retry_failed_jobs" ${checked(opt.retry_failed_jobs)}> Retry failed preparation</label>
    <label class="inline"><input type="checkbox" name="exception_notifications" ${checked(opt.exception_notifications)}> Log exhausted retries as exception notifications</label>
    ${[
      ["interval_minutes", "Interval in minutes", 1, 1440], ["min_match_score", "Minimum relevance score", 0, 100],
      ["max_applications_per_day", "Daily preparation limit", 0, 100], ["max_resume_generations_per_run", "Resumes per run", 0, 50],
      ["max_submissions_per_day", "Daily submission limit", 0, 100], ["max_job_attempts", "Attempts per failed job", 1, 8],
    ].map(([name, label, min, max]) => `<label>${label}<input type="number" name="${name}" value="${opt[name]}" min="${min}" max="${max}" required></label>`).join("")}
    <label>Application mode<select name="mode"><option value="ASSISTED" ${selected(opt.mode, "ASSISTED")}>Assisted</option><option value="MANUAL" ${selected(opt.mode, "MANUAL")}>Manual</option>
      ${state.authorized_board ? `<option value="AUTHORIZED_AUTO" ${selected(opt.mode, "AUTHORIZED_AUTO")}>Authorized employer API</option>` : ""}</select></label>
    <label>Display timezone<input name="timezone" value="${escape(opt.timezone)}" required></label></div>
    ${state.authorized_board ? `<label class="inline"><input type="checkbox" name="live" ${checked(!opt.dry_run)}> Enable individually approved submission for ${escape(state.authorized_board)}</label>` : ""}
    <label class="inline"><input type="checkbox" name="desktop_notifications" ${checked(opt.desktop_notifications)}> Windows desktop review notifications</label>
    <label class="inline"><input type="checkbox" name="approval_email" ${checked(opt.approval_email)}> Email review notifications with configured SMTP</label>
    <label>Notification interval in minutes<input name="notification_interval_minutes" type="number" min="1" max="1440" value="${opt.notification_interval_minutes}" required></label>
    <p class="muted">Autonomous Preparation + Manual Final Approval · ${opt.dry_run ? "Dry run active" : "Employer submission enabled"}</p>
    <div class="actions"><button class="primary" type="submit">Save schedule</button>${button(opt.enabled ? "Pause" : "Resume", "toggle", "", "")}</div></form>`) +
    panel("Model and source controls", `<form data-form="model-settings">${modelFields(opt)}
      <div><button class="primary" type="submit">Save model</button></div></form>
      <div class="stack">${sourceControls(opt)}<a href="#settings">Add or edit source boards</a></div>`) +
    panel("Run history", runs.length ? `<div class="table-wrap"><table><thead><tr><th>Created</th><th>Trigger</th><th>Status</th><th>Finished</th><th>Report</th><th></th></tr></thead><tbody>${runs.join("")}</tbody></table></div>` : '<p class="muted">No runs yet.</p>') +
    panel("Execution logs and notifications", list(state.logs.map((row) =>
      `<strong>${escape(row.message)}</strong> <span class="muted small">${escape(showDate(row.created))}</span>
       <details><summary>Details</summary><p class="pre">${escape(JSON.stringify(row.detail, null, 2))}</p></details>`)));
}

const prefLabels = {
  roles: "Target roles", locations: "Preferred locations", work_modes: "Work modes (remote, hybrid, onsite)",
  employment: "Employment types", levels: "Experience keywords", excluded_keywords: "Excluded keywords",
  target_companies: "Allowed companies", excluded_companies: "Excluded companies",
  min_salary: "Minimum annual salary", salary_currency: "Salary currency", recent_days: "Posted in last N days", relocation: "Relocation preferences",
  career_tracks: "Tracks (entry-level, graduate, backend, full-stack, data, ai-ml, internship)",
  maximum_mandatory_years: "Maximum required experience (years)",
};

function factRow(fact) {
  return `<div class="fact" data-fact="${escape(fact.id)}" data-source="${escape(fact.source)}" data-excerpt="${escape(fact.excerpt)}">
    <select aria-label="Fact category" data-field="category">${["personal", "education", "experience", "skill", "project", "authorization", "certification", "other"].map(
      (category) => `<option ${selected(category, fact.category)}>${category}</option>`).join("")}</select>
    <input aria-label="Fact label" data-field="label" maxlength="100" value="${escape(fact.label)}" placeholder="Label" required>
    <input aria-label="Fact value" data-field="value" maxlength="1500" value="${escape(fact.value)}" placeholder="Verified wording" required>
    <label class="inline" title="${escape(fact.excerpt || fact.source)}"><input type="checkbox" data-field="verified" ${checked(fact.verified)}> Verified</label>
    ${button("Remove", "remove-fact")}</div>`;
}

function profile() {
  const prefs = state.profile.preferences;
  return heading("Profile", "Manage the source facts JobForge can use in resumes and applications.") +
    panel("Master resume import", uploadForm()) +
    `<form data-form="profile">${panel("Profile facts", `<div class="stack">
    <p class="muted">Confirm imported facts before using them. Use Name, Email and Phone as labels for contact information.</p>
    <div class="stack" id="facts">${state.profile.facts.map(factRow).join("")}</div>
    <div>${button("Add fact", "add-fact")}</div></div>`)}
    ${panel("Job preferences", `<div class="fields">${Object.entries(prefLabels).map(([key, label]) => {
      const value = Array.isArray(prefs[key]) ? prefs[key].join(", ") : prefs[key] ?? "";
      const type = ["min_salary", "recent_days", "maximum_mandatory_years"].includes(key) ? "number" : "text";
      return `<label>${escape(label)}<input name="${key}" type="${type}" min="0" value="${escape(value)}"></label>`;
    }).join("")}<label class="inline"><input type="checkbox" name="exclude_senior_roles" ${checked(prefs.exclude_senior_roles)}> Exclude senior titles</label>
    </div><p class="muted small">Separate multiple values with commas.</p>
    ${button("Use early-career engineering filters", "early-career-preset")}`)}
    <div><button class="primary" type="submit">Save profile</button></div></form>`;
}

function modelFields(opt) {
  return `<div class="fields">
    <label>Provider<select name="provider"><option value="">Use environment default</option>
    ${["ollama", "rules", "anthropic", "openai"].map((name) => `<option ${selected(opt.provider, name)}>${name}</option>`).join("")}
    </select></label><label>Model override<input name="model" value="${escape(opt.model)}" placeholder="Use environment default"></label></div>`;
}

function sourceControls(opt) {
  return list(opt.sources.map((source, index) =>
    `${escape(source.company)} · ${escape(source.provider)} ${button(source.enabled ? "Disable" : "Enable", "source-toggle", String(index))}`));
}

function settings() {
  const opt = state.options;
  return heading("Settings", "Configure model access, source boards, and local data.") +
    panel("AI provider and job sources", `<form data-form="settings">${modelFields(opt)}
    <p class="muted">Configured provider ${escape(state.provider)} · ${escape(state.model || "default rules")}. Credentials come from environment variables.</p>
    <label>Job boards<textarea name="sources" rows="5" placeholder="greenhouse,board-id,Company">${escape(opt.sources.map((row) => `${row.provider},${row.board},${row.company}`).join("\n"))}</textarea></label>
    <p class="muted small">Enter one board per line as provider, board ID, company. Providers are greenhouse, lever, ashby, and mock.</p>
    <div><button class="primary" type="submit">Save sources and model</button></div></form>`) +
    panel("Source availability", sourceControls(opt)) +
    panel("Local data", `<div class="stack"><p>Original resumes and generated PDFs are stored in the private database.
    Access token and database settings are configured in your environment.</p><div class="actions">
    ${link("Export workspace", "/api/export")}${button("Delete workspace data", "erase", "", "danger")}
    ${!state.profile.facts.length ? button("Load synthetic test profile", "demo") : ""}</div></div>`);
}

async function loadVersions(jobId, versionId = null) {
  studioJob = jobId;
  versions = jobId ? await api(`/jobs/${jobId}/resumes`) : [];
  currentVersion = versionId ?? versions[0]?.id;
}

function go(page) {
  if (nowPage() === page) render();
  else location.hash = page;
}

async function act(action, id, target) {
  if (action === "edit-reviewed-resume") {
    const detail = reviews.get(id);
    await loadVersions(detail.job.id, detail.resume.id);
    go("studio");
    return;
  }
  if (action === "open-review") {
    if (reviews.has(id)) { reviews.delete(id); selection.delete(id); }
    else reviews.set(id, await api(`/applications/${id}/review`));
    render();
    return;
  }
  if (action === "show-answers") {
    const details = reviews.get(id);
    const dest = document.querySelector(`#answers-${id}`);
    if (!dest || !details) return;
    const payload = details.payload;
    if (payload.provider === "greenhouse") {
      dest.innerHTML = '<p>Contact fields come from verified Profile facts. Save changes in <a href="#profile">Profile</a>, then refresh preparation.</p>';
      return;
    }
    const isMock = Boolean(details.application.summary.browser);
    const saved = payload.saved_answers || {};
    dest.innerHTML = `<form data-form="review-answers" data-id="${id}">
      ${isMock ? `<label>Mock screening answer<textarea name="answer" maxlength="1500">${escape(saved.authorization ?? payload.fields?.authorization ?? "")}</textarea></label>`
        : `<label>Manual answers, one question and answer per line separated by a tab<textarea name="answer">${escape(
          Object.entries(saved).map(([question, answer]) => question + "\t" + answer.replace(/\r?\n/g, " ")).join("\n"))}</textarea></label>`}
      <div><button type="submit">Save answers and reprepare</button></div></form>`;
    return;
  }
  if (action === "approve-submit") {
    const detail = reviews.get(id);
    await api(`/applications/${id}/approve-submit`, "POST", { application_id: id, payload_hash: detail.payload_hash });
    reviews.set(id, await api(`/applications/${id}/review`));
    await refresh(false);
    notify("Approval recorded. Submission queued.");
    go("applications");
    return;
  }
  if (["bulk-approve", "bulk-reject"].includes(action)) {
    const picked = [...selection].map((key) => reviews.get(key)).filter(Boolean);
    if (!picked.length) return;
    if (action === "bulk-approve" && picked.some((item) => !item.approvable)) {
      throw new Error("Every selected application must support submission and be ready for approval.");
    }
    const label = action === "bulk-approve" ? "Approve and submit these exact applications?" : "Reject these exact applications?";
    const rows = picked.map((item) => `${item.job.role} — ${item.job.company}\nResume ${item.resume.id} · ${item.payload.destination || "manual handoff"}`);
    if (!window.confirm([label, ...rows].join("\n\n"))) return;
    await api(action === "bulk-approve" ? "/applications/bulk-review" : "/applications/bulk-reject", "POST", {
      reviews: picked.map((item) => ({application_id: item.application.id, payload_hash: item.payload_hash})),
    });
    selection.clear();
    for (const item of picked) reviews.set(item.application.id, await api(`/applications/${item.application.id}/review`));
    await refresh(false);
    notify(action === "bulk-approve" ? "Selected applications queued." : "Selected applications rejected.");
    go(action === "bulk-approve" ? "applications" : "approvals");
    return;
  }
  if (action === "job-details") {
    const job = await api(`/jobs/${id}`);
    selectedJob = id;
    jobDescription = job.description;
    const criteria = formData(document.querySelector("#job-filters"));
    render();
    const form = document.querySelector("#job-filters");
    for (const [name, value] of Object.entries(criteria)) form.elements[name].value = value;
    form.elements.available.checked = Boolean(criteria.available);
    filterJobs();
    return;
  }
  if (action === "studio-job") {
    await loadVersions(id);
    go("studio");
    return;
  }
  if (action === "add-fact") {
    const bytes = crypto.getRandomValues(new Uint8Array(16));
    const key = Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
    document.querySelector("#facts").insertAdjacentHTML("beforeend",
      factRow({ id: key, category: "personal", source: "manual", label: "", value: "", verified: false }));
    return;
  }
  if (action === "remove-fact") {
    target.closest(".fact").remove();
    return;
  }
  if (action === "timeline") {
    const events = await api(`/applications/${id}/events`);
    document.querySelector(`#timeline-${id}`).innerHTML = list(events.map((row) =>
      `${badge(row.status)} ${escape(row.message)} <span class="muted small">${escape(showDate(row.created))}</span>`));
    return;
  }
  if (action === "letter") {
    const letter = await api(`/jobs/${id}/letter`);
    const file = new Blob([letter.content], { type: "text/plain" });
    const url = URL.createObjectURL(file);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "cover-letter.txt";
    anchor.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    return;
  }
  if (action === "erase") {
    if (!window.confirm("Delete profile data, original resumes, jobs, generated PDFs, and run history?")) return;
    await api("/data", "DELETE");
    await loadVersions("");
  } else if (action === "demo") {
    await api("/demo", "POST");
    notify("Synthetic profile loaded and example run queued.");
  } else if (action === "run") {
    await api("/runs", "POST");
    notify("Run requested.");
  } else if (action === "cancel") {
    await api(`/runs/${id}/cancel`, "POST");
  } else if (action === "toggle") {
    await api("/settings", "PUT", { ...state.options, enabled: !state.options.enabled });
  } else if (action === "retry-job") {
    await api(`/jobs/${id}/retry`, "POST");
  } else if (action === "refresh-preparation") {
    await api(`/applications/${id}/review`, "PUT", {});
    reviews.set(id, await api(`/applications/${id}/review`));
    selection.delete(id);
  } else if (action === "read-notifications") {
    await api("/notifications/read", "POST");
    notices = await api("/notifications");
  } else if (action === "source-toggle") {
    const sources = state.options.sources.map((source, index) => index === Number(id) ? { ...source, enabled: !source.enabled } : source);
    await api("/settings", "PUT", { ...state.options, sources });
  } else if (action === "early-career-preset") {
    const form = target.closest("form");
    form.elements.career_tracks.value = "entry-level, graduate, backend, full-stack, data, ai-ml, internship";
    form.elements.exclude_senior_roles.checked = true;
    form.elements.maximum_mandatory_years.value = 2;
    return;
  } else if (action === "decision") {
    const [appId, decision] = id.split("|");
    await api(`/applications/${appId}/decision`, "POST", { action: decision });
    if (reviews.has(appId)) reviews.set(appId, await api(`/applications/${appId}/review`));
    selection.delete(appId);
  } else if (action === "job-status") {
    const [jobId, nextStatus] = id.split("|");
    await api(`/jobs/${jobId}/status`, "PUT", { status: nextStatus });
  } else if (action === "restore") {
    const result = await api(`/resumes/${id}/restore`, "POST");
    await loadVersions(studioJob, result.id);
  }
  await refresh();
  filterJobs();
}

async function submit(form) {
  const values = formData(form);
  const kind = form.dataset.form;
  if (kind === "upload") {
    const result = await api("/profile/upload", "POST", new FormData(form));
    notify(`Imported ${result.imported} draft facts. Confirm them in Profile.`);
  } else if (kind === "job") {
    const input = { url: values.url || null, description: values.description };
    if (values.company.trim()) input.company = values.company.trim();
    if (values.role.trim()) input.role = values.role.trim();
    const job = await api("/jobs", "POST", input);
    await loadVersions(job.id);
  } else if (kind === "generate") {
    const version = await api(`/jobs/${studioJob}/resumes`, "POST", { ...values, parent_id: currentVersion });
    await loadVersions(studioJob, version.id);
  } else if (kind === "compile") {
    const version = await api(`/resumes/${currentVersion}/compile`, "POST", values);
    await loadVersions(studioJob, version.id);
  } else if (kind === "prepare") {
    await api(`/jobs/${studioJob}/prepare`, "POST", { resume_id: currentVersion, review_accepted: Boolean(values.review) });
    notify("Application preparation recorded.");
    await refresh(false);
    const application = state.applications.find((row) => row.job_id === studioJob);
    go(application && hasException(application) ? "exceptions" : "approvals");
    return;
  } else if (kind === "tracking") {
    await api(`/applications/${form.dataset.id}/decision`, "POST", values);
  } else if (kind === "review-answers") {
    const id = form.dataset.id;
    const detail = reviews.get(id);
    const answers = detail.application.summary.browser ? {authorization: values.answer}
      : Object.fromEntries(values.answer.split("\n").filter((line) => line.trim()).map((line) => {
        const tab = line.indexOf("\t");
        if (tab < 1) throw new Error("Separate each manual question and answer with a tab.");
        return [line.slice(0, tab).trim(), line.slice(tab + 1).trim()];
      }));
    await api(`/applications/${id}/review`, "PUT", {answers});
    reviews.set(id, await api(`/applications/${id}/review`));
    selection.delete(id);
  } else if (kind === "automation") {
    for (const key of ["interval_minutes", "min_match_score", "max_applications_per_day", "max_resume_generations_per_run",
      "max_submissions_per_day", "max_job_attempts", "notification_interval_minutes"]) {
      values[key] = Number(values[key]);
    }
    values.enabled = Boolean(values.enabled);
    values.retry_failed_jobs = Boolean(values.retry_failed_jobs);
    values.exception_notifications = Boolean(values.exception_notifications);
    values.dry_run = values.mode !== "AUTHORIZED_AUTO" || !values.live;
    values.auto_submit = false;
    values.automation_mode = "AUTONOMOUS_PREPARATION";
    values.desktop_notifications = Boolean(values.desktop_notifications);
    values.approval_email = Boolean(values.approval_email);
    delete values.live;
    await api("/settings", "PUT", { ...state.options, ...values });
  } else if (kind === "model-settings") {
    await api("/settings", "PUT", { ...state.options, provider: values.provider || null, model: values.model });
  } else if (kind === "settings") {
    const sources = values.sources.split("\n").filter((line) => line.trim()).map((line) => {
      const [provider, board, ...company] = line.split(",");
      const existing = state.options.sources.find((source) => source.provider === provider.trim() && source.board === board?.trim());
      return { provider: provider.trim(), board: board?.trim(), company: company.join(",").trim(), enabled: existing?.enabled ?? true };
    });
    await api("/settings", "PUT", { ...state.options, sources, provider: values.provider || null, model: values.model });
  } else if (kind === "profile") {
    const facts = Array.from(form.querySelectorAll(".fact")).map((row) => ({
      id: row.dataset.fact, source: row.dataset.source, excerpt: row.dataset.excerpt,
      category: row.querySelector('[data-field="category"]').value,
      label: row.querySelector('[data-field="label"]').value.trim(),
      value: row.querySelector('[data-field="value"]').value.trim(),
      verified: row.querySelector('[data-field="verified"]').checked,
    }));
    for (const key of Object.keys(prefLabels)) {
      if (["min_salary", "recent_days", "maximum_mandatory_years"].includes(key)) values[key] = values[key] ? Number(values[key]) : null;
      else if (!["salary_currency", "relocation"].includes(key)) values[key] = values[key].split(",").map((s) => s.trim()).filter(Boolean);
    }
    values.exclude_senior_roles = Boolean(values.exclude_senior_roles);
    await api("/profile", "PUT", { facts, preferences: values });
  }
  if (kind !== "upload") notify("Saved.");
  await refresh();
}

async function task(target, callback) {
  if (busy) return;
  busy = true;
  if (target) target.disabled = true;
  try {
    await callback();
  } catch (error) {
    notify(error.message, true);
  } finally {
    if (target) target.disabled = false;
    busy = false;
  }
}

content.addEventListener("click", (event) => {
  const target = event.target.closest("[data-action]");
  if (target) task(target, () => act(target.dataset.action, target.dataset.id, target));
});
content.addEventListener("submit", (event) => {
  event.preventDefault();
  if (event.target.dataset.form) task(event.submitter, () => submit(event.target));
});
content.addEventListener("input", (event) => {
  if (event.target.closest("#job-filters")) filterJobs();
});
content.addEventListener("change", (event) => {
  const target = event.target;
  if (target.id === "review-filter" || target.id === "review-sort") {
    if (target.id === "review-filter") reviewFilter = target.value;
    else reviewSort = target.value;
    render();
  }
  if (target.dataset.reviewSelection) {
    if (target.checked && selection.size >= 20) {
      target.checked = false;
      notify("Select at most 20 applications per batch.", true);
      return;
    }
    if (target.checked) selection.add(target.dataset.reviewSelection);
    else selection.delete(target.dataset.reviewSelection);
    const position = window.scrollY;
    render();
    window.scrollTo(0, position);
  }
  if (target.id === "studio-job") task(target, async () => {
    await loadVersions(target.value);
    render();
  });
  if (target.id === "version-select") {
    currentVersion = target.value;
    render();
  }
  if (target.id === "compare-version") {
    const old = versions.find((row) => row.id === target.value);
    const current = versions.find((row) => row.id === currentVersion);
    const previousLines = old?.tex.split("\n") || [];
    const currentLines = current?.tex.split("\n") || [];
    const changed = currentLines.reduce((count, line, index) => count + Number(line !== previousLines[index]), 0);
    document.querySelector("#comparison").innerHTML = old && current ? `<details open><summary>Compare LaTeX versions · ${changed} changed line positions</summary>
      <div class="fields"><label>Previous source<textarea class="code" readonly>${escape(old.tex)}</textarea></label>
      <label>Current source<textarea class="code" readonly>${escape(current.tex)}</textarea></label></div></details>` : "";
  }
});
window.addEventListener("hashchange", () => {
  if (state) {
    window.scrollTo(0, 0);
    render();
    filterJobs();
    if (nowPage() === "notifications") api("/notifications").then((rows) => { notices = rows; render(); }).catch(() => {});
  }
});
document.querySelector("#refresh").addEventListener("click", (event) => task(event.target, async () => {
  if (studioJob) await loadVersions(studioJob, currentVersion);
  await refresh();
  filterJobs();
}));
document.querySelector("#theme").addEventListener("click", () => {
  const theme = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
  document.documentElement.dataset.theme = theme;
  localStorage.setItem("jobforge-theme", theme);
});
document.documentElement.dataset.theme = localStorage.getItem("jobforge-theme") ||
  (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");

refresh().then(async () => {
  filterJobs();
  if (nowPage() === "notifications") { notices = await api("/notifications"); render(); }
}).catch((error) => {
  content.textContent = error.message;
});
setInterval(() => {
  if (!busy && nowPage() === "overview") refresh().catch(() => {});
  if (!busy && nowPage() === "applications" && state?.applications.some((row) =>
    row.summary.durable_approval && ["APPROVED", "SUBMITTING"].includes(row.status))) {
    refresh(false).then(async () => {
      for (const [id] of reviews) reviews.set(id, await api(`/applications/${id}/review`));
      if (nowPage() === "applications") render();
    }).catch(() => {});
  }
}, 7000);
