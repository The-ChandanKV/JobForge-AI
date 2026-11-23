# Matching engine

Hard eligibility uses deterministic rules and verified facts. The workspace distinguishes eligible, ineligible, and needs review. Requirements expressed as named alternatives count as one group when the statement is unambiguous. Rules retain unknown work authorization, location, degree and experience requirements for review. Configured preferences, dated freshness, and eligibility stay separate from the relevance score.

The hourly queue ranks eligible openings by relevance and then considers priority employers, verified posting freshness and deadlines, and bounded recommendation feedback for the same company and title. **Already applied**, **Not interested**, and **Wrong experience level** prevent unattended reprocessing of that job. Feedback never edits the verified profile or filing state.

Settings accepts separate local models for semantic ranking and tailoring. Semantic ranking is optional and runs only on a bounded shortlist of up to three outstanding qualifying jobs, with a cached key for model, posting and verified evidence. The strict 0–10 output can add at most two queue-order points. It cannot establish eligibility, change the threshold, or authorize a submission. An unavailable or invalid model leaves the deterministic order in place. The existing Ollama evidence selector returns verified fact IDs. The feature never silently selects a paid provider. [Ollama structured outputs](https://docs.ollama.com/capabilities/structured-outputs)

## Installed hardware and benchmark

The Windows host reported an Intel i5-1145G7 with 4 cores, Intel Iris Xe graphics, and 15.5 GiB RAM. Installed models included Qwen 2.5 3B, 1.5B and 0.5B, plus SmolLM2 135M. No models were downloaded. The configuration was left unchanged.

The [review file](phase6-reviewed-postings.json) identifies two real public postings and four explicit criteria reviewed against posting text by the assistant. These are scoped criteria, not full job labels. The final rules found 4/4 criteria after improving the location and skill extraction.

| Model | Schema-valid responses | Reviewed criteria covered | Median latency | Ollama reported resident size |
| --- | ---: | ---: | ---: | ---: |
| Qwen 2.5 1.5B | 1 / 2 | 1 / 4 | 39.6 s | 1.37 GB |
| Qwen 2.5 3B | 2 / 2 | 1 / 4 | 72.0 s | 2.42 GB |

This small sample measures criterion coverage and output shape. It does not establish broad model accuracy, hiring probabilities, or a better production model. Project ranking and bullet selection are covered by the existing synthetic and live-Ollama provenance fixtures, independently of this public-posting measurement.

```powershell
.\.venv\Scripts\python.exe -m scripts.evaluate_phase6 --ollama http://127.0.0.1:11435
```

The benchmark reads the existing ignored local cache. See [benchmark collection instructions](JOB_MATCHING_EVALUATION.md) if the cache is absent.
