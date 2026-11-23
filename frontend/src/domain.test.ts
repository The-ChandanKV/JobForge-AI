import { describe, expect, it } from "vitest";
import type { Application, Job } from "./api";
import { awaitsReview, evidence, isApplicationException, stage } from "./domain";

const job: Job = {
  id: "j1", role: "Developer", company: "Example", available: true, status: "RESUME_READY",
  created: "", verified: "", match: {}, automation: {},
};
const application: Application = {
  id: "a1", job_id: job.id, resume_id: "r1", mode: "ASSISTED", created: "",
  status: "APPLICATION_PREPARED", review_status: "READY_FOR_REVIEW", confirmation: null, summary: {},
};

describe("persisted workflow", () => {
  it("maps job and canonical review status independently", () => {
    expect(stage(job)).toBe("Resume Ready");
    expect(stage(job, application)).toBe("Awaiting Review");
    expect(awaitsReview(application)).toBe(true);
    const uncertain = {...application, review_status: "SUBMISSION_UNCERTAIN"};
    expect(stage(job, uncertain)).toBe("Failed");
    expect(isApplicationException(uncertain)).toBe(true);
    expect(awaitsReview(uncertain)).toBe(false);
    const manual = {...application, summary: {exception: "Manual employer handoff"}};
    expect(isApplicationException(manual)).toBe(true);
    expect(isApplicationException({...manual, review_status: "SUBMITTED"})).toBe(false);
  });

  it("distinguishes evidence by source", () => {
    const confirmed = {...application, confirmation: "reference"};
    expect(evidence(application)).toBe("No verified receipt");
    expect(evidence(confirmed)).toBe("Provider verification");
    expect(evidence({...confirmed, summary: {external_confirmation: true}})).toBe("User-recorded employer confirmation");
    expect(evidence({...confirmed, summary: {simulation: true}})).toBe("Simulation receipt");
  });
});
