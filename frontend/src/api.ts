export interface Fact {
  id: string;
  category: string;
  label: string;
  value: string;
  verified: boolean;
  unsupported?: boolean;
  prioritized?: boolean;
  source: string;
  excerpt: string;
}

export type Preferences = Record<string, string[] | string | number | boolean | null>;
export type Profile = { facts: Fact[]; preferences: Preferences };
export type Source = { provider: string; board: string; company: string; enabled: boolean };
export interface Options {
  enabled: boolean;
  interval_minutes: number;
  min_match_score: number;
  max_applications_per_day: number;
  max_submissions_per_day: number;
  max_resume_generations_per_run: number;
  max_job_attempts: number;
  notification_interval_minutes: number;
  retry_failed_jobs: boolean;
  exception_notifications: boolean;
  desktop_notifications: boolean;
  approval_email: boolean;
  require_approval: true;
  dry_run: boolean;
  mode: string;
  automation_mode: string;
  provider: string | null;
  model: string;
  timezone: string;
  sources: Source[];
}

export interface Match {
  eligibility?: string;
  match_score?: number;
  recommendation?: string;
  reason?: string;
  matching_skills?: string[];
  required_skills?: string[];
  missing_skills?: string[];
  preferred_skills?: string[];
  concerns?: string[];
  components?: Record<string, number>;
  requirement_evidence?: Record<string, string[]>;
}

export interface Job {
  id: string;
  role: string;
  company: string;
  location?: string;
  source?: string;
  work_mode?: string;
  employment?: string;
  url?: string;
  apply_url?: string;
  description?: string;
  posted?: string | null;
  deadline?: string | null;
  available: boolean;
  status: string;
  created: string;
  verified: string;
  match: Match;
  automation: { state?: string; attempts?: number; next_retry?: string; reason?: string; stage?: string };
}

export interface Application {
  id: string;
  job_id: string;
  resume_id: string;
  mode: string;
  status: string;
  review_status: string;
  submission_method?: string;
  confirmation: string | null;
  created: string;
  summary: {
    simulation?: boolean;
    external_confirmation?: boolean;
    confirmed_at?: string;
    missing?: string[];
    exception?: string;
    checkpoint?: string;
    integration?: string;
    reason?: string;
    note?: string;
  };
}

export interface Notice {
  id: string;
  kind: string;
  message: string;
  read: boolean;
  count: number;
  created: string;
}

export interface Run {
  id: string;
  status: string;
  trigger: string;
  started: string | null;
  finished: string | null;
  canceled: boolean;
  attempts: number;
  created: string;
  report: { scanned?: number; filtered?: number; discovered?: number; compiled?: number; prepared?: number; error?: string };
}

export interface State {
  profile: Profile;
  profile_readiness: { ready: boolean; checks: Record<string, boolean> };
  options: Options;
  provider: string;
  model: string;
  authorized_board: string | null;
  worker: { status: string; last_heartbeat: string | null; last_success: string | null; pending: number; model: Record<string, unknown> };
  daily: Record<string, number>;
  resume_count: number;
  unread_notifications: number;
  next_run: string | null;
  jobs: Job[];
  applications: Application[];
  runs: Run[];
  logs: { id: string; kind: string; message: string; created: string; detail: Record<string, unknown> }[];
}

export interface Resume {
  id: string;
  parent_id: string | null;
  template: string;
  created: string;
  tex: string;
  report: { bullets?: unknown[]; claims?: unknown[]; [key: string]: unknown };
}

export interface Review {
  application: Application;
  job: Job;
  payload: {
    provider?: string;
    eligibility?: string;
    fields?: Record<string, unknown>;
    saved_answers?: Record<string, string>;
    pending?: string[];
    cover_letter?: string;
    prepared_at?: string;
    destination?: string;
  };
  payload_hash: string | null;
  resume: Pick<Resume, "id" | "template" | "created">;
  original_description: string | null;
  readiness: string;
  approvable: boolean;
  refusal: string | null;
  task: { status: string; result?: string; provider?: string; approved_at?: string; attempted_at?: string; finished_at?: string; preflight_attempts?: number } | null;
}

export type Event = { status: string; message: string; created: string };
export type Upload = { id: string; name: string; created: string };

export async function request<T>(path: string, method = "GET", body?: unknown, signal?: AbortSignal): Promise<T> {
  const form = body instanceof FormData;
  const response = await fetch(path, {
    method,
    credentials: "same-origin",
    signal,
    headers: body === undefined || form ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : form ? body : JSON.stringify(body),
  });
  if (!response.ok) {
    if (response.status === 401) window.location.reload();
    const result = await response.json().catch(() => ({}));
    throw new Error(typeof result.detail === "string" ? result.detail : "Request failed (" + response.status + ").");
  }
  return response.json();
}

export const resumeUrl = (id: string, format: "pdf" | "tex" = "pdf", download = false) =>
  "/api/resumes/" + id + "/" + format + (download ? "?download=true" : "");

export const jobPath = (id: string) => "/api/jobs/" + id;
export const appPath = (id: string) => "/api/applications/" + id;

export function officialUrl(value?: string) {
  if (!value) return;
  try {
    const url = new URL(value);
    if (url.protocol === "https:" || url.protocol === "http:") return url.href;
  } catch { return; }
}
