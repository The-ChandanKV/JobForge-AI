import type { Application, Job } from "./api";

export const stages = ["Discovered", "Shortlisted", "Resume Ready", "Preparing", "Awaiting Review", "Submitted", "Interview", "Offer", "Rejected", "Failed"] as const;
export type Stage = typeof stages[number];

const applicationStages: Record<string, Stage> = {
  PREPARING: "Preparing", READY_FOR_REVIEW: "Awaiting Review", NEEDS_MANUAL_ACTION: "Awaiting Review",
  APPROVED: "Awaiting Review", SUBMITTING: "Preparing", SUBMITTED: "Submitted",
  INTERVIEW: "Interview", OFFER: "Offer", REJECTED: "Rejected", REJECTED_BY_USER: "Rejected",
  CLOSED: "Rejected", FAILED: "Failed", SUBMISSION_UNCERTAIN: "Failed",
  SUBMISSION_FAILED: "Failed", SUBMISSION_BLOCKED: "Failed",
};

export function stage(job: Job, application?: Application): Stage {
  if (application && applicationStages[application.review_status]) return applicationStages[application.review_status];
  if (isJobException(job)) return "Failed";
  if (job.status === "RESUME_READY") return "Resume Ready";
  if (job.status === "SHORTLISTED") return "Shortlisted";
  if (job.status === "SKIPPED" || job.status === "CLOSED") return "Rejected";
  return "Discovered";
}

export const isJobException = (job: Job) => ["EXCEPTION", "RETRY_WAIT"].includes(job.automation.state ?? "");
export const needsEligibilityReview = (job: Job) => job.available && job.match.eligibility === "NEEDS_REVIEW"
  && !["SKIPPED", "CLOSED"].includes(job.status);
export const awaitsReview = (app: Application) => ["READY_FOR_REVIEW", "NEEDS_MANUAL_ACTION"].includes(app.review_status);
export const isApplicationException = (app: Application) =>
  ["NEEDS_MANUAL_ACTION", "FAILED", "SUBMISSION_UNCERTAIN", "SUBMISSION_FAILED", "SUBMISSION_BLOCKED"].includes(app.review_status)
  || (awaitsReview(app) && Boolean(app.summary.exception));

export function evidence(app: Application) {
  if (app.summary.simulation) return app.confirmation ? "Simulation receipt" : "Simulation";
  if (app.summary.external_confirmation) return "User-recorded employer confirmation";
  if (app.confirmation) return "Provider verification";
  return "No verified receipt";
}

export function label(value?: string | null) {
  return value ? value.toLowerCase().replaceAll("_", " ").replace(/^./, (letter) => letter.toUpperCase()) : "Unavailable";
}

export function date(value?: string | null, timezone?: string) {
  if (!value || !Number.isFinite(Date.parse(value))) return "—";
  return new Date(value).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short", timeZone: timezone });
}

export function display(value: unknown): string {
  if (value == null) return "—";
  if (typeof value === "string") return value;
  if (typeof value === "object") return JSON.stringify(value, null, 2);
  return String(value);
}

export const initials = (name: string) => name.trim().split(/\s+/).slice(0, 2).map(part => part[0]).join("").toUpperCase();
export const searchMatch = (query: string, ...fields: (string | undefined)[]) =>
  fields.some((field) => field?.toLowerCase().includes(query.trim().toLowerCase()));
