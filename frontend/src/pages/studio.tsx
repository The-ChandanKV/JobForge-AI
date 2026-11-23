import { useState } from "react";
import { Download, FilePlus2, UploadCloud } from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { jobPath, resumeUrl } from "../api";
import type { Application, Fact, Resume, Upload } from "../api";
import { date, display, label } from "../domain";
import { Details, Empty, ErrorNotice, Heading, Loading, Panel, Status, useResource } from "../shared";
import type { PageProps } from "../shared";
import { MatchDetails } from "./jobs";

export function UploadForm({ mutate, busy }: Pick<PageProps, "mutate" | "busy">) {
  const [imported, setImported] = useState<number>();
  return <form className="stack" onSubmit={async event => {
    event.preventDefault();
    const form = event.currentTarget;
    const result = await mutate<{ imported: number }>("/api/profile/upload", "POST", new FormData(form));
    if (result) {setImported(result.imported); form.reset();}
  }}>
    <label>Original resume<input type="file" name="file" accept=".pdf,.txt,.tex" required/></label>
    <Button type="submit" variant="outline" disabled={busy}><UploadCloud size={16}/> Import resume</Button>
    {imported !== undefined && <p role="status">{imported} draft facts imported. Verify the evidence in Profile before using it.</p>}
  </form>;
}

export function Studio(props: PageProps) {
  const { state, mutate, revision, busy } = props;
  const [params, setParams] = useSearchParams();
  const job = state.jobs.find(item => item.id === params.get("job"));
  return <>
    <Heading title="AI Resume Studio" description="Build and compare resume versions using facts you have verified."/>
    <div className="split-grid studio-top">
      <Panel title="Candidate evidence" caption={state.profile.facts.filter(fact => fact.verified).length + " verified facts"}>
        <UploadForm {...props}/><Link className="text-link" to="/profile">Review profile facts</Link>
      </Panel>
      <Panel title="Target job">
        <label>Job<select value={job?.id ?? ""} onChange={event => setParams(event.target.value ? {job: event.target.value} : {})}>
          <option value="">Select a saved role</option>
          {state.jobs.map(item => <option key={item.id} value={item.id}>{item.role} · {item.company}</option>)}
        </select></label>
      </Panel>
    </div>
    {job ? <><MatchDetails job={job}/><VersionWorkspace key={job.id} jobId={job.id} facts={state.profile.facts} mutate={mutate} revision={revision} busy={busy}/></>
      : <Panel title=""><Empty>Select a job to unlock tailored resume versions, a cover letter, and application preparation.</Empty></Panel>}
  </>;
}

function VersionWorkspace({ jobId, facts, mutate, revision, busy }: Pick<PageProps, "mutate" | "revision" | "busy"> & { jobId: string; facts: Fact[] }) {
  const { data: versions, error } = useResource<Resume[]>(jobPath(jobId) + "/resumes", revision);
  const { data: originals, error: originalError } = useResource<Upload[]>("/api/profile/uploads", revision);
  const [selected, setSelected] = useState("");
  const [original, setOriginal] = useState("");
  const [letter, setLetter] = useState("");
  const [draft, setDraft] = useState<{ id: string; tex: string }>();
  const [showOriginal, setShowOriginal] = useState(false);
  const [prepared, setPrepared] = useState<Application>();
  const current = versions?.find(version => version.id === selected) ?? versions?.[0];
  const upload = originals?.find(item => item.id === original) ?? originals?.[0];
  const {data: originalText, error: originalTextError} = useResource<{text: string}>(
    showOriginal && upload ? "/api/profile/uploads/" + upload.id + "/text" : null);
  const excerpts = upload ? [...new Set(facts.filter(fact => fact.source === "upload:" + upload.id).map(fact => fact.excerpt).filter(Boolean))] : [];
  const claims = new Map((current?.report.claims ?? []).flatMap(value => {
    if (!value || typeof value !== "object" || !("id" in value) || !("value" in value)) return [];
    return [[String(value.id), display(value.value)] as const];
  }));
  return <>
    <div className="split-grid studio-top">
      <Panel title="Generate tailored resume" caption="Uses the server’s configured model, verified facts, and LaTeX pipeline.">
        <form className="stack" onSubmit={async event => {
          event.preventDefault();
          const form = new FormData(event.currentTarget);
          const result = await mutate<Resume>(jobPath(jobId) + "/resumes", "POST",
            { template: form.get("template"), instructions: String(form.get("instructions")).trim(), parent_id: current?.id ?? null }, "Tailored resume compiled.");
          if (result) setSelected(result.id);
        }}>
          <label>Template<select name="template"><option value="classic">Classic</option><option value="compact">Compact</option></select></label>
          <label>Tailoring instructions<textarea name="instructions" rows={2} maxLength={1200}/></label>
          <Button type="submit" disabled={busy}><FilePlus2 size={16}/> Generate resume</Button>
        </form>
      </Panel>
      <Panel title="Version history">
        <ErrorNotice message={error}/>{!versions && !error && <Loading/>}
        {versions?.length ? <label>Compiled version<select value={current?.id} onChange={event => setSelected(event.target.value)}>
          {versions.map(version => <option value={version.id} key={version.id}>{label(version.template)} · {date(version.created)} · {version.id.slice(0, 7)}</option>)}
        </select></label> : versions && <Empty>No resume versions for this role.</Empty>}
        <Button variant="outline" disabled={busy} onClick={async () => {
          const result = await mutate<{content: string}>(jobPath(jobId) + "/letter");
          if (result) setLetter(result.content);
        }}>Generate cover letter</Button>
        {letter && <p className="preserve">{letter}</p>}
      </Panel>
    </div>
    {current && <>
      <Panel title="PDF preview" caption={current.parent_id ? "Derived from version " + current.parent_id.slice(0, 7) : "Initial version"}>
        <div className="inline">
          <Button asChild variant="outline"><a href={resumeUrl(current.id, "pdf", true)}><Download size={16}/> Download PDF</a></Button>
          <Button asChild variant="outline"><a href={resumeUrl(current.id, "tex", true)}>Download LaTeX</a></Button>
          <Button variant="outline" aria-pressed={showOriginal} onClick={() => setShowOriginal(!showOriginal)}>{showOriginal ? "Hide original comparison" : "Compare original"}</Button>
          <Button variant="outline" disabled={busy} onClick={async () => {
            const result = await mutate<Resume>("/api/resumes/" + current.id + "/restore", "POST", undefined, "Resume restored as a new version.");
            if (result) setSelected(result.id);
          }}>Restore as new version</Button>
        </div>
        <div className={showOriginal ? "split-grid" : ""}>
          {showOriginal && <div className="comparison">
            <ErrorNotice message={originalError ?? originalTextError}/>
            {upload && <><label>Imported original<select value={upload.id} onChange={event => setOriginal(event.target.value)}>{originals?.map(item =>
              <option key={item.id} value={item.id}>{item.name} · {date(item.created)}</option>)}</select></label>
              <a className="text-link" href={"/api/profile/uploads/" + upload.id}>Download original</a></>}
            {originals?.length === 0 && <Empty>Upload an original resume to compare versions.</Empty>}
            {upload && <p className="subtle">Original extracted text appears beside the tailored PDF.</p>}
            {originalText && <pre className="resume-source">{originalText.text}</pre>}
            {!originalText && !!excerpts.length && <ul className="bullets original-excerpts">{excerpts.map(excerpt => <li key={excerpt}>{excerpt}</li>)}</ul>}
          </div>}
          <iframe title="Tailored resume PDF" className="pdf" key={current.id} src={resumeUrl(current.id)}/>
        </div>
        <details><summary>Adjust LaTeX and compile a new version</summary><form className="stack" onSubmit={async event => {
          event.preventDefault();
          const result = await mutate<Resume>("/api/resumes/" + current.id + "/compile", "POST", {tex: draft?.id === current.id ? draft.tex : current.tex}, "Edited resume compiled.");
          if (result) {setSelected(result.id); setDraft(undefined);}
        }}>
          <label>LaTeX source<textarea className="code-label" rows={12} required maxLength={70000}
            value={draft?.id === current.id ? draft.tex : current.tex} onChange={event => setDraft({id: current.id, tex: event.target.value})}/></label>
          <p className="subtle">The compiler permits margin adjustments. Edit verified facts in Profile.</p>
          <Button disabled={busy} type="submit" variant="outline">Compile changes</Button>
        </form></details>
      </Panel>
      <Panel title="Evidence-backed changes">
        {current.report.bullets?.length ? <ul className="entries evidence-list">{current.report.bullets.map((bullet, index) => {
          if (!bullet || typeof bullet !== "object" || !("text" in bullet) || !("fact_id" in bullet)) return null;
          return <li key={index}><div><strong>{display(bullet.text)}</strong><small>Verified source · {claims.get(String(bullet.fact_id)) ?? "Unavailable"}</small>
            {"reason" in bullet && <small>{display(bullet.reason)}</small>}
            {"skills" in bullet && Array.isArray(bullet.skills) && bullet.skills.length > 0 && <small>Matching skills · {bullet.skills.join(", ")}</small>}</div></li>;
        })}</ul> : <Empty>This version has no separately recorded bullet changes.</Empty>}
        <details><summary>Validation and quality report</summary><Details values={Object.fromEntries(Object.entries(current.report).filter(([key]) => !["claims", "bullets"].includes(key)))}/></details>
      </Panel>
      <Panel title="Prepare application" caption="Prepare the selected version for review.">
        <Button disabled={busy} onClick={async () => {
          const result = await mutate<Application>(jobPath(jobId) + "/prepare", "POST", {resume_id: current.id}, "Application preparation saved.");
          if (result) setPrepared(result);
        }}>Prepare selected version</Button>
        {prepared && <div className="inline"><Status value={prepared.review_status}/><Link className="text-link" to={"/approvals?app=" + prepared.id}>Open application review</Link></div>}
      </Panel>
    </>}
  </>;
}
