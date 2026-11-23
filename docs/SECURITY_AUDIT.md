# Security and privacy audit

| Surface | Finding |
| --- | --- |
| Resumes, profile, PDFs and answers | Original uploads and exact prepared versions remain in local SQLite. Authenticated routes return originals as attachments or bounded text. React escapes displayed text. Private API responses carry no-store and the existing restrictive CSP. |
| Local access | The installed Windows listener was verified on `127.0.0.1:8000`. The access token was unset on this installation. Other processes or users able to reach loopback can access it unless a token is configured. Set `JOBFORGE_ACCESS_TOKEN` locally and restart the dashboard if the machine is shared. Cross-origin writes are blocked. |
| Windows data ACL | No allow entries were found for Everyone, Authenticated Users, or BUILTIN Users on the inspected data directory. No ACLs were changed. |
| Credentials and evidence | Provider and SMTP configuration stay in the environment. The repository ignores databases, local configuration and benchmark payloads. The shareable benchmark manifest contains only public posting metadata. |
| Logs | Scheduler, health and alert events use counts, state, and internal identifiers. Compiler failures return a bounded generic message without echoed TeX output. The desktop delivery diagnostic stores only the outcome code. |
| Untrusted content | Employer descriptions are untrusted inputs to the ranker. The ranker returns constrained IDs drawn from verified facts. Hard eligibility stays deterministic. External model services can receive bounded career evidence when explicitly configured. |
| LaTeX | Imported source is parsed as text. Generated TeX escapes fact values. Tectonic uses untrusted and cached modes in an isolated temporary directory with a reduced environment. Editable TeX is constrained to permitted layout changes. |
| External URLs | Discovery uses configured providers and normalized posting URLs. Manual review opens HTTP(S) employer links without data submission by JobForge. No browser-assisted automation was enabled for live portals. |
| Approval integrity | Final approval remains immutable and bound to the prepared snapshot. The current worker retains exact destination checks, form validation, and at-most-once dispatch. Production was verified in dry-run mode. |

Run `.\.venv\Scripts\python.exe -m scripts.check_private_files` before publishing. It checks tracked file content for known token formats and credential assignments and checks tracked and historical path names for private artifacts. It reports paths and categories only. This is a pattern check, so unusual secret formats and past contents at ordinary paths need additional review. No flagged paths or credential patterns were found in the verified branch.
