# Resume optimization

Resume Studio retrieves verified evidence according to the job's detected requirements. Each experience or project bullet preserves the source fact ID. The workspace displays the evidence, matching skills, and why the wording changed or stayed the same. Wording transformations are limited to whitespace, list formatting, capitalization and conservative first-person edits. The compiler revalidates the source-equivalent text. Unrestricted semantic paraphrasing is outside the supported path.

The existing classic and compact templates still render through Tectonic. The PDF report records page count, selectable text, detected fonts, section coverage, formatting warnings, required skill gaps and hyperlink annotations. Font detection and overflow diagnostics support review. They do not substitute for inspecting the PDF. Current templates may render verified links as text without clickable annotations.

Resume Studio compares source text and compiled output side by side. The worker reuses saved PDFs when verified claims remain unchanged and the stored posting digest still matches. Existing older versions remain intact. Newly produced versions both retain the posting digest and record which claims support their bullets.

The isolated smoke generated and validated a one-page classic PDF from synthetic evidence in 1.88 seconds. It detected two named fonts and zero unsupported claims. Real times vary by evidence length, compiler cache, and whether an Ollama model is used. [Approval and submission](APPROVAL_AND_SUBMISSION.md)
