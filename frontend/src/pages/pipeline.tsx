import { useState } from "react";
import { ArrowUpRight, Columns3, List, ShieldCheck } from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { appPath, jobPath, officialUrl, resumeUrl } from "../api";
import type { Event, Review } from "../api";
import { awaitsReview, date, evidence, isApplicationException, isJobException, label, searchMatch, stage, stages } from "../domain";
import { Details, Empty, ErrorNotice, Heading, Loading, Modal, Panel, Status, useResource } from "../shared";
import type { PageProps } from "../shared";
import { JobDrawer, MatchDetails } from "./jobs";
import { Company } from "./overview";

const editable = ["APPLICATION_PREPARED", "READY_FOR_REVIEW", "NEEDS_REVIEW", "NEEDS_MANUAL_ACTION", "APPROVED", "FAILED"];
const manual = ["APPLICATION_PREPARED", "READY_FOR_REVIEW", "NEEDS_MANUAL_ACTION", "APPROVED", "SUBMISSION_UNCERTAIN"];
const tracking = ["APPROVED", "SUBMITTED", "INTERVIEW", "OFFER"];

function ReviewDrawer({ id, close, mutate, revision, busy }: Pick<PageProps, "mutate" | "revision" | "busy"> & { id: string; close: () => void }) {
  const { data: review, error } = useResource<Review>(appPath(id) + "/review", revision);
  const { data: events, error: eventError } = useResource<Event[]>(appPath(id) + "/events", revision);
  const [confirmation, setConfirmation] = useState<Review>();
  const [answer, setAnswer] = useState<string>();
  const [reference, setReference] = useState("");
  const [outcome, setOutcome] = useState("interview");
  const app = review?.application;
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
            provider: review.payload.provider, destination: review.payload.destination,
            "prepared at": date(review.payload.prepared_at), "resume version": review.resume.id,
            template: label(review.resume.template), "payload hash": review.payload_hash,
          }}/>
          <div className="inline">
            <a className="text-link" href={resumeUrl(review.resume.id)} target="_blank" rel="noreferrer">Preview PDF <ArrowUpRight size={14}/></a>
            <a className="text-link" href={resumeUrl(review.resume.id, "pdf", true)}>Download PDF</a>
            <a className="text-link" href={resumeUrl(review.resume.id, "tex", true)}>Download LaTeX</a>
          </div>
          {review.payload.fields && <details open><summary>Exact form fields</summary><Details values={review.payload.fields}/></details>}
          {!!Object.keys(review.payload.saved_answers ?? {}).length && <details open><summary>Saved answers</summary><Details values={review.payload.saved_answers ?? {}}/></details>}
          <details><summary>Cover letter</summary><p className="preserve">{review.payload.cover_letter || "No cover letter is saved on this version."}</p></details>
          {!!review.payload.pending?.length && <ul className="bullets">{review.payload.pending.map((item, index) => <li key={index}>{item}</li>)}</ul>}
          <ErrorNotice message={review.refusal ?? undefined}/>
          {review.approvable && review.payload_hash && <Button disabled={busy} onClick={() => setConfirmation(review)}><ShieldCheck size={16}/> Approve &amp; submit</Button>}
          {review.approvable && review.payload.provider === "mock" && <p className="subtle">This destination is a local submission simulation.</p>}
        </Panel>
        <Panel title="Review actions">
          <div className="inline">
            {editable.includes(app.status) && <>
              <Button variant="outline" disabled={busy} onClick={() => void mutate(appPath(id) + "/review", "PUT", {}, "Application preparation refreshed.")}>Refresh preparation</Button>
              <Button variant="outline" disabled={busy} onClick={() => {
                if (window.confirm("Reject this prepared application?")) void decide("reject", "Application rejected.");
              }}>Reject</Button>
            </>}
            {app.status === "SUBMISSION_UNCERTAIN" && <Button variant="outline" disabled={busy} onClick={() => void decide("reconcile", "Reconciliation checked. Review the current receipt status.")}>Check receipt</Button>}
            <Link className="text-link" to={"/resume-studio?job=" + review.job.id}>Open resume studio <ArrowUpRight size={14}/></Link>
          </div>
          {review.payload.provider === "mock" && editable.includes(app.status) && <form className="stack" onSubmit={event => {
            event.preventDefault();
            void mutate(appPath(id) + "/review", "PUT", {answers: {authorization: answer ?? review.payload.saved_answers?.authorization ?? ""}}, "Screening answer saved. Review the refreshed version before approving.");
          }}>
            <label>Mock screening answer · work authorization<input required maxLength={1500} value={answer ?? review.payload.saved_answers?.authorization ?? ""} onChange={event => setAnswer(event.target.value)}/></label>
            <Button variant="outline" disabled={busy} type="submit">Save answer</Button>
          </form>}
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
            "task result": review.task?.result, "last attempt": date(review.task?.attempted_at) }}/>
        </Panel>
        <Panel title="Application timeline">
          <ErrorNotice message={eventError}/>{!events && !eventError && <Loading/>}
          {events?.length ? <ul className="entries">{events.map((event, index) => <li key={event.created + index}><div><strong>{label(event.status)}</strong><small>{event.message}</small></div><small>{date(event.created)}</small></li>)}</ul> : events && <Empty>No timeline events recorded.</Empty>}
        </Panel>
        <MatchDetails job={review.job}/>
        {review.original_description && <Panel title="Original job description"><p className="preserve">{review.original_description}</p></Panel>}
        {officialUrl(review.job.apply_url) && <a className="text-link" href={officialUrl(review.job.apply_url)} target="_blank" rel="noreferrer">Open employer application <ArrowUpRight size={14}/></a>}
      </>}
    </Modal>
    {confirmation && <Modal title="Confirm final approval" close={() => setConfirmation(undefined)}>
      <p>{confirmation.payload.provider === "mock" && <strong>Local simulation. </strong>}Approve the exact prepared application for <strong>{confirmation.job.role}</strong> at <strong>{confirmation.job.company}</strong>. This queues work for the existing submission worker.</p>
      <Details values={{ destination: confirmation.payload.destination, "resume version": confirmation.resume.id, "payload hash": confirmation.payload_hash }}/>
      <Button disabled={busy || !confirmation.payload_hash} onClick={async () => {
        const result = await mutate(appPath(id) + "/approve-submit", "POST",
          {application_id: id, payload_hash: confirmation.payload_hash}, "Final approval recorded. Submission is queued for verification.");
        if (result) setConfirmation(undefined);
      }}>Confirm approval and queue submission</Button>
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
  const [layout, setLayout] = useState("board");
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [page, setPage] = useState(1);
  const [title, description] = copy[mode];
  const jobs = new Map(state.jobs.map(job => [job.id, job]));
  const applications = new Map(state.applications.map(app => [app.job_id, app]));
  const rows = state.jobs.map(job => ({job, app: applications.get(job.id)})).filter(({job, app}) => {
    if (mode === "approvals" && (!app || !awaitsReview(app))) return false;
    if (mode === "history" && !app) return false;
    if (mode === "exceptions" && !isJobException(job) && (!app || !isApplicationException(app))) return false;
    if (params.get("evidence") === "verified" && (!app || evidence(app) !== "Provider verification")) return false;
    const day = (app?.created ?? job.created).slice(0, 10);
    return (!status || stage(job, app) === status) && (!start || day >= start) && (!end || day <= end) &&
      searchMatch(query, job.role, job.company, app?.confirmation ?? undefined);
  }).sort((a, b) => (b.app?.created ?? b.job.created).localeCompare(a.app?.created ?? a.job.created));
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
        {mode === "history" && <><label>From (UTC)<input type="date" value={start} max={end || undefined} onChange={event => {setStart(event.target.value); setPage(1);}}/></label>
          <label>To (UTC)<input type="date" value={end} min={start || undefined} onChange={event => {setEnd(event.target.value); setPage(1);}}/></label>
          {params.get("evidence") === "verified" && <Button asChild variant="outline"><Link to="/history">Show all receipts</Link></Button>}</>}
      </div>
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
        <div className="table-wrap"><table className="data-table responsive-table" role="table"><thead><tr><th>Role</th><th>Current status</th><th>Created</th><th>{mode === "exceptions" ? "Issue" : "Evidence"}</th>{mode === "exceptions" && <th>Retry</th>}</tr></thead>
          <tbody>{rows.slice((currentPage - 1) * 25, currentPage * 25).map(({job, app}) => <tr key={job.id}>
            <td><button className="flat-button" onClick={() => app ? select("app", app.id) : select("job", job.id)}><Company job={job}/></button></td>
            <td data-label="Current status"><Status value={app?.review_status ?? job.automation.state ?? job.status}/></td>
            <td data-label="Created">{date(app?.created ?? job.created)}</td>
            <td data-label={mode === "exceptions" ? "Issue" : "Evidence"}>{mode === "exceptions" ? app?.summary.missing?.join(", ") || job.automation.reason || app?.summary.reason || label(app?.review_status ?? job.automation.state)
              : app ? evidence(app) : "—"}</td>
            {mode === "exceptions" && <td data-label="Retry">{isJobException(job) && <Button variant="outline" size="sm" disabled={busy} onClick={() => void mutate(jobPath(job.id) + "/retry", "POST", undefined, "Internal retry budget reset.")}>Retry preparation</Button>}</td>}
          </tr>)}</tbody></table></div>
        {pages > 1 && <div className="pagination"><span>Page {currentPage} of {pages}</span><Button size="sm" variant="outline" disabled={currentPage <= 1} onClick={() => setPage(currentPage - 1)}>Previous</Button>
          <Button size="sm" variant="outline" disabled={currentPage >= pages} onClick={() => setPage(currentPage + 1)}>Next</Button></div>}
      </>}
    </Panel>
    {applicationId && <ReviewDrawer key={applicationId} id={applicationId} {...props} close={() => select("app")}/>}
    {jobId && jobs.has(jobId) && <JobDrawer {...props} id={jobId} close={() => select("job")}/>}
  </>;
}
