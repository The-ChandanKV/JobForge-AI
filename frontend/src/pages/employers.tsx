import { useState } from "react";
import { Button } from "@/components/ui/button";
import { officialUrl } from "../api";
import { date, label } from "../domain";
import { Empty, ErrorNotice, Loading, Panel, Status, useResource } from "../shared";
import type { PageProps } from "../shared";

type Group = "regular" | "priority" | "excluded";
type Employer = {key: string; company: string; provider: string; board: string; industry: string; careers: string;
  roles: string; locations: string; enabled: boolean; group: Group; verified_at: string | null};
type Preview = {complete: boolean; jobs: {role: string; location: string; url: string}[]};

export function EmployerDirectory({ busy, mutate, revision }: PageProps) {
  const [filters, setFilters] = useState("");
  const [previews, setPreviews] = useState<Record<string, Preview>>({});
  const {data, error} = useResource<Employer[]>("/api/employers" + filters, revision);
  return <Panel title="Discover employers" caption="Search the employer directory, verify the live source, and choose whether to monitor it.">
    <form className="toolbar" onSubmit={event => {
      event.preventDefault();
      const values = [...new FormData(event.currentTarget)].map(([key, value]) => [key, String(value).trim()]);
      setFilters("?" + new URLSearchParams(values).toString());
    }}>
      {["company", "industry", "location", "role"].map(name => <label key={name}>{label(name)}<input name={name} maxLength={100}/></label>)}
      <Button type="submit" variant="outline">Discover employers</Button>
    </form>
    <ErrorNotice message={error}/>
    {!data && !error && <Loading/>}
    {data?.length === 0 && <Empty>No directory entries match those filters.</Empty>}
    <div className="fact-list">{data?.map(employer => <article className="fact" key={employer.key}>
      <strong>{employer.company}</strong><p className="subtle">{employer.industry} · {label(employer.provider)}</p>
      <p className="subtle">{employer.locations} · {employer.roles}</p>
      <div className="inline"><a className="text-link" href={employer.careers} target="_blank" rel="noreferrer">Employer careers</a>
        <Status value={employer.enabled ? "Monitoring enabled" : employer.verified_at ? "Verified " + date(employer.verified_at) : "Verification required"}/></div>
      <div className="inline">
        <Button size="sm" variant="outline" disabled={busy} onClick={async () => {
          const result = await mutate<Preview>("/api/employers/" + employer.key + "/verify", "POST", undefined, "Public source verified.");
          if (result) setPreviews(previous => ({...previous, [employer.key]: result}));
        }}>Verify source and preview jobs</Button>
        <Button size="sm" variant="outline" disabled={busy || (!employer.enabled && (!employer.verified_at || employer.group === "excluded"))}
          onClick={() => void mutate("/api/employers/" + employer.key + "/monitor", "PUT",
            {enabled: !employer.enabled, group: employer.group}, employer.enabled ? "Monitoring disabled." : "Monitoring enabled.")}>
          {employer.enabled ? "Disable monitoring" : "Enable monitoring"}</Button>
        <label>Employer group<select value={employer.group} disabled={busy} onChange={event => {
          const group = event.target.value as Group;
          void mutate("/api/employers/" + employer.key + "/monitor", "PUT",
            {enabled: employer.enabled && group !== "excluded", group}, "Employer group saved.");
        }}><option value="regular">Regular</option><option value="priority">Priority</option><option value="excluded">Excluded</option></select></label>
      </div>
      {previews[employer.key] && <ul className="entries">{previews[employer.key].jobs.map((job, index) => <li key={index}>
        <a className="text-link" href={officialUrl(job.url)} target="_blank" rel="noreferrer">{job.role}</a><small>{job.location}</small>
      </li>)}</ul>}
    </article>)}</div>
  </Panel>;
}
