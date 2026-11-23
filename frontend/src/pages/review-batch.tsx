import { Button } from "@/components/ui/button";
import { resumeUrl } from "../api";
import type { Review } from "../api";
import { Details, Modal } from "../shared";
import type { Mutate } from "../shared";

export function ReviewBatch({ action, reviews, busy, mutate, close, complete }: {
  action: "approve" | "reject";
  reviews: Review[];
  busy: boolean;
  mutate: Mutate;
  close: () => void;
  complete: () => void;
}) {
  const approving = action === "approve";
  return <Modal title={approving ? "Confirm selected submissions" : "Confirm selected rejections"} close={close}>
    <p>{approving ? "Confirm final approval for each exact application below." : "Reject these exact prepared applications."}</p>
    <ol className="bullets">{reviews.map(review => <li key={review.application.id}>
      <strong>{review.job.role} · {review.job.company}</strong>
      <Details values={{ destination: review.payload.destination, provider: review.payload.provider,
        eligibility: review.payload.eligibility, "resume version": review.resume.id, "payload hash": review.payload_hash }}/>
      <a className="text-link" href={resumeUrl(review.resume.id)} target="_blank" rel="noreferrer">Preview selected PDF</a>
      <details><summary>Fields and screening answers</summary><Details values={review.payload.fields ?? {}}/><Details values={review.payload.saved_answers ?? {}}/></details>
    </li>)}</ol>
    <Button disabled={busy || !reviews.length || (approving && reviews.some(review => !review.approvable || review.payload.pending?.length))}
      onClick={async () => {
        const result = await mutate(approving ? "/api/applications/bulk-review" : "/api/applications/bulk-reject", "POST", {
          reviews: reviews.map(review => ({application_id: review.application.id, payload_hash: review.payload_hash})),
        }, approving ? "Final approvals recorded. Selected submissions are queued." : "Selected applications rejected.");
        if (result) complete();
      }}>{approving ? "Approve & submit selected" : "Reject selected applications"}</Button>
  </Modal>;
}
