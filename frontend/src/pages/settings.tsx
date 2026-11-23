import { useState } from "react";
import { Plus, Save, Trash2 } from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import type { Fact, Options, Preferences, Profile, Source, Upload } from "../api";
import { date, label, searchMatch } from "../domain";
import { Details, Empty, ErrorNotice, Heading, Modal, Panel, Status, useResource } from "../shared";
import type { PageProps } from "../shared";
import { EmployerDirectory } from "./employers";
import { UploadForm } from "./studio";

const categories = ["personal", "education", "experience", "skill", "project", "authorization", "certification", "other"];
const preferenceLists = ["roles", "locations", "work_modes", "employment", "levels", "career_tracks", "excluded_roles", "excluded_keywords", "target_companies", "priority_companies", "industries", "excluded_companies"];
export const suggestedRoles = ["Software Engineer I", "Graduate Software Engineer", "Associate Software Engineer",
  "Backend Developer", "Full Stack Developer", "Python Developer", "Data Engineer", "AI/ML Engineer",
  "Entry-level Software Developer", "Software Engineering Intern"];
const preferenceChoices: Record<string, string[]> = {
  work_modes: ["remote", "hybrid", "onsite"],
  career_tracks: ["entry-level", "graduate", "backend", "full-stack", "data", "ai-ml", "internship"],
};

function listInput(current: Preferences, key: string) {
  const value = current[key];
  return Array.isArray(value) ? value.join(", ") : "";
}

export function ProfilePage(props: PageProps) {
  const { state, mutate, busy } = props;
  const [draft, setDraft] = useState<Profile>();
  const [listDraft, setListDraft] = useState<Record<string, string>>({});
  const [params] = useSearchParams();
  const [query, setQuery] = useState("");
  const [unverified, setUnverified] = useState(params.get("review") === "1");
  const [reviewed, setReviewed] = useState<Fact[]>([]);
  const [confirming, setConfirming] = useState(false);
  const [editing, setEditing] = useState<string>();
  const [scope, setScope] = useState<string>();
  const {data: uploads} = useResource<Upload[]>("/api/profile/uploads", props.revision);
  const [original, setOriginal] = useState("");
  const {data: sourceDocument, error: sourceError} = useResource<{name: string; text: string}>(
    original ? "/api/profile/uploads/" + original + "/text" : null);
  const current = draft ?? state.profile;
  const hasDraft = !!draft || Object.keys(listDraft).length > 0;
  function toggleReviewed(fact: Fact) {
    setReviewed(previous => previous.some(item => item.id === fact.id)
      ? previous.filter(item => item.id !== fact.id) : [...previous, fact]);
  }
  const facts = current.facts.filter(fact => searchMatch(query, fact.label, fact.value, fact.category) &&
    (!unverified || !fact.verified) && (!scope || fact.source === scope));
  const sources = [...new Set(current.facts.map(fact => fact.source))];
  function updateFact(id: string, changes: Partial<Fact>) {
    setDraft({ ...current, facts: current.facts.map(fact => fact.id === id ? {...fact, ...changes} : fact) });
  }

  function updatePreference(key: string, value: Preferences[string]) {
    setDraft({...current, preferences: {...current.preferences, [key]: value}});
  }

  async function saveProfile() {
    const modified = new Map(current.facts.map(fact => [fact.id, fact]));
    const overwrites = state.profile.facts.some(fact => {
      if (!fact.verified) return false;
      const updated = modified.get(fact.id);
      return !updated || !updated.verified || fact.label !== updated.label ||
        fact.category !== updated.category || fact.value !== updated.value;
    });
    if (overwrites && !window.confirm("Save changes that edit, remove, or unverify existing verified facts?")) return;
    const preferences = {...current.preferences};
    for (const [key, text] of Object.entries(listDraft)) preferences[key] = text.split(",").map(item => item.trim()).filter(Boolean);
    const result = await mutate<Profile>("/api/profile", "PUT", {...current, preferences}, "Profile saved.");
    if (result) {setDraft(undefined); setListDraft({});}
  }
  return <>
    <Heading title="Candidate profile" description="Manage your job preferences and verify facts against their original evidence.">
      <Button type="submit" form="profile-form" disabled={busy || (!draft && !Object.keys(listDraft).length)}><Save size={16}/> Save profile</Button>
    </Heading>
    <div className="split-grid studio-top">
      <Panel title="Profile coverage">
        <Status value={state.profile_readiness.ready ? "Ready for autonomous preparation" : "Verified evidence required"}/>
        <Details values={Object.fromEntries(Object.entries(state.profile_readiness.checks).map(([key, value]) => [key, value ? "Verified" : "Required"]))}/>
        <Details values={{ "verified facts": current.facts.filter(fact => fact.verified).length, "draft facts": current.facts.filter(fact => !fact.verified).length, total: current.facts.length }}/></Panel>
      <Panel title="Import a resume">{draft || Object.keys(listDraft).length ? <p className="subtle">Save or discard your draft before importing another resume.</p> : <UploadForm {...props}/>}</Panel>
    </div>
    <form id="profile-form" className="content-grid" onSubmit={event => {event.preventDefault(); void saveProfile();}}>
      <Panel title="Job preferences" caption="Use commas to separate roles, locations, and keywords.">
        <Button type="button" variant="outline" onClick={() => setListDraft({...listDraft, roles: suggestedRoles.join(", ")})}>Use software engineering role suggestions</Button>
        <div className="form-grid">{preferenceLists.map(key => {
          const choices = preferenceChoices[key];
          const values = current.preferences[key];
          return choices ? <fieldset key={key}><legend>{label(key)}</legend><div className="inline">{choices.map(choice =>
            <label className="check" key={choice}><input type="checkbox" checked={Array.isArray(values) && values.includes(choice)} onChange={event => {
              const selected = Array.isArray(values) ? values : [];
              updatePreference(key, event.target.checked ? [...selected, choice] : selected.filter(value => value !== choice));
            }}/>{label(choice)}</label>)}</div></fieldset>
            : <label key={key}>{label(key)}<input value={listDraft[key] ?? listInput(current.preferences, key)}
              onChange={event => setListDraft({...listDraft, [key]: event.target.value})}/></label>;
        })}
        {(["min_salary", "recent_days", "minimum_mandatory_years", "maximum_mandatory_years"] as const).map(key => <label key={key}>{label(key)}
          <input type="number" min={key === "recent_days" ? 1 : 0} max={key === "recent_days" ? 365 : key.endsWith("mandatory_years") ? 30 : undefined}
            value={String(current.preferences[key] ?? "")} onChange={event => updatePreference(key, event.target.value === "" ? null : Number(event.target.value))}/></label>)}
        <label>Salary currency<input maxLength={3} value={String(current.preferences.salary_currency ?? "")} onChange={event => updatePreference("salary_currency", event.target.value)}/></label>
        <label>Relocation<input maxLength={160} value={String(current.preferences.relocation ?? "")} onChange={event => updatePreference("relocation", event.target.value)}/></label>
        <label className="check"><input type="checkbox" checked={Boolean(current.preferences.exclude_senior_roles)} onChange={event => updatePreference("exclude_senior_roles", event.target.checked)}/> Exclude senior roles</label></div>
      </Panel>
      <div className={uploads?.length ? "split-grid" : "content-grid"}>
    {!!uploads?.length && <Panel title="Original resume" caption="Select an upload to read its text and review the extracted facts beside it.">
      <label>Original document<select value={original} onChange={event => {
        setOriginal(event.target.value); setScope(event.target.value ? "upload:" + event.target.value : undefined);
      }}><option value="">Select an upload</option>{uploads.map(upload => <option value={upload.id} key={upload.id}>{upload.name}</option>)}</select></label>
      {original && <a className="text-link" href={"/api/profile/uploads/" + original}>Download original</a>}
      <ErrorNotice message={sourceError}/>
      {sourceDocument && <pre className="resume-source">{sourceDocument.text}</pre>}
    </Panel>}
      <Panel title="Profile facts">
        <p className="subtle">Read each original excerpt before adding a draft fact to the verification batch.</p>
        <div className="toolbar">
          <label>Search facts<input type="search" value={query} onChange={event => setQuery(event.target.value)}/></label>
          <label>Source<select value={scope ?? ""} onChange={event => setScope(event.target.value)}><option value="">All sources</option>{sources.map(source => <option key={source}>{source}</option>)}</select></label>
          <label className="check"><input type="checkbox" checked={unverified} onChange={event => setUnverified(event.target.checked)}/> Unverified only</label>
          <Button type="button" variant="outline" disabled={current.facts.length >= 250} onClick={() => {
            const id = crypto.randomUUID().replaceAll("-", "");
            setDraft({...current, facts: [{id, category:"other", label:"", value:"", verified:false, source:"manual", excerpt:""}, ...current.facts]});
            setQuery(""); setScope(undefined); setEditing(id);
          }}><Plus size={16}/> Add fact</Button>
          {(draft || Object.keys(listDraft).length > 0) && <Button type="button" variant="ghost" onClick={() => {setDraft(undefined); setListDraft({});}}>Discard draft</Button>}
        </div>
        {!!reviewed.length && !hasDraft && <div className="inline">
          <Button type="button" variant="outline" onClick={() => setConfirming(true)}>Review selected facts ({reviewed.length})</Button>
          <Button type="button" variant="ghost" onClick={() => setReviewed([])}>Clear selection</Button>
        </div>}
        {facts.length ? <div className="fact-list">{facts.map(fact => <article className="fact" key={fact.id}>
          {editing === fact.id ? <div className="stack">
            <label>Category<select value={fact.category} onChange={event => updateFact(fact.id, {category: event.target.value, verified: false})}>{categories.map(category => <option key={category}>{category}</option>)}</select></label>
            <label>Label<input required maxLength={100} value={fact.label} onChange={event => updateFact(fact.id, {label: event.target.value, verified: false})}/></label>
            <label>Value<textarea required maxLength={1500} value={fact.value} onChange={event => updateFact(fact.id, {value: event.target.value, verified: false})}/></label>
          </div> : <div><strong>{fact.label || "New fact"}</strong><p className="preserve">{fact.value}</p></div>}
          <p className="subtle">{label(fact.category)} · {fact.source}</p>
          {fact.excerpt && <details open={unverified && !fact.verified ? true : undefined}><summary>Source excerpt</summary><p className="preserve">{fact.excerpt}</p></details>}
          <div className="inline">
            {!hasDraft && !fact.verified && !fact.unsupported && fact.source.startsWith("upload:") && fact.excerpt &&
              <label className="check"><input type="checkbox" checked={reviewed.some(item => item.id === fact.id)}
                onChange={() => toggleReviewed(fact)}/> Select reviewed evidence</label>}
            <label className="check"><input type="checkbox" checked={fact.verified} disabled={fact.unsupported || !fact.label.trim() || !fact.value.trim()} onChange={event => updateFact(fact.id, {verified:event.target.checked})}/> Verified</label>
            <label className="check"><input type="checkbox" checked={!!fact.unsupported} onChange={event => updateFact(fact.id, {
              unsupported: event.target.checked, ...(event.target.checked ? {verified: false, prioritized: false} : {}),
            })}/> Unsupported</label>
            {fact.category === "project" && <label className="check"><input type="checkbox" checked={!!fact.prioritized && fact.verified}
              disabled={!fact.verified} onChange={event => updateFact(fact.id, {prioritized: event.target.checked})}/> Prioritize project</label>}
            <Button type="button" size="sm" variant="ghost" onClick={() => setEditing(editing === fact.id ? undefined : fact.id)}>{editing === fact.id ? "Done" : "Edit"}</Button>
            <Button type="button" size="icon" variant="ghost" aria-label={"Remove " + (fact.label || "new fact")} onClick={() => setDraft({...current, facts: current.facts.filter(item => item.id !== fact.id)})}><Trash2 size={15}/></Button>
          </div>
        </article>)}</div> : <Empty>No facts match this view.</Empty>}
      </Panel>
      </div>
    </form>
    {confirming && <Modal title="Confirm source facts" close={() => setConfirming(false)}>
      <p>Verify only the facts that accurately reflect your original resume.</p>
      <ul className="entries">{reviewed.map(fact => <li key={fact.id}><div><strong>{fact.label} · {fact.value}</strong>
        <small>{fact.excerpt}</small></div></li>)}</ul>
      <Button disabled={busy || !reviewed.length} onClick={async () => {
        const result = await mutate<{verified: number}>("/api/profile/verify", "POST", {facts: reviewed}, "Reviewed source facts verified.");
        if (result) {setReviewed([]); setConfirming(false);}
      }}>Verify {reviewed.length} selected facts</Button>
    </Modal>}
  </>;
}

const numbers = {
  interval_minutes: [1, 1440], min_match_score: [0, 100], max_applications_per_day: [0, 100],
  max_submissions_per_day: [0, 100], max_resume_generations_per_run: [0, 50], max_job_attempts: [1, 8],
  notification_interval_minutes: [1, 1440],
} as const;
const toggles = ["enabled", "retry_failed_jobs", "exception_notifications", "desktop_notifications", "approval_email"] as const;

export function Settings(props: PageProps) {
  const {state, mutate, busy} = props;
  const [draft, setDraft] = useState<Partial<Options>>({});
  const current = {...state.options, ...draft};
  const sources = current.sources;
  const authorizedMode = current.mode === "AUTHORIZED_AUTO";
  function setSubmissionMode(enabled: boolean) {
    setDraft(previous => ({...previous, mode: enabled ? "AUTHORIZED_AUTO" : "ASSISTED", dry_run: !enabled}));
  }
  function update<K extends keyof Options>(name: K, value: Options[K]) {
    setDraft(previous => ({...previous, [name]: value}));
  }
  function sourceChange(index: number, changes: Partial<Source>) {
    update("sources", sources.map((source, position) => position === index ? {...source, ...changes} : source));
  }
  return <>
    <Heading title="Settings" description="Configure matching, discovery sources, resume generation, and automation.">
      <Button type="submit" form="settings-form" disabled={busy || !Object.keys(draft).length}><Save size={16}/> Save settings</Button>
    </Heading>
    <EmployerDirectory {...props}/>
    <form id="settings-form" className="content-grid" onSubmit={async event => {
      event.preventDefault();
      if (await mutate<Options>("/api/settings", "PUT", current, "Settings saved.")) setDraft({});
    }}>
      <div className="split-grid">
        <Panel title="Automation and notifications">
          <div className="form-grid">
            {Object.entries(numbers).map(([key, [min, max]]) => {
              const name = key as keyof typeof numbers;
              return <label key={key}>{label(key)}<input type="number" min={min} max={max} required value={current[name]} onChange={event => update(name, event.target.valueAsNumber || 0)}/></label>;
            })}
            <label>Time zone<input required value={current.timezone} onChange={event => update("timezone", event.target.value)}/></label>
            {toggles.map(name => <label className="check" key={name}><input type="checkbox" checked={current[name]} onChange={event => update(name, event.target.checked)}/>{label(name)}</label>)}
          </div>
        </Panel>
        <Panel title="AI and resume generation">
          <div className="stack">
            <label>Model provider<select value={current.provider ?? ""} onChange={event => update("provider", event.target.value || null)}>
              <option value="">Server default</option><option value="rules">Rules only</option><option value="ollama">Ollama</option>
              <option value="openai">OpenAI</option><option value="anthropic">Anthropic</option>
            </select></label>
            <label>Local semantic ranking model<input maxLength={150} value={current.semantic_model ?? ""} onChange={event => update("semantic_model", event.target.value)}/></label>
            <label>Local tailoring model<input maxLength={150} value={current.tailoring_model ?? ""} onChange={event => update("tailoring_model", event.target.value)}/></label>
            <label>Model override<input maxLength={150} value={current.model} onChange={event => update("model", event.target.value)}/></label>
            <Link className="text-link" to="/resume-studio">Choose a template in Resume Studio</Link>
          </div>
          <Details values={{ "configured provider": state.provider, "configured model": state.model }}/>
        </Panel>
      </div>
      <Panel title="Job boards" caption="Configure discovery by board slug. Employer submission credentials are managed on the server.">
        {sources.map((source, index) => <div key={index} className="toolbar source-row">
          <label>Provider<select value={source.provider} onChange={event => sourceChange(index, {provider:event.target.value})}>
            {["greenhouse", "lever", "ashby", "smartrecruiters", "recruitee", "mock"].map(name => <option key={name}>{name}</option>)}
          </select></label>
          <label>Board slug<input required pattern="[A-Za-z0-9_\-]{1,80}" value={source.board} onChange={event => sourceChange(index, {board:event.target.value})}/></label>
          {source.provider === "smartrecruiters" && <label>Search terms<input maxLength={100} value={source.search ?? "software"} onChange={event => sourceChange(index, {search:event.target.value})}/></label>}
          <label>Company<input required maxLength={150} value={source.company} onChange={event => sourceChange(index, {company:event.target.value})}/></label>
          <label className="check"><input type="checkbox" checked={source.enabled} onChange={event => sourceChange(index, {enabled:event.target.checked})}/> Enabled</label>
          <Button type="button" variant="ghost" size="icon" aria-label={"Remove board " + (index + 1)} onClick={() => update("sources", sources.filter((_, position) => index !== position))}><Trash2 size={15}/></Button>
        </div>)}
        {!sources.length && <Empty>No discovery boards configured.</Empty>}
        <Button type="button" variant="outline" disabled={sources.length >= 20} onClick={() => update("sources", [...sources, {provider:"greenhouse", board:"", company:"", enabled:true}])}><Plus size={16}/> Add board</Button>
      </Panel>
      <Panel title="Review and system health">
        <div className="inline"><Status value="Final approval required" tone="good"/><Status value={"Worker " + state.worker.status}/></div>
        <label className="check"><input type="checkbox" checked={authorizedMode && !current.dry_run}
          disabled={!state.authorized_board && !authorizedMode}
          onChange={event => setSubmissionMode(event.target.checked)}/> Enable individually approved Greenhouse submission</label>
        <p className="subtle">{state.authorized_board ? "Final approval is required for each application. Save settings to apply this change."
          : "A verified employer board must be configured on the server to enable this option."}</p>
        <Details values={{ "automation mode": label(current.automation_mode), "application mode": label(current.mode),
          "dry run": current.dry_run ? "Enabled" : "Disabled by server configuration", "authorized board": state.authorized_board,
          "last heartbeat": date(state.worker.last_heartbeat), "last successful run": date(state.worker.last_success),
          "model health": state.worker.model }}/>
      </Panel>
    </form>
  </>;
}
