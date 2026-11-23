# Job matching evaluation

The Phase 4 benchmark retrieved **36 current engineering postings** on November 23, 2026, from six public employer career feeds. Each employer contributed six postings. The [public manifest](job-benchmark-manifest.json) records the official URL, source key, and retrieval time. Full fetched descriptions, model outputs, and the review template stay in the ignored local `data/job-benchmark/` directory. The benchmark uses synthetic applicant facts and does not touch the workspace profile. [Greenhouse Job Board API](https://docs.greenhouse.io/job-board.html#list-jobs)

The rules ran on all 36 postings with approximately 20 ms median rule time. They classified 30 as needs review and 6 as eligible for the synthetic profile. These are rule outputs. No human reviewed the labels. Accuracy, false-eligibility rates, missing-requirement rates against ground truth, and ranking accuracy therefore remain unmeasured.

The same three public postings were sent to each already installed local model. Structured responses were checked with a strict schema. Latency includes local request time and any model loading on that sample. Resident memory is the maximum measured model size reported by Ollama after the requests.

| Installed model | Valid / attempted | Invalid | Median latency | Reported resident memory |
| --- | ---: | ---: | ---: | ---: |
| qwen2.5:3b | 3 / 3 | 0 | 62.25 s | 2.17 GB |
| qwen2.5:1.5b | 2 / 3 | 1 | 31.47 s | 1.17 GB |
| qwen2.5:0.5b | 1 / 3 | 2 | 19.38 s | 0.49 GB |
| smollm2:135m | 0 / 3 | 3 | 12.43 s | 0.38 GB |

On this sample the 3B model produced the most schema-valid output. The sample and absence of reviewed labels do not support changing the production model or replacing deterministic hard eligibility. No models were downloaded.

```powershell
.\.venv\Scripts\python.exe -m scripts.benchmark_jobs --collect --limit 36
.\.venv\Scripts\python.exe -m scripts.benchmark_jobs --ollama http://127.0.0.1:11435 --model-sample 3
.\.venv\Scripts\python.exe -m scripts.benchmark_jobs --labels data/job-benchmark/reviewed.json
```

Copy the generated review template to `reviewed.json`. For each reviewed posting, set `review_status` to `human_reviewed` and add only validated fields. Available labels include required and preferred skills, mandatory experience, graduation, eligibility, degree, location, authorization, relevant projects, and a numeric `relevance_grade` for pairwise ranking. Leave keys absent when evidence is insufficient. Model extraction compares applicable reviewed fields without deciding application eligibility.
