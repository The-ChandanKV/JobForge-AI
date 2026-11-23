import { Activity, CalendarClock, Clock3, Pause, Play } from "lucide-react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import type { Notice } from "../api";
import { date, isJobException, label } from "../domain";
import { Details, Empty, ErrorNotice, Heading, Loading, Panel, Status, useResource } from "../shared";
import type { PageProps } from "../shared";

const workflow = ["Discovery", "Filtering", "Eligibility", "Matching", "Resume tailoring", "Validation", "Application preparation", "Human review", "Submission verification"];
const stageForKind: Record<string, number> = {
  discovery: 0, filter: 1, eligibility: 2, matching: 3, resume: 4, validation: 5, application: 6, review: 7, submission: 8,
};

export function Automation({ state, mutate, busy }: PageProps) {
  const timezone = state.options.timezone;
  const running = state.runs.find(run => run.status === "RUNNING");
  const phase = running && state.logs.find(log => log.detail.run_id === running.id && stageForKind[log.kind] !== undefined);
  const preparing = state.applications.some(app => app.review_status === "PREPARING");
  const tailoring = state.jobs.some(job => job.automation.state === "STARTED");
  const current = preparing ? stageForKind.application : running && tailoring ? stageForKind.resume : phase ? stageForKind[phase.kind] : undefined;
  const retries = state.jobs.filter(isJobException);
  return <>
    <Heading title="Automation center" description="Monitor worker health, job preparation, retries, and scheduled activity.">
      <Button variant="outline" disabled={busy} onClick={() => void mutate("/api/settings", "PUT", {...state.options, enabled: !state.options.enabled}, state.options.enabled ? "Scheduled automation paused." : "Scheduled automation resumed.")}>
        {state.options.enabled ? <Pause size={16}/> : <Play size={16}/>} {state.options.enabled ? "Pause schedule" : "Resume schedule"}</Button>
      <Button disabled={busy || state.worker.pending > 0} onClick={() => void mutate("/api/runs", "POST", undefined, "Automation run queued.")}><Play size={16}/> Run now</Button>
    </Heading>
    <div className="split-grid studio-top">
      <Panel title="Worker" caption={timezone}>
        <p>Autonomous Preparation + Manual Final Approval</p>
        <div className="inline"><Activity size={17}/><Status value={state.worker.status} tone={state.worker.status === "RUNNING" ? "good" : "warn"}/></div>
        <Details values={{ "current stage": current !== undefined ? workflow[current] : running ? "Run active" : "Idle",
          "last heartbeat": date(state.worker.last_heartbeat, timezone), "last success": date(state.worker.last_success, timezone), "queued or running": state.worker.pending, "internal retries or exceptions": retries.length }}/>
      </Panel>
      <Panel title="Today’s automation" caption={timezone}>
        <p className="inline"><CalendarClock size={17}/> Next scheduled execution {date(state.next_run, timezone)}</p>
        <Details values={{ "jobs discovered": state.daily.new_jobs, "jobs scanned": state.daily.scanned, "jobs filtered": state.daily.filtered,
          "resumes compiled": state.daily.compiled, "applications prepared": state.daily.prepared, "failed runs": state.daily.failed_runs }}/>
        <Link className="text-link" to="/settings">Manage automation settings</Link>
      </Panel>
    </div>
    <div className="content-grid">
      <Panel title="Preparation workflow">
        <ol className="workflow" aria-label="Automation steps">{workflow.map((name, index) =>
          <li key={name} className={"workflow-step " + (index === current ? "current" : "")}><span className="workflow-node"><Clock3 size={14}/></span><span>{name}</span></li>)}</ol>
      </Panel>
      <Panel title="Recent runs">
        {state.runs.length ? <div className="table-wrap"><table className="data-table"><thead><tr><th>Created</th><th>Trigger</th><th>Status</th><th>Attempts</th><th>Scanned</th><th>Prepared</th><th>Action</th></tr></thead>
          <tbody>{state.runs.map(run => <tr key={run.id}><td>{date(run.created, timezone)}</td><td>{label(run.trigger)}</td>
            <td><Status value={run.status}/>{run.report.error && <small className="row-note">{run.report.error}</small>}</td>
            <td>{run.attempts}</td><td>{run.report.scanned ?? "—"}</td><td>{run.report.prepared ?? "—"}</td>
            <td>{!run.canceled && ["QUEUED", "RUNNING"].includes(run.status) && <Button variant="outline" size="sm" disabled={busy} onClick={() => void mutate("/api/runs/" + run.id + "/cancel", "POST", undefined, "Cancellation requested.")}>Cancel</Button>}</td></tr>)}</tbody></table></div>
          : <Empty>No worker runs recorded.</Empty>}
      </Panel>
      <Panel title="Retry checkpoints">
        {retries.length ? <ul className="entries">{retries.map(job => <li key={job.id}><div><Link className="text-link" to={"/exceptions?job=" + job.id}>{job.role} · {job.company}</Link><small>{job.automation.reason ?? label(job.automation.state)}</small></div>
          <small>{job.automation.attempts ?? 0} attempts · {date(job.automation.next_retry, timezone)}</small></li>)}</ul> : <Empty>No job retry checkpoints.</Empty>}
      </Panel>
      <Panel title="Execution logs">
        {state.logs.length ? <ul className="entries">{state.logs.map(log => <li key={log.id}><div><strong>{log.message}</strong><small>{label(log.kind)}</small>
          {Object.keys(log.detail).length > 0 && <details><summary>Details</summary><Details values={log.detail}/></details>}</div><small>{date(log.created, timezone)}</small></li>)}</ul> : <Empty>No logs recorded.</Empty>}
      </Panel>
    </div>
  </>;
}

export function Notifications({ mutate, revision, busy, state }: PageProps) {
  const { data, error } = useResource<Notice[]>("/api/notifications", revision);
  return <>
    <Heading title="Notifications" description="Review persisted alerts from automation and the application workflow.">
      <Button variant="outline" disabled={busy || !state.unread_notifications} onClick={() => void mutate("/api/notifications/read", "POST", undefined, "Notifications marked as read.")}>Mark all as read</Button>
    </Heading>
    <Panel title="Inbox">
      <ErrorNotice message={error}/>{!data && !error && <Loading/>}
      {data?.length ? <ul className="entries">{data.map(item => <li key={item.id}><div><strong>{item.message}</strong><small>{label(item.kind)}{item.kind !== "daily_summary" ? " · " + item.count + " events" : ""}</small>
        <Link className="text-link" to={item.kind === "ready" ? "/approvals" : item.kind === "daily_summary" ? "/analytics" : "/history"}>
          {item.kind === "ready" ? "Open approval queue" : item.kind === "daily_summary" ? "Open analytics" : "Open application history"}
        </Link></div>
        <div className="inline">{!item.read && <Status value="Unread" tone="warn"/>}<small>{date(item.created, state.options.timezone)}</small></div></li>)}</ul> : data && <Empty>You have no notifications.</Empty>}
    </Panel>
  </>;
}
