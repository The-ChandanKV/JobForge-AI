import { useState } from "react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { officialUrl } from "../api";
import { date, label } from "../domain";
import { Details, ErrorNotice, Heading, Loading, Panel, Status, useResource } from "../shared";
import type { PageProps } from "../shared";
import { suggestedRoles } from "./settings";

type Original = {id: string; name: string};
type Evidence = {id: string; category: string; label: string; value: string; verified: boolean; career: boolean;
  conflict: string | null; evidence: {original: Original; excerpt: string}[]};
type Review = {revision: string; originals: Original[]; groups: Evidence[]};
type Posting = {role: string; location: string; url: string; work_mode?: string; posted?: string | null; required_years?: number | null};
type Employer = {key: string; company: string; roles: string; locations: string; enabled: boolean; can_enable: boolean; verified_at: string | null;
  preview: {complete: boolean; listing_count: number; jobs: Posting[]} | null};
type ActivationSummary = {
  checks: Record<string, boolean>; limit: number; next_run: string | null;
  latest_run: {
    status: string; finished: string | null; selected: number;
    scanned: number; discovered: number; eligible: number; compiled: number; prepared: number; errors: string[];
  } | null;
};

const list = (value: string) => value.split(",").map(item => item.trim()).filter(Boolean);
const toggle = (items: string[], item: string, checked: boolean) => checked ? [...items, item] : items.filter(value => value !== item);
const originalUrl = (original: Original) => "/api/profile/uploads/" + original.id;
const words = (text: string): string[] => text.toLowerCase().match(/[a-z0-9]+/g) ?? [];
const phrase = (text: string) => " " + words(text).join(" ") + " ";
const timestamp = (value?: string | null) => value ? Date.parse(value) || 0 : 0;
const proposedLocations = ["Bengaluru", "Hyderabad", "Pune", "Chennai"];
const roleTerms = /^(software|engineer|engineering|developer|entry|level|associate|graduate|intern|i)$/;

function proposeRoles(groups: Evidence[]) {
  const evidence = new Set(groups.filter(fact => fact.career).flatMap(fact => words(fact.value)));
  const support = (role: string) => words(role).filter(term => !roleTerms.test(term) && evidence.has(term)).length;
  return [...suggestedRoles].sort((left, right) => support(right) - support(left));
}

function rankBoards(boards: Employer[], roles: string[], locations: string[], modes: string[], maximum: string) {
  const targetTerms = roles.filter(role => words(role).length).map(phrase);
  const focus = new Set(roles.flatMap(words).filter(word => word.length >= 4));
  const markets = locations.map(phrase);
  if (locations.some(location => proposedLocations.some(city => phrase(city) === phrase(location)))) markets.push(" india ");
  if (modes.includes("remote")) markets.push(" remote ");
  const localModes = modes.filter(mode => mode !== "remote");
  return boards.filter(board => board.verified_at && board.preview).map(board => {
    const matches = board.preview!.jobs.filter(job => {
      const title = phrase(job.role);
      const place = job.location.toLowerCase();
      const remote = job.work_mode === "remote" || (!job.work_mode && words(place).includes("remote"));
      return targetTerms.some(term => title.includes(term)) &&
        (remote ? modes.includes("remote") : locations.some(location => phrase(place).includes(phrase(location))) &&
          (!localModes.length || (!!job.work_mode && localModes.includes(job.work_mode)))) &&
        (maximum === "" || job.required_years == null || job.required_years <= Number(maximum));
    });
    const knownExperience = matches.filter(job => job.required_years != null).length;
    const newest = Math.max(0, ...matches.map(job => timestamp(job.posted)));
    const catalogMarket = markets.some(market => phrase(board.locations).includes(market));
    const catalogFocus = words(board.roles).filter(word => focus.has(word)).length;
    return {...board, matches, knownExperience, newest, catalogMarket, catalogFocus};
  }).sort((left, right) => right.matches.length - left.matches.length || right.knownExperience - left.knownExperience ||
    right.newest - left.newest || Number(right.preview!.complete) - Number(left.preview!.complete) ||
    Number(right.catalogMarket) - Number(left.catalogMarket) || right.catalogFocus - left.catalogFocus ||
    timestamp(right.verified_at) - timestamp(left.verified_at));
}

export function Activation({state, revision, mutate, busy}: PageProps) {
  const {data: summary, error: summaryError} = useResource<ActivationSummary>("/api/activation", revision);
  const {data: review, error: reviewError} = useResource<Review>("/api/activation/review", revision);
  const {data: boards, error: boardsError} = useResource<Employer[]>("/api/employers", revision);
  const preferences = state.profile.preferences;
  const saved = (key: string) => Array.isArray(preferences[key]) ? preferences[key] : [];
  const [roleDraft, setRoles] = useState<string>();
  const [locationDraft, setLocations] = useState<string>();
  const [modeDraft, setModes] = useState<string[]>();
  const [employmentDraft, setEmployment] = useState<string>();
  const [experienceDraft, setExperience] = useState<string>();
  const [facts, setFacts] = useState<string[]>([]);
  const [boardKeys, setBoardKeys] = useState<string[]>([]);
  const [selectionRevision, setSelectionRevision] = useState<string>();
  const roles = roleDraft ?? (saved("roles").length ? saved("roles") : proposeRoles(review?.groups ?? [])).join(", ");
  const locations = locationDraft ?? (saved("locations").length ? saved("locations") : proposedLocations).join(", ");
  const modes = modeDraft ?? saved("work_modes");
  const employment = employmentDraft ?? saved("employment").join(", ");
  const maximum = experienceDraft ?? String(preferences.maximum_mandatory_years ?? "");
  const categories = new Map<string, Evidence[]>();
  for (const fact of review?.groups ?? []) {
    const group = categories.get(fact.category) ?? [];
    group.push(fact);
    categories.set(fact.category, group);
  }
  const ranked = rankBoards(boards ?? [], list(roles), list(locations), modes, maximum);
  const stale = !!selectionRevision && selectionRevision !== review?.revision;
  const selectedGroups = review?.groups.filter(fact => facts.includes(fact.id)) ?? [];
  const conflicting = selectedGroups.some(fact => fact.conflict && review?.groups.some(other =>
    other.id !== fact.id && other.conflict === fact.conflict && (other.verified || facts.includes(other.id))));
  const blockers = [
    !summary?.checks.Name && "Verify your name in Profile.",
    !summary?.checks.Email && "Verify your email in Profile.",
    !summary?.checks["Career evidence"] && !selectedGroups.some(fact => fact.career) && "Select accurate career evidence to verify.",
    list(roles).length === 0 && "Add a target role.",
    list(locations).length === 0 && !modes.includes("remote") && "Add a preferred location or approve remote work.",
    !boardKeys.length && "Select at least one verified employer board.",
    boardKeys.some(key => !ranked.some(board => board.key === key && board.can_enable)) && "Remove unavailable boards from your selection.",
    !state.options.enabled && "Resume hourly discovery in Automation.",
    !summary?.checks["Real submission disabled"] && "Enable dry-run preparation and disable automatic submission in Automation.",
    state.worker.pending > 0 && "Wait for the current run to finish.",
    stale && "The profile changed. Reset your fact selections and review the latest evidence.",
    conflicting && "Review conflicting entries and select only one value per credential or link.",
  ].filter(Boolean);
  const latest = summary?.latest_run;

  return <div className="content-grid">
    <Heading title="Activate JobForge" description="Review your resume evidence, search preferences, and employer boards together."/>
    <form className="content-grid" onSubmit={async event => {
      event.preventDefault();
      if (!review || blockers.length || busy || reviewError || boardsError || summaryError) return;
      const result = await mutate("/api/activation/confirm", "POST", {
        revision: review.revision, fact_ids: facts, board_keys: boardKeys,
        preferences: {roles: list(roles), locations: list(locations), employment: list(employment), work_modes: modes},
        ...(experienceDraft !== undefined ? {maximum_mandatory_years: maximum === "" ? null : Number(maximum)} : {}),
      }, "Activation confirmed. First dry-run preparation queued.");
      if (result) {
        setFacts([]);
        setBoardKeys([]);
        setSelectionRevision(undefined);
      }
    }}>
      <Panel title="Career evidence" caption="Select the facts you can verify. Open a source excerpt to compare entries across originals.">
        <ErrorNotice message={reviewError}/>
        {!review && !reviewError && <Loading/>}
        <div className="inline">{review?.originals.map(original => <a className="text-link" key={original.id}
          href={originalUrl(original)}>{original.name}</a>)}</div>
        <p>{facts.length} selected for verification</p>
        <div className="inline">
          <Link className="text-link" to="/profile">Manage contact details and originals</Link>
          {facts.length > 0 && <Button type="button" variant="outline" size="sm" onClick={() => {
            setFacts([]);
            setSelectionRevision(undefined);
          }}>Reset fact selections</Button>}
        </div>
        {review && <div className="stack">{[...categories].map(([category, entries]) =>
          <details key={category} open={entries.some(fact => fact.conflict) || undefined}>
            <summary>{category} · {entries.filter(fact => !fact.verified).length} to review</summary>
            <div className="fact-list">{entries.map(fact => <article className="fact" key={fact.id}>
              <strong>{fact.value}</strong>
              {fact.label === "Graduation year" && <p className="subtle">Check the stated year or education date range in the original.</p>}
              {fact.conflict && <Status value="Conflicting source values"/>}
              {fact.verified ? <Status value="Verified"/> : <label className="check"><input type="checkbox"
                aria-label={"Verify " + fact.value} disabled={busy || stale} checked={facts.includes(fact.id)} onChange={event => {
                  setSelectionRevision(review.revision);
                  setFacts(toggle(facts, fact.id, event.target.checked));
                }}/>Verify this fact</label>}
              {fact.evidence.length > 0 && <details><summary>Source evidence · {fact.evidence.length}</summary>
                {fact.evidence.map(({original, excerpt}, index) => <div key={index}>
                  <a className="text-link" href={originalUrl(original)}>{original.name}</a><blockquote>{excerpt}</blockquote>
                </div>)}
              </details>}
            </article>)}</div>
          </details>)}</div>}
      </Panel>

      <Panel title="Search preferences" caption="The proposed roles use draft resume evidence. Edit the roles and cities, and select Remote if you want remote discovery.">
        <div className="form-grid">
          <label>Target roles<input value={roles} onChange={event => setRoles(event.target.value)} required/></label>
          <label>Preferred locations<input value={locations} onChange={event => setLocations(event.target.value)}/></label>
          <label>Employment types<input value={employment} onChange={event => setEmployment(event.target.value)} placeholder="Full-time, internship"/></label>
          <label>Maximum mandatory years of experience<input type="number" min="0" max="30" step="1" value={maximum}
            onChange={event => setExperience(event.target.value)}/></label>
        </div>
        <fieldset><legend>Work modes</legend><div className="inline">{["remote", "hybrid", "onsite"].map(mode =>
          <label className="check" key={mode}><input type="checkbox" checked={modes.includes(mode)}
            onChange={event => setModes(toggle(modes, mode, event.target.checked))}/>{label(mode)}</label>
        )}</div></fieldset>
        <p>For entry-level searches, consider roles asking for up to two years. Eligibility is checked against your verified evidence.</p>
        <Button type="button" variant="outline" size="sm" onClick={() => setExperience("2")}>Use two-year search limit</Button>
      </Panel>

      <Panel title="Verified employer boards" caption="Ranked using the saved samples, source health, and employer directory. Experience and posting dates are used when available.">
        <ErrorNotice message={boardsError}/>
        {!boards && !boardsError && <Loading/>}
        {boards && !ranked.length && <p>No saved employer previews. <Link className="text-link" to="/settings">Verify a board in Settings</Link>.</p>}
        <div className="fact-list">{ranked.map(board => <article className="fact" key={board.key}>
          <label className="check"><input type="checkbox" checked={boardKeys.includes(board.key)}
            disabled={busy || !board.can_enable || (boardKeys.length >= 10 && !boardKeys.includes(board.key))}
            onChange={event => setBoardKeys(toggle(boardKeys, board.key, event.target.checked))}/>Select {board.company}</label>
          <p>{board.preview!.listing_count} postings in saved feed · {board.preview!.complete ? "Complete source check" : "Partial source check"}
            {board.enabled && " · Monitoring enabled"}</p>
          <p className="subtle">Verified {date(board.verified_at, state.options.timezone)}</p>
          <p className="subtle">Employer directory · {board.locations} · {board.roles}</p>
          <p>{board.matches.length ? board.matches.length + " potential matches in saved preview" : "No suitable openings in the saved preview"}</p>
          {board.matches.length > 0 && <details><summary>Potential matches</summary><ul className="entries">
            {board.matches.map(job => <li key={job.url}><a className="text-link" href={officialUrl(job.url)}
              target="_blank" rel="noreferrer">{job.role}</a>
              <small>{job.location || "Location unavailable"} · {job.required_years == null ? "Experience unavailable" : job.required_years + " years required"}
                {" · "}{job.posted ? "Posted " + date(job.posted, state.options.timezone) : "Posting date unavailable"}</small></li>)}
          </ul></details>}
        </article>)}</div>
      </Panel>

      <Panel title="Automation and readiness" caption="AUTONOMOUS PREPARATION + MANUAL FINAL APPROVAL">
        <ErrorNotice message={summaryError}/>
        <Details values={{"Scheduled interval": state.options.interval_minutes + " minutes", worker: label(state.worker.status),
          "Next scheduled run": date(summary?.next_run, state.options.timezone), "First run limit": summary?.limit ?? 5,
          "Selected boards": boardKeys.length}}/>
        {summary && (blockers.length ? <ul className="bullets">{blockers.map(item => <li key={String(item)}>{item}</li>)}</ul>
          : <Status value="Ready to confirm"/>)}
        <Button type="submit" disabled={!review || !summary || !boards || !!blockers.length || busy || !!(reviewError || boardsError || summaryError)}>
          Confirm activation and queue first run
        </Button>
      </Panel>
    </form>

    <Panel title="First real preparation">
      {latest ? <>
        <Details values={{status: label(latest.status), finished: date(latest.finished, state.options.timezone), scanned: latest.scanned,
          discovered: latest.discovered, "eligibility checks passed": latest.eligible, selected: latest.selected,
          "compiled PDFs": latest.compiled, "prepared applications": latest.prepared}}/>
        {!!latest.errors.length && <ul className="bullets">{latest.errors.map((item, index) => <li key={index}>{item}</li>)}</ul>}
      </> : <p>Waiting for activation confirmation.</p>}
      <div className="inline"><Link className="text-link" to="/automation">View worker and run history</Link>
        <Link className="text-link" to="/approvals">Open Approval Queue</Link></div>
    </Panel>
  </div>;
}
