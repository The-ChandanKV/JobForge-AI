import { useState } from "react";
import { Button } from "@/components/ui/button";
import { officialUrl } from "../api";
import { date, label } from "../domain";
import { Empty, ErrorNotice, Loading, Panel, Status, useResource } from "../shared";
import type { PageProps } from "../shared";

type Group = "regular" | "priority" | "excluded";
type Employer = {key: string; company: string; provider: string; board: string; industry: string; careers: string;
  roles: string; locations: string; enabled: boolean; group: Group; verified_at: string | null; can_enable: boolean; preference_overlap: number; preview: Preview | null};
type Preview = {complete: boolean; endpoint: string; listing_count: number; jobs: {role: string; location: string; url: string}[]};

export function EmployerDirectory({ busy, mutate, revision }: PageProps) {
  const [filters, setFilters] = useState("");
  const [selected, setSelected] = useState<string[]>([]);
  const [failures, setFailures] = useState<Record<string, string>>({});
  const [previews, setPreviews] = useState<Record<string, Preview>>({});
  const {data, error} = useResource<Employer[]>("/api/employers" + filters, revision);
  const chosen = data?.filter(employer => selected.includes(employer.key) && !employer.enabled && employer.group !== "excluded") ?? [];
  const suggested = data?.filter(employer => !employer.enabled && employer.group !== "excluded" && employer.preference_overlap > 0).slice(0, 5) ?? [];
  return <Panel title="Discover employers" caption="Search the employer directory, verify the live source, and choose whether to monitor it.">
    <form className="toolbar" onSubmit={event => {
      event.preventDefault();
      const values = [...new FormData(event.currentTarget)].map(([key, value]) => [key, String(value).trim()]);
      setSelected([]);
      setFilters("?" + new URLSearchParams(values).toString());
    }}>
      {["company", "industry", "location", "role"].map(name => <label key={name}>{label(name)}<input name={name} maxLength={100}/></label>)}
      <Button type="submit" variant="outline">Discover employers</Button>
    </form>
    <div className="inline">
      {suggested.length > 0 && <Button size="sm" variant="outline" disabled={busy}
        onClick={() => setSelected(suggested.map(employer => employer.key))}>Select up to five suggested boards</Button>}
      {!!chosen.length && <>
        <strong>{chosen.length} selected</strong>
        <Button size="sm" variant="outline" disabled={busy} onClick={async () => {
          const result = await mutate<Record<string, Preview | {error: string}>>("/api/employers/verify-selected", "POST",
            {keys: chosen.map(row => row.key)});
          if (!result) return;
          const valid: Record<string, Preview> = {};
          const invalid: Record<string, string> = {};
          for (const [key, value] of Object.entries(result)) {
            if ("error" in value) invalid[key] = value.error;
            else valid[key] = value;
          }
          setFailures(invalid);
          setPreviews(previous => ({...previous, ...valid}));
        }}>Verify selected and preview jobs</Button>
        <Button size="sm" disabled={busy || chosen.some(employer => !employer.can_enable)} onClick={async () => {
          const result = await mutate<{enabled: number}>("/api/employers/enable-selected", "POST",
            {keys: chosen.map(row => row.key)}, "Selected verified boards enabled.");
          if (result) setSelected([]);
        }}>Enable selected verified boards</Button>
      </>}
    </div>
    <ErrorNotice message={error}/>
    {!data && !error && <Loading/>}
    {data?.length === 0 && <Empty>No directory entries match those filters.</Empty>}
    <div className="fact-list">{data?.map(employer => {
      const preview = previews[employer.key] ?? employer.preview;
      return <article className="fact" key={employer.key}>
      {!employer.enabled && employer.group !== "excluded" && <label className="check"><input type="checkbox"
        checked={selected.includes(employer.key)} disabled={busy || (selected.length >= 10 && !selected.includes(employer.key))}
        onChange={event => setSelected(previous => event.target.checked ? [...previous, employer.key] : previous.filter(key => key !== employer.key))}/>
        Select {employer.company}</label>}
      <strong>{employer.company}</strong><p className="subtle">{employer.industry} · {label(employer.provider)}</p>
      <p className="subtle">{employer.locations} · {employer.roles}</p>
      <div className="inline"><a className="text-link" href={employer.careers} target="_blank" rel="noreferrer">Employer careers</a>
        <Status value={employer.enabled ? "Monitoring enabled" : employer.verified_at ? "Verified " + date(employer.verified_at) : "Verification required"}/></div>
      <div className="inline">
        <Button size="sm" variant="outline" disabled={busy} onClick={async () => {
          const result = await mutate<Preview>("/api/employers/" + employer.key + "/verify", "POST", undefined, "Public source verified.");
          if (result) setPreviews(previous => ({...previous, [employer.key]: result}));
        }}>Verify source and preview jobs</Button>
        <Button size="sm" variant="outline" disabled={busy || (!employer.enabled && (!employer.can_enable))}
          onClick={() => void mutate("/api/employers/" + employer.key + "/monitor", "PUT",
            {enabled: !employer.enabled, group: employer.group}, employer.enabled ? "Monitoring disabled." : "Monitoring enabled.")}>
          {employer.enabled ? "Disable monitoring" : "Enable monitoring"}</Button>
        <label>Employer group<select value={employer.group} disabled={busy} onChange={event => {
          const group = event.target.value as Group;
          void mutate("/api/employers/" + employer.key + "/monitor", "PUT",
            {enabled: employer.enabled && group !== "excluded", group}, "Employer group saved.");
        }}><option value="regular">Regular</option><option value="priority">Priority</option><option value="excluded">Excluded</option></select></label>
      </div>
      <ErrorNotice message={failures[employer.key]}/>
      {preview && <p className="subtle">{preview.listing_count} employer postings · {preview.complete ? "Complete" : "Partial"} source check</p>}
      {preview && <details><summary>Preview verified postings</summary><ul className="entries">{preview.jobs.map((job, index) => <li key={index}>
        <a className="text-link" href={officialUrl(job.url)} target="_blank" rel="noreferrer">{job.role}</a><small>{job.location}</small>
      </li>)}</ul></details>}
    </article>;})}</div>
  </Panel>;
}
