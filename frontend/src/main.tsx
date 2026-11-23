import { useCallback, useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Link, NavLink, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import {
  Activity, Bell, Briefcase, ChartNoAxesCombined, CircleCheck, ClipboardList, Database, FileText,
  GitBranch, History, LayoutDashboard, Menu, Moon, PanelLeft, Search, Settings as Gear, ShieldAlert, Sun, UserRound, X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { request } from "./api";
import type { State } from "./api";
import { awaitsReview, initials, isApplicationException, isJobException, label, searchMatch } from "./domain";
import { Empty, ErrorNotice, Feedback, Loading, Modal } from "./shared";
import type { Mutate, PageProps } from "./shared";
import { Analytics, Overview } from "./pages/overview";
import { JobIntelligence } from "./pages/intelligence";
import { Jobs } from "./pages/jobs";
import { Pipeline } from "./pages/pipeline";
import { Studio } from "./pages/studio";
import { Automation, Notifications } from "./pages/automation";
import { ProfilePage, Settings } from "./pages/settings";
import "./lovable.css";
import "./workspace.css";

const workspace = [
  {path: "/", name: "Overview", Icon: LayoutDashboard},
  {path: "/jobs", name: "Job discovery", Icon: Briefcase},
  {path: "/intelligence", name: "Job Intelligence", Icon: Briefcase},
  {path: "/pipeline", name: "Pipeline", Icon: GitBranch},
  {path: "/resume-studio", name: "Resume Studio", Icon: FileText},
  {path: "/history", name: "History", Icon: History},
  {path: "/analytics", name: "Analytics", Icon: ChartNoAxesCombined},
];
const operations = [
  {path: "/automation", name: "Automation", Icon: Activity},
  {path: "/approvals", name: "Approval queue", Icon: ClipboardList},
  {path: "/exceptions", name: "Exceptions", Icon: ShieldAlert},
];
const personal = [
  {path: "/settings", name: "Settings", Icon: Gear},
  {path: "/profile", name: "Profile", Icon: UserRound},
  {path: "/notifications", name: "Notifications", Icon: Bell},
];
const navigation = [...workspace, ...operations, ...personal];

function App() {
  const [state, setState] = useState<State>();
  const [connectionError, setConnectionError] = useState("");
  const [feedback, setFeedback] = useState({error: "", success: ""});
  const [revision, setRevision] = useState(0);
  const [busy, setBusy] = useState(false);
  const [dark, setDark] = useState(() => localStorage.getItem("jobforge-theme") !== "light");
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [command, setCommand] = useState(false);
  const sequence = useRef(0);
  const pending = useRef(false);
  const { pathname, search } = useLocation();
  const nav = useNavigate();
  const title = navigation.find(item => item.path === pathname)?.name;
  const refresh = useCallback(async (signal?: AbortSignal) => {
    const current = ++sequence.current;
    try {
      const result = await request<State>("/api/state", "GET", undefined, signal);
      if (signal?.aborted || current !== sequence.current) return;
      setState(result);
      setConnectionError("");
      setRevision(value => value + 1);
    } catch (error) {
      if (!signal?.aborted && current === sequence.current) setConnectionError((error as Error).message);
    }
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    void refresh(controller.signal);
    const interval = window.setInterval(() => {
      if (!pending.current && !document.hidden) void refresh(controller.signal);
    }, 15000);
    return () => {controller.abort(); window.clearInterval(interval);};
  }, [refresh]);
  useEffect(() => {
    document.documentElement.dataset.theme = dark ? "dark" : "light";
    localStorage.setItem("jobforge-theme", dark ? "dark" : "light");
  }, [dark]);
  useEffect(() => {
    document.title = title ? title + " · JobForge AI" : "JobForge AI";
  }, [title]);
  useEffect(() => {
    function keys(event: KeyboardEvent) {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setCommand(value => !value);
      }
      if (event.key === "Escape") setMobileOpen(false);
    }
    window.addEventListener("keydown", keys);
    return () => window.removeEventListener("keydown", keys);
  }, []);
  useEffect(() => {
    setFeedback({error: "", success: ""});
  }, [pathname]);
  useEffect(() => {
    if (!feedback.success) return;
    const timeout = window.setTimeout(() => setFeedback(previous => ({...previous, success: ""})), 5500);
    return () => window.clearTimeout(timeout);
  }, [feedback.success]);

  const mutate: Mutate = async <T,>(path: string, method = "GET", body?: unknown, message?: string) => {
    if (pending.current) return;
    pending.current = true;
    setBusy(true);
    setFeedback({error: "", success: ""});
    try {
      const result = await request<T>(path, method, body);
      if (method !== "GET") await refresh();
      if (message) setFeedback({error: "", success: message});
      return result;
    } catch (error) {
      setFeedback({error: (error as Error).message, success: ""});
      return undefined;
    } finally {
      pending.current = false;
      setBusy(false);
    }
  };
  const props: PageProps | undefined = state ? {state, revision, mutate, busy} : undefined;
  const currentName = state?.profile.facts.find(fact => fact.category === "personal" && fact.label.toLowerCase() === "name" && fact.verified)?.value;
  const counts: Record<string, number> = {
    "/approvals": state?.applications.filter(awaitsReview).length ?? 0,
    "/exceptions": new Set([...(state?.jobs.filter(isJobException).map(job => job.id) ?? []), ...(state?.applications.filter(isApplicationException).map(item => item.job_id) ?? [])]).size,
  };

  function openCommand() { setCommand(true); }
  function choose(path: string) {setCommand(false); setMobileOpen(false); nav(path);}
  function group(items: typeof workspace, caption: string) {
    return <><div className="nav-caption">{caption}</div><div className="nav-list">{items.map(({path, name, Icon}) =>
      <NavLink to={path} end key={path} className="nav-link" onClick={() => setMobileOpen(false)} title={name}>
        <Icon/><span className="nav-name">{name}</span>{counts[path] > 0 && <span className="nav-count">{counts[path]}</span>}
      </NavLink>
    )}</div></>;
  }

  return <Feedback.Provider value={feedback}>
    <a href="#workspace" className="skip-link">Skip to content</a>
    <div className={"app-shell" + (collapsed ? " collapsed" : "")}>
      <button type="button" tabIndex={mobileOpen ? 0 : -1} aria-label="Close navigation" className={"mobile-backdrop" + (mobileOpen ? " open" : "")} onClick={() => setMobileOpen(false)}/>
      <aside className={"app-sidebar" + (mobileOpen ? " open" : "")} aria-label="Sidebar">
        <Link className="brand-lockup" to="/" onClick={() => setMobileOpen(false)} aria-label="JobForge AI home"><span className="brand-mark"><GitBranch size={18}/></span><span className="brand-name">JobForge <span>AI</span></span></Link>
        <nav aria-label="Main navigation">{group(workspace, "Workspace")}{group(operations, "Operations")}{group(personal.slice(0, 1), "Preferences")}</nav>
        <div className="sidebar-spacer"/>
        <div className="sidebar-status">
          <div className="status-line" title="Backend connection"><span className={"status-light " + (connectionError ? "bad" : state ? "good" : "warn")}/><span>{connectionError ? "Backend disconnected" : state ? "Backend connected" : "Connecting to backend"}</span></div>
          <div className="status-line" title="Automation worker"><span className={"status-light " + (state?.worker.status === "RUNNING" ? "good" : "warn")}/><span>Worker {state ? label(state.worker.status).toLowerCase() : "unknown"}</span></div>
        </div>
        <NavLink to="/profile" className="profile-access" title="Candidate profile" onClick={() => setMobileOpen(false)}><span className="profile-avatar">{currentName ? initials(currentName) : <UserRound size={14}/>}</span><span className="profile-label"><strong>{currentName || "Candidate profile"}</strong><span>Personal workspace</span></span></NavLink>
      </aside>
      <div className="app-main">
        <header className="topbar">
          <div className="topbar-title">
            <Button className="mobile-menu-button" variant="ghost" size="icon" aria-label="Open navigation" aria-expanded={mobileOpen} onClick={() => setMobileOpen(!mobileOpen)}><Menu size={19}/></Button>
            <Button className="desktop-menu-button" variant="ghost" size="icon" aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"} aria-expanded={!collapsed} onClick={() => setCollapsed(!collapsed)}><PanelLeft size={17}/></Button>
            <span className="topbar-crumb">Workspace</span><span className="topbar-crumb">/</span><span>{title ?? "JobForge AI"}</span>
          </div>
          <div className="topbar-actions">
            <button type="button" className="topbar-search" aria-label="Search workspace" onClick={openCommand}><Search size={16}/><span className="topbar-search-label">Search workspace</span><kbd className="key-hint">Ctrl K</kbd></button>
            <Button variant="ghost" size="icon" asChild><Link className="notification-button" to="/notifications" aria-label={"Notifications" + (state?.unread_notifications ? " (" + state.unread_notifications + " unread)" : "")}><Bell size={18}/>{!!state?.unread_notifications && <span className="notification-dot"/>}</Link></Button>
            <Button variant="ghost" size="icon" aria-label={dark ? "Switch to light mode" : "Switch to dark mode"} onClick={() => setDark(!dark)}>{dark ? <Sun size={18}/> : <Moon size={18}/>}</Button>
          </div>
        </header>
        <main className="page-wrap" id="workspace" tabIndex={-1}>
          {!!connectionError && <div className="connection-alert"><ErrorNotice message={"Backend unavailable. " + connectionError}/><Button size="sm" variant="outline" onClick={() => void refresh()}><Database size={15}/> Retry connection</Button></div>}
          {!state && !connectionError && <Loading/>}
          {!(pathname !== "/resume-studio" && (new URLSearchParams(search).has("app") || new URLSearchParams(search).has("job"))) && <ErrorNotice message={feedback.error}/>}
          {props && <Routes>
            <Route path="/" element={<Overview {...props}/>}/>
            <Route path="/jobs" element={<Jobs {...props}/>}/>
            <Route path="/intelligence" element={<JobIntelligence {...props}/>}/>
            <Route path="/pipeline" element={<Pipeline key="pipeline" mode="pipeline" {...props}/>}/>
            <Route path="/resume-studio" element={<Studio {...props}/>}/>
            <Route path="/automation" element={<Automation {...props}/>}/>
            <Route path="/approvals" element={<Pipeline key="approvals" mode="approvals" {...props}/>}/>
            <Route path="/exceptions" element={<Pipeline key="exceptions" mode="exceptions" {...props}/>}/>
            <Route path="/history" element={<Pipeline key="history" mode="history" {...props}/>}/>
            <Route path="/analytics" element={<Analytics {...props}/>}/>
            <Route path="/settings" element={<Settings {...props}/>}/>
            <Route path="/profile" element={<ProfilePage {...props}/>}/>
            <Route path="/notifications" element={<Notifications {...props}/>}/>
            <Route path="*" element={<Empty>This workspace page is unavailable. <Link className="text-link" to="/">Return to overview</Link></Empty>}/>
          </Routes>}
        </main>
      </div>
    </div>
    {feedback.success && <div role="status" className="success-toast"><CircleCheck size={18}/><span>{feedback.success}</span>
      <Button variant="ghost" size="icon" aria-label="Dismiss status" onClick={() => setFeedback({...feedback, success:""})}><X size={16}/></Button></div>}
    {command && <Command state={state} close={() => setCommand(false)} choose={choose}/>}
  </Feedback.Provider>;
}

function Command({ state, close, choose }: { state?: State; close: () => void; choose: (path: string) => void }) {
  const [query, setQuery] = useState("");
  const pages = navigation.filter(item => searchMatch(query, item.name));
  const jobs = query.trim() ? state?.jobs.filter(job => searchMatch(query, job.role, job.company, job.location)).slice(0, 6) ?? [] : [];
  const applications = query.trim() ? state?.applications.flatMap(app => {
    const job = state.jobs.find(item => item.id === app.job_id);
    return job && searchMatch(query, job.role, job.company, app.confirmation ?? undefined) ? [{app,job}] : [];
  }).slice(0, 5) ?? [] : [];
  const first = pages[0]?.path ?? (jobs[0] ? "/jobs?job=" + jobs[0].id : applications[0] && "/history?app=" + applications[0].app.id);
  return <Modal title="Search workspace" close={close}>
    <input autoFocus aria-label="Search pages, jobs, and applications" type="search" placeholder="Search pages, jobs, and applications…" value={query} onChange={event => setQuery(event.target.value)}
      onKeyDown={event => {if (event.key === "Enter" && first) {event.preventDefault(); choose(first);}}}/>
    <div className="command-list">
      {pages.map(({path, name, Icon}) => <button className="command-option" type="button" key={path} onClick={() => choose(path)}><Icon size={17}/>{name}</button>)}
      {jobs.map(job => <button className="command-option" type="button" key={job.id} onClick={() => choose("/jobs?job=" + job.id)}><Briefcase size={17}/>{job.role} · {job.company}</button>)}
      {applications.map(({app, job}) => <button className="command-option" type="button" key={app.id} onClick={() => choose("/history?app=" + app.id)}><ClipboardList size={17}/>{job.role} · {job.company} · {label(app.review_status)}</button>)}
      {!first && <Empty>No results match your search.</Empty>}
    </div>
  </Modal>;
}

createRoot(document.getElementById("root")!).render(<BrowserRouter><App/></BrowserRouter>);
