import { useState } from "react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { date, label } from "../domain";
import { Details, ErrorNotice, Heading, Loading, Panel, Status, useResource } from "../shared";
import type { PageProps } from "../shared";
import { EmployerDirectory } from "./employers";
import { suggestedRoles } from "./settings";

type ActivationSummary = {
  checks: Record<string, boolean>;
  ready: boolean;
  verified_enabled_boards: number;
  enabled_boards: number;
  limit: number;
  next_run: string | null;
  latest_run: {
    status: string; finished: string | null; selected: number;
    scanned: number; discovered: number; eligible: number; compiled: number; prepared: number;
    errors: string[];
  } | null;
};

const list = (value: FormDataEntryValue | null) => String(value ?? "").split(",").map(item => item.trim()).filter(Boolean);

export function Activation(props: PageProps) {
  const {data, error} = useResource<ActivationSummary>("/api/activation", props.revision);
  const preferences = props.state.profile.preferences;
  const saved = (key: string) => Array.isArray(preferences[key]) ? preferences[key] : [];
  const [roles, setRoles] = useState<string>();
  const latest = data?.latest_run;
  return <div className="content-grid">
    <Heading title="Activate JobForge" description="Review your resume evidence, save your search preferences, and enable verified employer boards."/>
    <Panel title="Activation checklist">
      <ErrorNotice message={error}/>
      {!data && !error && <Loading/>}
      {data && <>
        <Status value={data.ready ? "Ready for first real preparation" : "Setup required"}/>
        <Details values={Object.fromEntries(Object.entries(data.checks).map(([key, ready]) => [key, ready ? "Complete" : "Required"]))}/>
        <p>{data.verified_enabled_boards} verified boards enabled · Next scheduled run {date(data.next_run, props.state.options.timezone)}</p>
      </>}
      <Link className="text-link" to="/profile?review=1">Review existing resume facts or import an original</Link>
    </Panel>
    <Panel title="Search preferences" caption="These choices apply to every future run. Add locations, or explicitly allow remote work.">
      <form className="stack" onSubmit={async event => {
        event.preventDefault();
        const form = new FormData(event.currentTarget);
        await props.mutate("/api/activation/preferences", "PUT", {
          roles: list(form.get("roles")), locations: list(form.get("locations")),
          work_modes: form.getAll("mode"), employment: list(form.get("employment")),
        }, "Search preferences saved.");
      }}>
        <div className="form-grid">
          <label>Target roles<input name="roles" value={roles ?? saved("roles").join(", ")} onChange={event => setRoles(event.target.value)} required/></label>
          <label>Preferred locations<input name="locations" defaultValue={saved("locations").join(", ")}/></label>
          <label>Employment types<input name="employment" defaultValue={saved("employment").join(", ")} placeholder="Full-time, internship"/></label>
        </div>
        <fieldset><legend>Work modes</legend><div className="inline">{["remote", "hybrid", "onsite"].map(mode =>
          <label className="check" key={mode}><input type="checkbox" name="mode" value={mode} defaultChecked={saved("work_modes").includes(mode)}/>{label(mode)}</label>
        )}</div></fieldset>
        <div className="inline">
          <Button type="button" variant="outline" onClick={() => setRoles(suggestedRoles.join(", "))}>Use editable software role suggestions</Button>
          <Button type="submit" disabled={props.busy}>Save search preferences</Button>
          <Link className="text-link" to="/profile">Edit salary, employer, experience and exclusions</Link>
        </div>
      </form>
    </Panel>
    <EmployerDirectory {...props}/>
    <Panel title="First real preparation">
      <p>The first run checks verified enabled boards and reserves up to {data?.limit ?? 5} qualifying jobs for preparation. Final submission stays disabled.</p>
      <Button disabled={!data?.ready || props.busy || props.state.worker.pending > 0} onClick={() => void props.mutate(
        "/api/activation/run", "POST", undefined, "First real preparation run queued.")
      }>Run first real preparation</Button>
      {latest && <>
        <Details values={{ status: label(latest.status), finished: date(latest.finished, props.state.options.timezone), scanned: latest.scanned,
          discovered: latest.discovered, "eligibility checks passed": latest.eligible, selected: latest.selected,
          "compiled PDFs": latest.compiled, "prepared applications": latest.prepared }}/>
        {!!latest.errors.length && <ul className="bullets">{latest.errors.map((item, index) => <li key={index}>{item}</li>)}</ul>}
      </>}
      <div className="inline"><Link className="text-link" to="/automation">View worker and run history</Link>
        <Link className="text-link" to="/approvals">Open Approval Queue</Link></div>
    </Panel>
  </div>;
}
