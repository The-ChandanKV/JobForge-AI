# Phase 9 workflow validation

Validation took place on November 23, 2026 on the installed Windows workspace. The worker was set to assisted preparation, a 60-minute interval, dry-run enabled, and automatic submission disabled. The profile passed readiness with 112 verified facts. Ten role preferences, one preferred location, explicit remote discovery, and seven public employer boards were active. The validation preserved the profile, preferences, and board selection.

## Live discovery and preparation

| Run | Scanned | Filtered | New jobs saved | Eligible | Shortlisted | PDFs compiled | Applications prepared |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Initial activation | 2,359 | 2,358 | 1 | 0 | 0 | 0 | 0 |
| Phase 9 controlled baseline | 2,357 | 2,356 | 0 | 0 | 0 | 0 | 0 |
| Phase 9 controlled follow-up | 2,357 | 2,356 | 0 | 0 | 0 | 0 | 0 |

The enabled sources were Anthropic, Bosch Group, Cloudflare, Datadog, Linear, Stripe, and The Codest. Six boards returned complete source results. Bosch returned 12 listings through the bounded SmartRecruiters check and was marked partial. The controlled runs completed without run errors. A repeat sighting of the saved job kept the same record. The worker checks employer identity and HTTPS job and application destinations on the catalog boards, preserves the original description, and uses feed presence, explicit deadlines, and normalized source aliases to manage availability and duplicates. An incomplete source can still return valid postings. Only postings revalidated in the current run enter automatic preparation.

The single saved opening was available on its official employer URL. Its full description contained minimum qualifications, U.S.-based remote and travel requirements, and degree or equivalent evidence. The employer referred to a level-specific experience minimum without supplying the years, and the feed did not supply employment type or an application deadline. Eligibility remained **Needs review**, with a relevance score of 70. The saved result appears in Exceptions with links to the requirements. There were zero live PDFs, application packages, pending approvals, or submissions. The observed opening did not qualify for a live tailoring sample under the active search and eligibility criteria. [Official employer posting](https://job-boards.greenhouse.io/anthropic/jobs/5462966008)

## Performance and recovery

| Measurement | Observation |
| --- | --- |
| Run elapsed time | 25.34 seconds before the change and 13.84 seconds after it, about 45% lower in this pair of live measurements. |
| Discovery | 13.48 seconds across seven boards after the change. The 13.48-second partial Bosch check set the critical path. |
| Matching | 0.245 seconds across 2,358 measured checks or groups of checks. |
| Database | 37 cursor statements and 0.0054 seconds of cursor execution. Includes executed statements and excludes transaction commit and object hydration. |
| Resource usage | Worker CPU was 6.30 seconds before and 4.94 seconds after. Process peak RSS was 136.00 MiB before and 200.04 MiB after. |
| Local model and compiler | One isolated fictional posting took 1.74 seconds for Ollama fact selection and 0.98 seconds for Tectonic compilation and PDF validation. |
| Live preparation per application | Unmeasured because no posting reached preparation. A single run pair does not establish long-term timing. |

The worker overlaps up to three public board fetches while retaining existing per-provider request spacing and retry budgets. Database writes remain sequential. Matching reuses unchanged results when the matching rules version is current, and new postings reuse the eligibility calculation during persistence. Preparation continues to reuse an existing validated PDF when its verified claims and posting still match. Deterministic PDF validation failures stop automatic retries and surface the cause. Other internal failures continue to use the existing bounded retry budget.

One Windows worker process tree advanced its heartbeat after reloading the existing Task Scheduler entries. The real rolling observation covered 10.584 hours, with 11 expected slots, six recorded scheduled runs that all succeeded, five missed slots, zero failed runs, six worker starts, eight heartbeat gaps, and zero Ollama unavailable transitions. Worker starts include the validation reload and are not a count of crashes. The causes of missed slots were not established. Scheduled-run averages include early runs before all boards were enabled. Observations continue in the installed worker. [Rolling report](24_HOUR_RELIABILITY.md)

## Isolated package, browser, and security checks

An isolated fixture using the actual local Ollama and Tectonic binaries generated a one-page PDF with extractable text, zero layout warnings, zero unsupported claims, and five exact source fact references. Resume versions retain quality reports and the compiled PDF in the private database. Synthetic application tests cover official-link handoff, preparation and screening fields, application status and receipts, approval invalidation after edits, retry recovery, and notification grouping. No employer was contacted for submission. No live application-ready alert was expected because no live package reached review.

Chrome exercised the installed Profile, Discovery, Intelligence, Studio, Approval queue, History, Automation, Notifications, and Exceptions pages. The isolated authenticated browser flow checked PDF preview, manual handoff, and exact approval against a local simulation. The live dashboard listened on 127.0.0.1. The isolated token-enabled flow rejected unauthenticated private PDF access, and PDF responses used no-store. A cross-origin write was rejected. Job descriptions go through text normalization and can only influence ranking or which allowlisted verified fact IDs the model selects. TeX uses trusted templates and Tectonic's untrusted mode. The Git scan covered tracked and historical paths and found no flagged private paths or token patterns. [Test report](TEST_REPORT.md)
