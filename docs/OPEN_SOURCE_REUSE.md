# Open-source reuse

Seven shallow clones are isolated in research/upstream. Setup scripts from the clones were not executed.

| Project | Inspected commit | License | Findings and integration |
|---|---|---|---|
| [career-ops](https://github.com/career-ops-hq/career-ops) | 087235431837f6de4ef10e0a813bcfce46dd97da | MIT | Prioritized as a foundation. Reviewed the README, package scripts, tests, ATS classifier, URL deduplication and LaTeX builder. The Go dashboard and Node pipeline rely on career-ops workspace files, profile conventions and reports. Its standalone Ollama evaluation does not provide the shared database and explicit provenance/approval contract required here. Vendored only the dependency-free ATS classifier for manual URL routing, with the original MIT notice. Node is required for this entry point. |
| [AIHawk](https://github.com/feder-cr/Jobs_Applier_AI_Agent) | 6e57771c79d371745055a0e8f0ce40b8da4c8506 | MIT with NOTICE | CLI, job database pipeline, scoring, profile and browser flows. Tests include fake and live-browser paths. Database has separate source terms including ODbL and CC BY. No import of code or compiled job data, and no reliance on browser login or applicant account state. |
| [JobSpy](https://github.com/speedyapply/JobSpy) | c1be997b61d6acefec8328f5f56c968ceef7e28a | MIT | Aggregator scrapers and normalization with pandas/numpy and provider-specific network assumptions. Standalone test suite was not evident in the clone. Deferred as a plugin until an explicitly permitted source and collection policy are available. |
| [ApplyPilot](https://github.com/Pickle-Pixel/ApplyPilot) | 4a8d521f67f5139811c0a910ef37410f8e6d836a | AGPL-3.0-only | Reference for staged discovery, scoring, tailoring and application tracking. Uses Playwright, LLM adapters, JobSpy and optional CLI-driven automation. No production code incorporated because the coupling and licensing obligations do not fit this build. |
| [Ollama](https://github.com/ollama/ollama) | 318ee284aa3b5558de57efefff730ea33c4a9bef | MIT | Reviewed API and integration tree. External runtime via documented structured chat API. Preserve distribution notices if bundling. Model weights have separate terms and hardware requirements. |
| [Tectonic](https://github.com/tectonic-typesetting/tectonic) | d2224d9ba4185f952fd3d982eccd1f444dbdf895 | MIT with separately licensed components | External compiler via subprocess. Reviewed Rust CLI and test tree. Bundle bootstrap needs network or provisioned cache. Preserve compiler and bundle notices when distributing them. |
| [Playwright](https://github.com/microsoft/playwright) | 049226728d2da8054db18b04782a9848b755855e | Apache-2.0 | Use the published Python binding and Chromium for mock-site application preparation and verification. Browser binaries carry separate notices. |

Public discovery uses the first-party [Greenhouse Job Board API](https://docs.greenhouse.io/job-board.html), [Lever Postings API](https://github.com/lever/postings-api), and [Ashby Job Posting API](https://developers.ashbyhq.com/docs/public-job-posting-api).

