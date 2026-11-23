import { useState } from "react";
import { Activity, ArrowUpRight, Briefcase, CheckCircle2, ClipboardCheck, FileText, ListChecks, Play, Target } from "lucide-react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import type { Job, State } from "../api";
import { awaitsReview, date, evidence, initials, label, stage, stages } from "../domain";
import { Empty, Heading, Panel, Status } from "../shared";
import type { PageProps } from "../shared";

export function Company({ job }: { job: Job }) {
  return <div className="company-lockup"><span className="company-mark">{initials(job.company)}</span>
    <div className="company-copy"><strong>{job.role}</strong><span>{job.company}{job.location ? " · " + job.location : ""}</span></div></div>;
}

export function Distribution({ rows }: { rows: { name: string; count: number }[] }) {
  if (!rows.some(row => row.count)) return <Empty>No activity in this view.</Empty>;
  const max = Math.max(...rows.map(row => row.count));
  return <ul className="chart-bars">{rows.map(row => <li key={row.name}>
    <span>{row.name}</span><svg viewBox="0 0 100 5" preserveAspectRatio="none" aria-hidden="true">
      <rect className="bar-track" width="100" height="5" rx="1"/><rect className="bar-fill" width={row.count / max * 100} height="5" rx="1"/>
    </svg><strong>{row.count}</strong>
  </li>)}</ul>;
}

export function pipelineCounts(state: State) {
  const applications = new Map(state.applications.map(item => [item.job_id, item]));
  const stagesByJob = state.jobs.map(job => stage(job, applications.get(job.id)));
  return stages.map(name => ({ name, count: stagesByJob.filter(current => current === name).length }));
}

function dailyTrend(state: State, take = 7) {
  const day = new Intl.DateTimeFormat("en-CA", { timeZone: state.options.timezone, year: "numeric", month: "2-digit", day: "2-digit" });
  const days = Array.from({ length: take }, (_, index) => day.format(new Date(Date.now() - (take - 1 - index) * 86400000)));
  return days.map(name => ({
    name,
    jobs: state.jobs.filter(row => day.format(new Date(row.created)) === name).length,
    applications: state.applications.filter(row => day.format(new Date(row.created)) === name).length,
  }));
}

export function Overview({ state, mutate, busy }: PageProps) {
  const qualified = state.jobs.filter(job => job.match.recommendation === "PREPARE_APPLICATION");
  const verified = state.applications.filter(app => app.confirmation && !app.summary.simulation && !app.summary.external_confirmation);
  const metrics = [
    { name: "Jobs discovered", value: state.jobs.length, Icon: Briefcase, to: "/jobs", note: "Saved postings" },
    { name: "Qualified matches", value: qualified.length, Icon: Target, to: "/jobs?qualified=true", note: "Meet your match threshold" },
    { name: "Resumes generated", value: state.resume_count, Icon: FileText, to: "/resume-studio", note: "Compiled versions" },
    { name: "Applications prepared", value: state.applications.length, Icon: ClipboardCheck, to: "/pipeline", note: "Saved application records" },
    { name: "Verified submissions", value: verified.length, Icon: CheckCircle2, to: "/history?evidence=verified", note: "Provider receipts" },
    { name: "Awaiting human review", value: state.applications.filter(awaitsReview).length, Icon: ListChecks, to: "/approvals", note: "Review queue" },
  ];
  const recommendations = [...qualified].filter(job => job.available && !["SKIPPED", "CLOSED"].includes(job.status))
    .sort((a, b) => (b.match.match_score ?? 0) - (a.match.match_score ?? 0)).slice(0, 5);
  const trend = dailyTrend(state);
  const priority = new Set(Array.isArray(state.profile.preferences.priority_companies) ?
    state.profile.preferences.priority_companies.map(company => company.toLowerCase()) : []);
  const hiring = [...new Set(state.jobs.filter(job => job.available && job.source !== "mock" &&
    priority.has(job.company.toLowerCase())).map(job => job.company))];
  const newThisHour = state.jobs.filter(job => job.source !== "mock" && Date.parse(job.created) >= Date.now() - 3600000).length;
  const localDay = new Intl.DateTimeFormat("en-CA", {timeZone: state.options.timezone, year: "numeric", month: "2-digit", day: "2-digit"});
  const today = localDay.format(new Date());
  const todaysMatches = qualified.filter(job => job.available && job.source !== "mock" &&
    !["SKIPPED", "CLOSED"].includes(job.status) && Number.isFinite(Date.parse(job.created)) &&
    localDay.format(new Date(job.created)) === today)
    .sort((left, right) => (right.match.match_score ?? 0) - (left.match.match_score ?? 0)).slice(0, 5);
  const jobById = new Map(state.jobs.map(job => [job.id, job]));
  const realApplications = state.applications.filter(app => !app.summary.simulation && jobById.get(app.job_id)?.source !== "mock");
  return <>
    <Heading title="Overview" description="Track your job search, application activity, and automation in one place.">
      <Button disabled={busy || state.worker.pending > 0} onClick={() => void mutate("/api/runs", "POST", undefined, "Automation run queued.")}><Play size={15}/> Run now</Button>
    </Heading>
    <section className="metric-grid" aria-label="Key metrics">{metrics.map(({ name, value, Icon, to, note }) =>
      <Link className="metric-card" key={name} to={to}><div className="metric-top"><span>{name}</span><Icon size={17}/></div>
        <strong className="metric-value">{value}</strong><span className="metric-note">{note}</span></Link>
    )}</section>
    {!state.profile_readiness.ready && <p><Link className="text-link" to="/activation">Complete real-world activation</Link></p>}
    {!state.options.sources.some(source => source.enabled && source.provider !== "mock") && <p><Link className="text-link" to="/activation">Verify and enable employer boards</Link></p>}
    <div className="dashboard-grid">
      <Panel title="Career activity" caption="Current counts from saved records">
        <dl className="details">
          <div><dt>New jobs this hour</dt><dd>{newThisHour}</dd></div>
          <div><dt>Priority companies hiring</dt><dd>{hiring.length ? hiring.join(", ") : "None in the current listings"}</dd></div>
          <div><dt>Resumes compiled today</dt><dd>{state.daily.compiled}</dd></div>
          <div><dt>Real applications ready for review</dt><dd>{realApplications.filter(app => app.review_status === "READY_FOR_REVIEW").length}</dd></div>
          <div><dt>Real submissions with confirmation</dt><dd>{realApplications.filter(app => app.confirmation).length}</dd></div>
          <div><dt>Applications requiring information</dt><dd>{state.applications.filter(app => app.summary.missing?.length).length}</dd></div>
          <div><dt>Employer responses recorded</dt><dd>{state.applications.filter(app => ["INTERVIEW", "OFFER", "REJECTED"].includes(app.status)).length}</dd></div>
          <div><dt>Interview opportunities</dt><dd>{state.applications.filter(app => app.status === "INTERVIEW").length}</dd></div>
        </dl>
      </Panel>
      <Panel title="Best matches today" caption="Qualified real postings first saved today">
        {todaysMatches.length ? <div className="match-list">{todaysMatches.map(job =>
          <Link className="match-row" key={job.id} to={"/intelligence?job=" + job.id}><Company job={job}/><span className="score-pill">{job.match.match_score}%</span></Link>
        )}</div> : <Empty>No qualified real postings have been saved today.</Empty>}
      </Panel>
      <Panel title="Application trend" caption={"New application records by day · " + state.options.timezone}>
        <Distribution rows={trend.map(row => ({ name: row.name.slice(5), count: row.applications }))}/>
      </Panel>
      <Panel title="Recommended jobs" caption="Available roles that meet your matching criteria">
        {recommendations.length ? <div className="match-list">{recommendations.map(job =>
          <Link key={job.id} to={"/jobs?job=" + job.id} className="match-row"><Company job={job}/><span className="score-pill">{job.match.match_score}%</span></Link>
        )}</div> : <Empty>Qualified roles will appear after discovery and evaluation.</Empty>}
        <Link className="text-link" to="/jobs">Browse jobs <ArrowUpRight size={14}/></Link>
      </Panel>
      <Panel title="Pipeline distribution"><Distribution rows={pipelineCounts(state)}/></Panel>
      <div className="content-grid">
        <Panel title="Automation">
          <p className="inline"><Activity size={16}/><Status value={state.worker.status} tone={state.worker.status === "RUNNING" ? "good" : "warn"}/></p>
          <p>Autonomous Preparation + Manual Final Approval</p>
          <p>Next run {date(state.next_run, state.options.timezone)} · {state.worker.pending} active or queued</p>
          <dl className="details">
            <div><dt>Discovered today</dt><dd>{state.daily.new_jobs}</dd></div>
            <div><dt>Eligible jobs</dt><dd>{state.jobs.filter(job => job.available && job.match.eligibility === "ELIGIBLE").length}</dd></div>
            <div><dt>Approved</dt><dd>{state.applications.filter(app => app.status === "APPROVED").length}</dd></div>
            <div><dt>Failed</dt><dd>{state.applications.filter(app => ["FAILED", "SUBMISSION_FAILED"].includes(app.review_status)).length}</dd></div>
            <div><dt>Needs manual action</dt><dd>{state.applications.filter(app => ["NEEDS_MANUAL_ACTION", "SUBMISSION_UNCERTAIN", "SUBMISSION_BLOCKED"].includes(app.review_status) || (app.submission_method === "manual" && awaitsReview(app))).length}</dd></div>
          </dl>
          <Link className="text-link" to="/automation">View automation <ArrowUpRight size={14}/></Link>
        </Panel>
        <Panel title="Recent activity">
          {state.logs.length ? <ul className="entries">{state.logs.slice(0, 4).map(item =>
            <li key={item.id}><div><strong>{item.message}</strong><small>{label(item.kind)}</small></div><small>{date(item.created, state.options.timezone)}</small></li>
          )}</ul> : <Empty>Run and application events will appear here.</Empty>}
        </Panel>
      </div>
    </div>
  </>;
}

export function Analytics({ state }: PageProps) {
  return <AnalyticsContent state={state}/>;
}

function AnalyticsContent({ state }: { state: State }) {
  const [range, setRange] = useState(30);
  const since = Date.now() - range * 86400000;
  const within = (value?: string | null) => !!value && Date.parse(value) >= since;
  const jobs = state.jobs.filter(job => within(job.created));
  const apps = state.applications.filter(app => within(app.created));
  const runs = state.runs.filter(run => within(run.finished));
  const verified = apps.filter(app => evidence(app) === "Provider verification").length;
  const sourceRows = [...new Set(jobs.map(job => job.source ?? "Unknown"))].map(name => ({
    name, count: jobs.filter(job => (job.source ?? "Unknown") === name).length,
  }));
  const errors = state.logs.filter(log => within(log.created) && /error|fail|exception/i.test(log.kind));
  const counts = [0, 20, 40, 60, 80].map(min => ({
    name: min + "–" + (min === 80 ? 100 : min + 19),
    count: jobs.filter(job => typeof job.match.match_score === "number" && job.match.match_score >= min && (min === 80 || job.match.match_score < min + 20)).length,
  }));
  return <>
    <Heading title="Analytics" description="Analyze saved postings, prepared applications, and recorded outcomes.">
      <label className="inline">Date range <select value={range} onChange={event => setRange(Number(event.target.value))}>
        <option value={7}>Last 7 days</option><option value={30}>Last 30 days</option><option value={90}>Last 90 days</option>
      </select></label>
    </Heading>
    <div className="split-grid">
      <Panel title="Discovery trend" caption="New postings per day · latest 14 days within the selected range">
        <Distribution rows={dailyTrend(state, Math.min(range, 14)).map(row => ({name: row.name.slice(5), count: row.jobs}))}/>
      </Panel>
      <Panel title="Match score distribution"><Distribution rows={counts}/></Panel>
      <Panel title="Preparation and conversion" caption="Application records created in this range and their current recorded outcomes">
        <Distribution rows={[
          { name: "Applications", count: apps.length }, { name: "Verified", count: verified },
          { name: "Interview", count: apps.filter(app => app.status === "INTERVIEW").length },
          { name: "Offer", count: apps.filter(app => app.status === "OFFER").length },
        ]}/>
        <p>{apps.length ? (verified / apps.length * 100).toFixed(1) + "% verified conversion" : "No applications in this range"}</p>
        <p className="subtle">{runs.reduce((sum, run) => sum + (run.report.compiled ?? 0), 0)} resumes compiled in available finished runs.</p>
      </Panel>
      <Panel title="Saved postings by source"><Distribution rows={sourceRows}/></Panel>
      <Panel title="Recent errors" caption="Based on available recent logs and run summaries">
        <Distribution rows={[
          { name: "Failed runs", count: runs.filter(run => run.status === "FAILED").length },
          { name: "Runs with errors", count: runs.filter(run => run.status === "COMPLETED_WITH_ERRORS").length },
          ...[...new Set(errors.map(item => item.kind))].map(name => ({ name: label(name), count: errors.filter(item => item.kind === name).length })),
        ]}/>
      </Panel>
    </div>
  </>;
}
