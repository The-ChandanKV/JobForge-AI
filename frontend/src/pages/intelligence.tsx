import { Link, useSearchParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { jobPath, officialUrl, resumeUrl } from "../api";
import type { Job, ReadinessSummary } from "../api";
import { date, label } from "../domain";
import { Details, Empty, ErrorNotice, Heading, Loading, Panel, Status, useResource } from "../shared";
import type { PageProps } from "../shared";
import { MatchDetails } from "./jobs";

const feedbackOptions = {
  good: "Good recommendation", bad: "Bad recommendation",
  not_interested: "Not interested", already_applied: "Already applied", wrong_level: "Wrong experience level",
};

type Intelligence = {
  job: Job;
  readiness: ReadinessSummary;
  sources: {key: string; canonical_url: string | null; verified: string; available: boolean}[];
  resume: {id: string; template: string; created: string} | null;
  application_id: string | null;
  feedback: string | null;
};

export function Readiness({ value }: { value: ReadinessSummary }) {
  return <Panel title="Application readiness">
    <Status value={value.category}/>
    <p>{value.verified_checks} of {value.total_checks} checks verified</p>
    <Details values={Object.fromEntries(Object.entries(value.checks).map(([key, result]) =>
      [key, result == null ? "Unknown" : result ? "Verified" : "Not established"]))}/>
    {!!value.pending.length && <p>Pending · {value.pending.join(", ")}</p>}
  </Panel>;
}

export function JobIntelligence({ state, revision, busy, mutate }: PageProps) {
  const [params, setParams] = useSearchParams();
  const selected = params.get("job") ?? "";
  const {data, error} = useResource<Intelligence>(selected ? jobPath(selected) + "/intelligence" : null, revision);
  const original = officialUrl(data?.job.url);
  return <>
    <Heading title="Job Intelligence" description="Review the opening, matching evidence, and what is still needed for an application."/>
    <Panel title="Choose an opening">
      <label>Job<select value={selected} onChange={event => setParams(event.target.value ? {job: event.target.value} : {})}>
        <option value="">Select a saved job</option>{state.jobs.map(job => <option key={job.id} value={job.id}>
          {job.role} · {job.company}{job.source === "mock" ? " (synthetic)" : ""}
        </option>)}</select></label>
    </Panel>
    <ErrorNotice message={error}/>
    {selected && !data && !error && <Loading/>}
    {!selected && <Empty>Choose a posting to see the evidence used to evaluate it.</Empty>}
    {data && <div className="content-grid">
      <Panel title={data.job.role} caption={data.job.company + (data.job.source === "mock" ? " · Synthetic fixture" : "")}>
        <Details values={{ source: data.job.source, "last verified": date(data.job.verified),
          "posting date": date(data.job.posted), location: data.job.location,
          "semantic relevance (0–10)": data.job.match.semantic?.relevance, "current feedback": data.feedback ? label(data.feedback) : undefined }}/>
        <div className="inline">
          {original && <a className="text-link" href={original} target="_blank" rel="noreferrer">Open original job</a>}
          <Link className="text-link" to={"/resume-studio?job=" + data.job.id}>Tailor in Resume Studio</Link>
          {data.application_id && <Link className="text-link" to={"/approvals?app=" + data.application_id}>Open application review</Link>}
        </div>
      </Panel>
      <div className="split-grid">
        <MatchDetails job={data.job}/>
        <Readiness value={data.readiness}/>
      </div>
      <Panel title="Relevant projects">
        {data.job.match.relevant_projects?.length ? <ul className="bullets">{data.job.match.relevant_projects.map((project, index) =>
          <li key={index}>{project}</li>)}</ul> : <p>No matching verified project evidence.</p>}
      </Panel>
      <Panel title="Source evidence">
        {data.sources.map(item => <div key={item.key} className="inline">
          <span>{item.key} · {date(item.verified)}</span>
          <Status value={item.available ? "Available" : "Unavailable"}/>
          {officialUrl(item.canonical_url ?? undefined) && <a className="text-link" href={officialUrl(item.canonical_url ?? undefined)} target="_blank" rel="noreferrer">Source</a>}
        </div>)}
      </Panel>
      {data.resume && <Panel title="Tailored resume" caption={date(data.resume.created)}>
        <a className="text-link" href={resumeUrl(data.resume.id)} target="_blank" rel="noreferrer">Preview exact PDF</a>
        <a className="text-link" href={resumeUrl(data.resume.id, "pdf", true)}>Download PDF</a>
      </Panel>}
      <Panel title="Recommendation feedback">
        <div className="inline">{Object.entries(feedbackOptions).map(([value, name]) => <Button variant="outline" key={value}
          disabled={busy || data.feedback === value} onClick={() => void mutate(jobPath(data.job.id) + "/feedback", "POST", {value}, "Recommendation feedback saved.")}>{name}</Button>)}</div>
      </Panel>
    </div>}
  </>;
}
