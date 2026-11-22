# Local model evaluation

The Windows host reported approximately 15.5 GiB of physical memory, approximately 3.9 GiB free at selection time, and Intel Iris Xe integrated graphics. Ollama already had Qwen2.5 1.5B locally. The comparison added its 1.9 GB Qwen2.5 3B variant and used local inference on loopback. [Ollama Qwen2.5 tags](https://ollama.com/library/qwen2.5/tags)

The five synthetic fixtures cover graduate backend engineering, junior data engineering, ML internship work authorization, full-stack mandatory experience, and a clearance exception. Fixtures include expected required and preferred skills, an eligibility outcome, a target project, and distractors. Each evaluation compiles a real one-page Tectonic PDF and checks the verified project wording, extraction, and layout result. Latency includes ranking and compilation.

| Measure | Qwen2.5 1.5B | Qwen2.5 3B |
|---|---:|---:|
| Structured ranking returned by Ollama | 5/5 | 5/5 |
| First ranked project matched fixture target | 5/5 | 5/5 |
| Factual PDF and clean layout checks | 5/5 | 5/5 |
| Deterministic eligibility and skill classification | 5/5 each | 5/5 each |
| Median end-to-end latency | 2.30 s | 4.08 s |

Qwen2.5 1.5B stays the default. The benchmark found equal fixture outcomes and a faster median for 1.5B. Eligibility and extraction use Python rules, so their outcomes are shared. This is a small synthetic benchmark, and formatting checks cover text, page count, and compiler warnings. The larger model remains an explicit option in Settings.

```powershell
$env:OLLAMA_BASE_URL = 'http://127.0.0.1:11435'
./.venv/Scripts/python.exe -m scripts.evaluate_models qwen2.5:1.5b qwen2.5:3b
```

Use the port of your running Ollama server. The evaluator uses a temporary database and synthetic profiles.
