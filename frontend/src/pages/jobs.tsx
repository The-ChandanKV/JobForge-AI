import { useState } from "react";
import { ArrowUpRight, ChevronLeft, ChevronRight, Plus, Search } from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { jobPath, officialUrl } from "../api";
import type { Job } from "../api";
import { date, label, searchMatch } from "../domain";
import { Details, Empty, ErrorNotice, Heading, Loading, Modal, Panel, Status, useResource } from "../shared";
import type { PageProps } from "../shared";
import { Company } from "./overview";

const size = 15;

export function MatchDetails({ job }: { job: Job }) {
  const match = job.match;
  return <Panel title="Match and eligibility">
    <div className="inline"><Status value={match.eligibility} tone={match.eligibility === "ELIGIBLE" ? "good" : "warn"}/>
      {typeof match.match_score === "number" && <span className="score-pill">{match.match_score}%</span>}</div>
    {match.reason && <p>{match.reason}</p>}
    {match.concerns?.length ? <ul className="bullets">{match.concerns.map((item, index) => <li key={index}>{item}</li>)}</ul> : null}
    <Details values={{ "Verified matches": match.matching_skills?.join(", "), "Required skills": match.required_skills?.join(", "),
      "Missing skills": match.missing_skills?.join(", "), "Preferred skills": match.preferred_skills?.join(", ") }}/>
    {!!match.alternative_skill_groups?.length && <p>One skill per group · {match.alternative_skill_groups.map(group => group.join(" or ")).join(" · ")}</p>}
    {!!match.components && <details><summary>Score breakdown</summary><Details values={match.components}/></details>}
    {!!match.requirement_evidence && <details><summary>Posting requirements</summary>
      <Details values={Object.fromEntries(Object.entries(match.requirement_evidence).filter(([, lines]) => lines.length).map(([key, lines]) => [key, lines.join("\n")]))}/>
    </details>}
  </Panel>;
}

export function JobDrawer({ id, close, revision, mutate, busy }: Pick<PageProps, "revision" | "mutate" | "busy"> & { id: string; close: () => void }) {
  const { data: job, error } = useResource<Job>(jobPath(id), revision);
  const official = officialUrl(job?.url);
  return <Modal title="Job details" drawer close={close}>
    <ErrorNotice message={error}/>{!job && !error && <Loading/>}
    {job && <>
      <div className="inline"><Company job={job}/><Status value={job.status}/>{!job.available && <Status value="Posting unavailable" tone="warn"/>}</div>
      <div className="inline">
        <Button variant="outline" disabled={busy || job.status === "SHORTLISTED"} onClick={() => void mutate(jobPath(id) + "/status", "PUT", {status: "SHORTLISTED"}, "Job shortlisted.")}>Shortlist</Button>
        <Button variant="outline" disabled={busy || job.status === "SKIPPED"} onClick={() => void mutate(jobPath(id) + "/status", "PUT", {status: "SKIPPED"}, "Job skipped.")}>Skip</Button>
        {job.available && <Button asChild><Link to={"/resume-studio?job=" + id}>Prepare resume</Link></Button>}
        {official && <a className="text-link" href={official} target="_blank" rel="noreferrer">Original posting <ArrowUpRight size={14}/></a>}
      </div>
      <Link className="text-link" to={"/intelligence?job=" + id}>Open Job Intelligence <ArrowUpRight size={14}/></Link>
      <MatchDetails job={job}/>
      <Panel title="Posting"><Details values={{ source: job.source, location: job.location, "work mode": job.work_mode, employment: job.employment, "last verified": date(job.verified) }}/>
        <p className="preserve">{job.description || "No job description was saved."}</p></Panel>
    </>}
  </Modal>;
}

export function Jobs(props: PageProps) {
  const { state, mutate, busy } = props;
  const [params, setParams] = useSearchParams();
  const [search, setSearch] = useState("");
  const [filters, setFilters] = useState({ role: "", company: "", location: "", score: "0", status: "", sort: "date" });
  const [page, setPage] = useState(1);
  const [add, setAdd] = useState(false);
  const qualified = params.get("qualified") === "true";
  const chosen = params.get("job");
  const similar = state.jobs.find(job => job.id === params.get("similar"));
  const similarSkill = new Set(similar?.match.required_skills ?? []);
  const roleWords = (job: Job) => job.role.toLowerCase().split(/[^a-z]+/).filter(word => word.length > 3);
  const shared = (job: Job) => similarSkill.size > 0 && job.match.required_skills?.some(skill => similarSkill.has(skill));
  const rows = state.jobs.filter(job => (!similar || (job.id !== similar.id && job.available &&
    (shared(job) || roleWords(job).some(word => !["engineer", "software", "developer"].includes(word) && roleWords(similar).includes(word))))) &&
    searchMatch(search, job.role, job.company, job.location, job.source) &&
    (!filters.role || job.role === filters.role) && (!filters.company || job.company === filters.company) &&
    (!filters.location || job.location === filters.location) && (!filters.status || job.status === filters.status) &&
    (filters.score === "0" || (job.match.match_score ?? -1) >= Number(filters.score)) &&
    (!qualified || job.match.recommendation === "PREPARE_APPLICATION"))
    .sort((a,b) => filters.sort === "score" ? (b.match.match_score ?? -1) - (a.match.match_score ?? -1) : b.created.localeCompare(a.created));
  const pages = Math.max(1, Math.ceil(rows.length / size));
  const activePage = Math.min(page, pages);
  function filter(key: keyof typeof filters, value: string) {
    setFilters({ ...filters, [key]: value }); setPage(1);
  }
  function param(key: string, value?: string) {
    setParams(current => {
      const next = new URLSearchParams(current);
      if (value) next.set(key, value); else next.delete(key);
      return next;
    });
  }

  return <>
    <Heading title="Job discovery" description="Explore saved postings and see how each role matches your verified profile."><Button onClick={() => setAdd(true)}><Plus size={16}/> Add posting</Button></Heading>
    {similar && <Panel title={"Similar roles to " + similar.role} caption="Available postings that share role terms or detected required skills.">
      <div className="inline">
        <Button variant="outline" disabled={busy || state.worker.pending > 0} onClick={() => void mutate("/api/runs", "POST", undefined, "Discovery queued for configured job boards.")}>Refresh discovery</Button>
        <Button variant="ghost" onClick={() => param("similar")}>Show all jobs</Button>
      </div>
    </Panel>}
    <Panel title="">
      <div className="toolbar">
        <label className="search-field"><Search size={16}/><input aria-label="Search jobs" value={search} placeholder="Search jobs" onChange={event => {setSearch(event.target.value); setPage(1);}}/></label>
        {(["role", "company", "location", "status"] as const).map(key => {
          const choices = [...new Set(state.jobs.map(job => job[key]).filter((item): item is string => !!item))].sort();
          return <label key={key}>{label(key)}<select value={filters[key]} onChange={event => filter(key, event.target.value)}>
            <option value="">All</option>{choices.map(item => <option key={item} value={item}>{key === "status" ? label(item) : item}</option>)}
          </select></label>;
        })}
        <label>Minimum match<select value={filters.score} onChange={event => filter("score", event.target.value)}>
          <option value="0">Any</option>{[50, 65, 80, 90].map(score => <option key={score} value={score}>{score}%</option>)}
        </select></label>
        <label>Sort<select value={filters.sort} onChange={event => filter("sort", event.target.value)}><option value="date">Newest</option><option value="score">Highest match</option></select></label>
        {qualified && <Button variant="outline" onClick={() => param("qualified")}>Clear qualified filter</Button>}
      </div>
      {rows.length ? <div className="table-wrap"><table className="data-table responsive-table" role="table"><thead><tr><th>Posting</th><th>Source</th><th>Match</th><th>Eligibility</th><th>Status</th></tr></thead>
        <tbody>{rows.slice((activePage - 1) * size, activePage * size).map(job => <tr key={job.id}>
          <td><button className="flat-button" onClick={() => param("job", job.id)}><Company job={job}/></button></td>
          <td data-label="Source">{label(job.source)}</td><td data-label="Match">{typeof job.match.match_score === "number" ? <span className="score-pill">{job.match.match_score}%</span> : "—"}</td>
          <td data-label="Eligibility"><Status value={job.match.eligibility}/></td><td data-label="Status"><Status value={job.status}/></td>
        </tr>)}</tbody></table></div> : <Empty>{state.jobs.length ? "No jobs match the selected filters." : "Add a posting or run automation to discover jobs."}</Empty>}
      <div className="pagination"><span>{rows.length} jobs · Page {activePage} of {pages}</span>
        <Button variant="outline" size="icon" aria-label="Previous page" disabled={activePage === 1} onClick={() => setPage(activePage - 1)}><ChevronLeft size={16}/></Button>
        <Button variant="outline" size="icon" aria-label="Next page" disabled={activePage === pages} onClick={() => setPage(activePage + 1)}><ChevronRight size={16}/></Button></div>
    </Panel>
    {chosen && <JobDrawer {...props} id={chosen} close={() => param("job")}/>}
    {add && <Modal title="Add a job posting" close={() => setAdd(false)}>
      <form className="stack" onSubmit={async event => {
        event.preventDefault();
        const form = new FormData(event.currentTarget);
        const url = String(form.get("url")).trim();
        const saved = await mutate<Job>("/api/jobs", "POST", {
          ...(url ? {url} : {}), company: String(form.get("company")).trim() || "Manual entry",
          role: String(form.get("role")).trim() || "Untitled role", description: String(form.get("description")).trim(),
        }, "Posting saved and evaluated.");
        if (saved) {setAdd(false); param("job", saved.id);}
      }}>
        <label>Posting URL<input name="url" type="url" placeholder="https://…"/></label>
        <label>Company<input name="company" maxLength={240}/></label>
        <label>Role<input name="role" maxLength={300}/></label>
        <label>Job description<textarea name="description" rows={7} maxLength={100000}/></label>
        <p className="subtle">Provide an official posting URL or paste the job description.</p>
        <Button disabled={busy} type="submit">Save posting</Button>
      </form>
    </Modal>}
  </>;
}
