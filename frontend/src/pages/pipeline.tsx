import { useState } from "react";
import { ArrowUpRight, Columns3, List, ShieldCheck } from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { appPath, jobPath, officialUrl, resumeUrl } from "../api";
import type { Application, Event, Job, Review } from "../api";
import { date, evidence, isApplicationException, isJobException, label, searchMatch, stage, stages } from "../domain";
import { Details, Empty, ErrorNotice, Heading, Loading, Modal, Panel, Status, useResource } from "../shared";
import type { PageProps } from "../shared";
import { JobDrawer, MatchDetails } from "./jobs";
import { Company } from "./overview";
import { Readiness } from "./intelligence";
import { ReviewBatch } from "./review-batch";

const editable = ["APPLICATION_PREPARED", "READY_FOR_REVIEW", "NEEDS_REVIEW", "NEEDS_MANUAL_ACTION", "APPROVED", "FAILED"];
const manual = ["APPLICATION_PREPARED", "READY_FOR_REVIEW", "NEEDS_MANUAL_ACTION", "APPROVED", "SUBMISSION_UNCERTAIN"];
const rejectable = ["APPLICATION_PREPARED", "READY_FOR_REVIEW", "NEEDS_REVIEW", "NEEDS_MANUAL_ACTION"];
const queueFilters = {
  ready: "Ready for review", dispatch: "Ready to submit", uncertain: "Submission uncertain", missing: "Missing information", manual: "Manual handoff",
  rejected: "Previously rejected", failed: "Submission failed", submitted: "Submitted", all: "All applications",
};
const queueSorts = { recommended: "Recommended first", score: "Highest match", expiring: "Expiring soon", discovered: "Discovery date", company: "Company", posted: "Recently posted" };

const reasons = {not_interested: "Not interested", wrong_location: "Wrong location", too_senior: "Too senior",
  salary_mismatch: "Salary mismatch", already_applied: "Already applied", incorrect_match: "Incorrect match", other: "Other"};

function matchesQueue(app: Application, filter: keyof typeof queueFilters, canDispatch: boolean) {
  switch (filter) {
    case "ready": return app.review_status === "READY_FOR_REVIEW" && !app.summary.missing?.length;
    case "dispatch": return canDispatch;
    case "uncertain": return app.review_status === "SUBMISSION_UNCERTAIN";
    case "missing": return Boolean(app.summary.missing?.length);
    case "manual": return app.submission_method === "manual" || Boolean(app.summary.exception);
    case "rejected": return ["REJECTED", "REJECTED_BY_USER"].includes(app.review_status);
    case "failed": return ["FAILED", "SUBMISSION_FAILED", "SUBMISSION_UNCERTAIN", "SUBMISSION_BLOCKED"].includes(app.review_status);
    case "submitted": return Boolean(app.confirmation) || app.status === "SUBMITTED";
    case "all": return true;
  }
}

function compareJobs(a: Job, b: Job, sort: keyof typeof queueSorts) {
  switch (sort) {
    case "recommended":
    case "score": return (b.match.match_score ?? -1) - (a.match.match_score ?? -1);
    case "company": return a.company.localeCompare(b.company) || a.role.localeCompare(b.role);
    case "expiring": {
      const expiry = (job: Job) => {
        const at = Date.parse(job.deadline ?? "");
        return job.available && Number.isFinite(at) && at > Date.now() ? at : Number.MAX_SAFE_INTEGER;
      };
      return expiry(a) - expiry(b);
    }
    case "posted": {
      const left = Date.parse(a.posted ?? "");
      const right = Date.parse(b.posted ?? "");
      return (Number.isFinite(right) ? right : 0) - (Number.isFinite(left) ? left : 0);
    }
    case "discovered": return b.created.localeCompare(a.created);
  }
}

const tracking = ["APPROVED", "SUBMITTED", "INTERVIEW", "OFFER"];

function ReviewDrawer({ id, close, mutate, revision, busy, selected, toggle }: Pick<PageProps, "mutate" | "revision" | "busy"> & { id: string; close: () => void; selected?: Review; toggle?: (review: Review) => void }) {
  const { data: review, error } = useResource<Review>(appPath(id) + "/review", revision);
  const { data: events, error: eventError } = useResource<Event[]>(appPath(id) + "/events", revision);
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState("");
  const [block, setBlock] = useState(false);
  const [excludeSenior, setExcludeSenior] = useState(false);
  const [copied, setCopied] = useState("");
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<string>();
  const [reference, setReference] = useState("");
  const [outcome, setOutcome] = useState("interview");
  const app = review?.application;
  const provider = review?.payload.provider;
  const originalLink = officialUrl(review?.job.url);
  const applyLink = officialUrl(review?.job.apply_url) ?? originalLink;
  async function copyAnswer(value: string, field: string) {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(field + " copied.");
    } catch {
      setCopied("Clipboard unavailable. Select and copy the value manually.");
    }
  }
  async function decide(action: string, message: string, note = "") {
    return mutate(appPath(id) + "/decision", "POST", {action, note}, message);
  }
  return <>
    <Modal title="Application details" drawer close={close}>
      <ErrorNotice message={error}/>{!review && !error && <Loading/>}
      {review && app && <>
        <div className="inline"><Company job={review.job}/><Status value={review.readiness}/></div>
        <Panel title="Prepared application" caption="Review the saved content and selected resume before approving this version.">
          <Details values={{
            provider, destination: review.payload.destination,
            "employment type": review.job.employment, "location": review.job.location, "posting date": date(review.job.posted),
            "eligibility at preparation": label(review.payload.eligibility),
            "prepared at": date(review.payload.prepared_at), "resume version": review.resume.id,
            template: label(review.resume.template), "payload hash": review.payload_hash,
          }}/>
          <div className="inline">
            <a className="text-link" href={resumeUrl(review.resume.id)} target="_blank" rel="noreferrer">Preview PDF <ArrowUpRight size={14}/></a>
            <a className="text-link" href={resumeUrl(review.resume.id, "pdf", true)}>Download PDF</a>
            <a className="text-link" href={resumeUrl(review.resume.id, "tex", true)}>Download LaTeX</a>
          </div>
          <details><summary>Saved resume PDF</summary><iframe className="pdf" title="Application resume PDF" src={resumeUrl(review.resume.id)} loading="lazy"/></details>
          {review.payload.fields && <details open><summary>Exact form fields</summary><Details values={review.payload.fields}/></details>}
          {!!Object.keys(review.payload.saved_answers ?? {}).length && <details open><summary>Saved answers</summary><Details values={review.payload.saved_answers ?? {}}/></details>}
          <details><summary>Cover letter</summary><p className="preserve">{review.payload.cover_letter || "No cover letter is saved on this version."}</p></details>
          {!!review.payload.pending?.length && <ul className="bullets">{review.payload.pending.map((item, index) => <li key={index}>{item}</li>)}</ul>}
          <ErrorNotice message={review.refusal ?? undefined}/>
          {review.approvable && review.payload_hash && <>
            <p className="subtle">Approve this exact resume, answers and destination to queue submission.</p>
            <Button disabled={busy} onClick={() => void mutate(appPath(id) + "/approve-submit", "POST",
              {application_id: id, payload_hash: review.payload_hash}, "Final approval recorded. Submission is queued for verification.")}><ShieldCheck size={16}/> Approve &amp; submit</Button>
          </>}
          {provider === "manual" && <>
            <ol className="bullets">
              <li>Download the saved PDF and open the employer form.</li>
              <li>Enter the verified contact fields and review any required answers and consent yourself.</li>
              <li>After submitting on the employer site, return with the confirmation reference.</li>
            </ol>
            <div className="stack">{Object.entries({...review.payload.fields, ...review.payload.saved_answers}).filter(([, value]) => typeof value === "string" && value).map(([field, value]) =>
              <div className="inline" key={field}><Button size="sm" variant="outline" onClick={() => void copyAnswer(String(value), field)}>Copy {field}</Button></div>)}</div>
            {copied && <p role="status">{copied}</p>}
          </>}
          {provider === "manual" && review.payload.cover_letter && <Button size="sm" variant="outline"
            onClick={() => void copyAnswer(review.payload.cover_letter!, "Cover letter")}>Copy cover letter</Button>}
          {provider === "manual" && applyLink && <Button asChild variant="outline">
            <a href={applyLink} target="_blank" rel="noreferrer">Review &amp; open application <ArrowUpRight size={15}/></a>
          </Button>}
          {review.approvable && review.payload.provider === "mock" && <p className="subtle">This destination is a local submission simulation.</p>}
        </Panel>
        <Panel title="Review actions">
          <div className="inline">
            {editable.includes(app.status) && <>
              <Button variant="outline" disabled={busy} onClick={() => void mutate(appPath(id) + "/review", "PUT", {}, "Application preparation refreshed.")}>Refresh preparation</Button>
              <Button variant="outline" disabled={busy} onClick={() => setRejecting(true)}>Reject application</Button>
            </>}
            {app.status === "SUBMISSION_UNCERTAIN" && <Button variant="outline" disabled={busy} onClick={() => void decide("reconcile", "Reconciliation checked. Review the current receipt status.")}>Check receipt</Button>}
            <Link className="text-link" to={"/resume-studio?job=" + review.job.id}>Edit resume <ArrowUpRight size={14}/></Link>
            <Link className="text-link" to={"/jobs?similar=" + review.job.id}>Find similar roles <ArrowUpRight size={14}/></Link>
          </div>
          {review.payload.provider === "mock" && editable.includes(app.status) && <form className="stack" onSubmit={event => {
            event.preventDefault();
            void mutate(appPath(id) + "/review", "PUT", {answers: {authorization: answer ?? review.payload.saved_answers?.authorization ?? ""}}, "Screening answer saved. Review the refreshed version before approving.");
          }}>
            <label>Mock screening answer · work authorization<input required maxLength={1500} value={answer ?? review.payload.saved_answers?.authorization ?? ""} onChange={event => setAnswer(event.target.value)}/></label>
            <Button variant="outline" disabled={busy} type="submit">Save answer</Button>
          </form>}
          {provider === "manual" && editable.includes(app.status) && <form className="stack" onSubmit={async event => {
            event.preventDefault();
            if (!question.trim() || !answer?.trim()) return;
            const result = await mutate(appPath(id) + "/review", "PUT",
              {answers: {...review.payload.saved_answers, [question.trim()]: answer.trim()}}, "Manual handoff answer saved.");
            if (result) {setQuestion(""); setAnswer(undefined);}
          }}>
            <label>Screening question<input required maxLength={120} value={question} onChange={event => setQuestion(event.target.value)}/></label>
            <label>Answer for manual handoff<textarea required maxLength={1500} value={answer ?? ""} onChange={event => setAnswer(event.target.value)}/></label>
            <Button type="submit" variant="outline" disabled={busy}>Save handoff answer</Button>
          </form>}
          {provider === "greenhouse" && editable.includes(app.status) && <p>Update supported contact fields in <Link className="text-link" to="/profile">Profile</Link>, then refresh preparation.</p>}
          {manual.includes(app.status) && !app.summary.simulation && review.payload.provider !== "mock" && <form className="stack" onSubmit={async event => {
            event.preventDefault();
            if (await decide("record_confirmation", "Employer confirmation recorded.", reference.trim())) setReference("");
          }}>
            <label>Employer confirmation reference<input value={reference} onChange={event => setReference(event.target.value)} required minLength={3} maxLength={175}/></label>
            <Button variant="outline" disabled={busy || reference.trim().length < 3} type="submit">Record external confirmation</Button>
          </form>}
          {tracking.includes(app.status) && <form className="inline" onSubmit={event => {
            event.preventDefault(); void decide(outcome, "Employer outcome recorded.");
          }}><label>Employer outcome<select value={outcome} onChange={event => setOutcome(event.target.value)}>
            <option value="interview">Interview</option><option value="offer">Offer</option>
            <option value="employer_rejection">Rejected</option><option value="closed">Closed</option>
          </select></label><Button variant="outline" disabled={busy} type="submit">Save outcome</Button></form>}
        </Panel>
        <Panel title="Submission evidence">
          <Details values={{ evidence: evidence(app), confirmation: app.confirmation, "confirmed at": date(app.summary.confirmed_at),
            "task status": review.task ? label(review.task.status) : undefined,
            "task result": review.task?.result, "submission provider": review.task?.provider,
            "approved at": date(review.task?.approved_at), "last attempt": date(review.task?.attempted_at),
            "task completed": date(review.task?.finished_at), "preflight attempts": review.task?.preflight_attempts }}/>
        </Panel>
        <Panel title="Application timeline">
          <ErrorNotice message={eventError}/>{!events && !eventError && <Loading/>}
          {events?.length ? <ul className="entries">{events.map((event, index) => <li key={event.created + index}><div><strong>{label(event.status)}</strong><small>{event.message}</small></div><small>{date(event.created)}</small></li>)}</ul> : events && <Empty>No timeline events recorded.</Empty>}
        </Panel>
        {review.readiness_details && <Readiness value={review.readiness_details}/>}
        <MatchDetails job={review.job}/>
        <Panel title="Original job description"><p className="preserve">{review.original_description ?? review.job.description ?? "No description was saved."}</p></Panel>
        {toggle && review.payload_hash && (selected || rejectable.includes(app.status)) && <Button
            variant="outline" disabled={busy}
            onClick={() => toggle(review)}>{selected?.payload_hash === review.payload_hash ? "Remove from bulk review" : "Select reviewed application"}</Button>}
        {originalLink && <a className="text-link" href={originalLink} target="_blank" rel="noreferrer">Open original job <ArrowUpRight size={14}/></a>}
      </>}
    </Modal>
    {rejecting && <Modal title="Reject application" close={() => setRejecting(false)}>
      <form className="stack" onSubmit={async event => {
        event.preventDefault();
        const result = await mutate(appPath(id) + "/decision", "POST",
          {action: "reject", reason: reason || null, block_company: block, exclude_senior: reason === "too_senior" && excludeSenior}, "Application rejected.");
        if (result) {setRejecting(false); close();}
      }}>
        <label>Rejection reason<select value={reason} onChange={event => setReason(event.target.value)}>
          <option value="">Choose a reason</option>{Object.entries(reasons).map(([key, name]) => <option key={key} value={key}>{name}</option>)}
        </select></label>
        <label className="check"><input type="checkbox" checked={block} onChange={event => setBlock(event.target.checked)}/> Never recommend this company</label>
        {reason === "too_senior" && <label className="check"><input type="checkbox" checked={excludeSenior} onChange={event => setExcludeSenior(event.target.checked)}/> Exclude senior roles in my preferences</label>}
        <Button type="submit" disabled={busy}>Confirm rejection</Button>
      </form>
    </Modal>}
  </>;
}

const copy = {
  pipeline: ["Application pipeline", "See where each saved opportunity stands, from discovery through employer outcomes."],
  approvals: ["Approval queue", "Review an exact prepared application and its documents before giving final approval."],
  exceptions: ["Exception queue", "Investigate blocked preparations, failed tasks, and submissions that need verification."],
  history: ["Application history", "Find application records, their exact resume versions, and any recorded receipts."],
};

export function Pipeline({ mode, ...props }: PageProps & { mode: keyof typeof copy }) {
  const { state, mutate, busy } = props;
  const [params, setParams] = useSearchParams();
  const [reviews, setReviews] = useState<Review[]>([]);
  const [batch, setBatch] = useState<"approve" | "reject">();
  const [queueFilter, setQueueFilter] = useState<keyof typeof queueFilters>("ready");
  const [queueSort, setQueueSort] = useState<keyof typeof queueSorts>("recommended");
  const [layout, setLayout] = useState("board");
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [page, setPage] = useState(1);
  const [title, description] = copy[mode];
  const approvalQueue = mode === "approvals";
  const preferred = new Set(Array.isArray(state.profile.preferences.priority_companies) ?
    state.profile.preferences.priority_companies.map(company => company.toLowerCase()) : []);
  function recommended(a: Job, b: Job) {
    return Number(b.available && b.match.eligibility === "ELIGIBLE") - Number(a.available && a.match.eligibility === "ELIGIBLE")
      || compareJobs(a, b, "score")
      || Number(preferred.has(b.company.toLowerCase())) - Number(preferred.has(a.company.toLowerCase()))
      || compareJobs(a, b, "posted")
      || compareJobs(a, b, "expiring")
      || compareJobs(a, b, "discovered");
  }
  const canDispatch = (app?: Application) => Boolean(app && app.review_status === "READY_FOR_REVIEW" && !app.summary.missing?.length
    && (app.submission_method === "mock" || (app.submission_method === "greenhouse" && state.authorized_board && !state.options.dry_run)));
  function toggleReview(review: Review) {
    setReviews(previous => {
      const selected = previous.find(item => item.application.id === review.application.id);
      const remaining = previous.filter(item => item.application.id !== review.application.id);
      return selected?.payload_hash === review.payload_hash ? remaining : [...remaining, review];
    });
  }
  const jobs = new Map(state.jobs.map(job => [job.id, job]));
  const applications = new Map(state.applications.map(app => [app.job_id, app]));
  const rows = state.jobs.map(job => ({job, app: applications.get(job.id)})).filter(({job, app}) => {
    if (approvalQueue && (!app || !matchesQueue(app, queueFilter, canDispatch(app)))) return false;
    if (mode === "history" && !app) return false;
    if (mode === "exceptions" && !isJobException(job) && (!app || !isApplicationException(app))) return false;
    if (params.get("evidence") === "verified" && (!app || evidence(app) !== "Provider verification")) return false;
    const day = (app?.created ?? job.created).slice(0, 10);
    return (!status || stage(job, app) === status) && (!start || day >= start) && (!end || day <= end) &&
      searchMatch(query, job.role, job.company, app?.confirmation ?? undefined);
  }).sort((a, b) => approvalQueue ? (queueSort === "recommended" ? recommended(a.job, b.job) : compareJobs(a.job, b.job, queueSort)) : (b.app?.created ?? b.job.created).localeCompare(a.app?.created ?? a.job.created));
  const pages = Math.max(1, Math.ceil(rows.length / 25));
  const currentPage = Math.min(page, pages);
  function select(key: "app" | "job", id?: string) {
    const next = new URLSearchParams(params);
    next.delete("app"); next.delete("job");
    if (id) next.set(key, id);
    setParams(next);
  }
  const applicationId = params.get("app");
  const jobId = params.get("job");
  return <>
    <Heading title={title} description={description}>
      {mode === "pipeline" && <><Button variant={layout === "board" ? "secondary" : "outline"} aria-pressed={layout === "board"} onClick={() => setLayout("board")}><Columns3 size={16}/> Board</Button>
        <Button variant={layout === "table" ? "secondary" : "outline"} aria-pressed={layout === "table"} onClick={() => setLayout("table")}><List size={16}/> Table</Button></>}
    </Heading>
    <Panel title="">
      <div className="toolbar">
        <label>Search<input type="search" value={query} placeholder="Role, company, receipt" onChange={event => {setQuery(event.target.value); setPage(1);}}/></label>
        <label>Stage<select value={status} onChange={event => {setStatus(event.target.value); setPage(1);}}><option value="">All stages</option>
          {stages.map(item => <option key={item}>{item}</option>)}</select></label>
        {approvalQueue && <>
          <label>Filter applications<select value={queueFilter} onChange={event => {setQueueFilter(event.target.value as keyof typeof queueFilters); setPage(1);}}>
            {Object.entries(queueFilters).map(([key, value]) => <option key={key} value={key}>{value}</option>)}</select></label>
          <label>Sort applications<select value={queueSort} onChange={event => {setQueueSort(event.target.value as keyof typeof queueSorts); setPage(1);}}>
            {Object.entries(queueSorts).map(([key, value]) => <option key={key} value={key}>{value}</option>)}</select></label>
        </>}
        {mode === "history" && <><label>From (UTC)<input type="date" value={start} max={end || undefined} onChange={event => {setStart(event.target.value); setPage(1);}}/></label>
          <label>To (UTC)<input type="date" value={end} min={start || undefined} onChange={event => {setEnd(event.target.value); setPage(1);}}/></label>
          {params.get("evidence") === "verified" && <Button asChild variant="outline"><Link to="/history">Show all receipts</Link></Button>}</>}
      </div>
      {approvalQueue && reviews.length > 0 && <div className="toolbar">
        <span>{reviews.length} reviewed and selected</span>
        <Button variant="outline" disabled={busy || reviews.some(review => !review.approvable)} onClick={() => setBatch("approve")}>Review selected submissions</Button>
        <Button variant="outline" disabled={busy || reviews.some(review => !rejectable.includes(review.application.status))} onClick={() => setBatch("reject")}>Reject selected</Button>
        <Button variant="ghost" onClick={() => setReviews([])}>Clear selection</Button>
      </div>}
      {!rows.length ? <Empty>{mode === "exceptions" ? "No matching exceptions." : mode === "approvals" ? "No applications are waiting in this review queue." : "No matching records."}</Empty>
        : mode === "pipeline" && layout === "board" ? <div className="kanban board">
          {stages.filter(name => !status || status === name).map(name => {
            const cards = rows.filter(({job, app}) => stage(job, app) === name);
            return <section className="kanban-column" key={name}><h2 className="kanban-heading">{name}<span>{cards.length}</span></h2>
              <div className="kanban-cards">{cards.map(({job, app}) => <button key={job.id} className="kanban-card" onClick={() => app ? select("app", app.id) : select("job", job.id)}>
                <strong>{job.role}</strong><span>{job.company}</span>{app && <span>{label(app.review_status)}</span>}
              </button>)}</div></section>;
          })}
        </div> : <>
        <div className="table-wrap"><table className="data-table responsive-table" role="table"><thead><tr><th>Role</th><th>Current status</th>{approvalQueue && <th>Match</th>}<th>Created</th><th>{mode === "exceptions" ? "Issue" : "Evidence"}</th>{mode === "exceptions" && <th>Retry</th>}</tr></thead>
          <tbody>{rows.slice((currentPage - 1) * 25, currentPage * 25).map(({job, app}) => <tr key={job.id}>
            <td><button className="flat-button" onClick={() => app ? select("app", app.id) : select("job", job.id)}><Company job={job}/></button></td>
            <td data-label="Current status"><Status value={app?.review_status ?? job.automation.state ?? job.status}/></td>
            {approvalQueue && <td data-label="Match">{job.match.match_score == null ? "—" : job.match.match_score + "%"}</td>}
            <td data-label="Created">{date(app?.created ?? job.created)}{queueSort === "expiring" && job.available && Date.parse(job.deadline ?? "") > Date.now() && <small className="row-note">Deadline {date(job.deadline)}</small>}</td>
            <td data-label={mode === "exceptions" ? "Issue" : "Evidence"}>{mode === "exceptions" ? app?.summary.missing?.join(", ") || job.automation.reason || app?.summary.exception || app?.summary.reason || label(app?.review_status ?? job.automation.state)
              : app ? evidence(app) : "—"}</td>
            {mode === "exceptions" && <td data-label="Retry">{isJobException(job) && <Button variant="outline" size="sm" disabled={busy} onClick={() => void mutate(jobPath(job.id) + "/retry", "POST", undefined, "Internal retry budget reset.")}>Retry preparation</Button>}</td>}
          </tr>)}</tbody></table></div>
        {pages > 1 && <div className="pagination"><span>Page {currentPage} of {pages}</span><Button size="sm" variant="outline" disabled={currentPage <= 1} onClick={() => setPage(currentPage - 1)}>Previous</Button>
          <Button size="sm" variant="outline" disabled={currentPage >= pages} onClick={() => setPage(currentPage + 1)}>Next</Button></div>}
      </>}
    </Panel>
    {applicationId && <ReviewDrawer key={applicationId} id={applicationId} {...props} toggle={approvalQueue ? toggleReview : undefined} selected={reviews.find(item => item.application.id === applicationId)} close={() => select("app")}/>}
    {batch && <ReviewBatch action={batch} reviews={reviews} busy={busy} mutate={mutate} close={() => setBatch(undefined)} complete={() => {setBatch(undefined); setReviews([]);}}/>}
    {jobId && jobs.has(jobId) && <JobDrawer {...props} id={jobId} close={() => select("job")}/>}
  </>;
}
