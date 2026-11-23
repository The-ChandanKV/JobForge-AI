"""Isolated-process text extraction for uploaded documents."""
import sys
from urllib.parse import urlsplit

from pypdf import PdfReader

if sys.platform != "win32":
    import resource

    resource.setrlimit(resource.RLIMIT_AS, (384 * 1024 * 1024, 384 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_CPU, (12, 12))

reader = PdfReader(sys.argv[1], strict=True)
if reader.is_encrypted or len(reader.pages) > 24:
    raise SystemExit("Encrypted or oversized document")
text = "\n".join(page.extract_text() or "" for page in reader.pages)
if "--contact-links" in sys.argv:
    links = []
    for number, page in enumerate(reader.pages, 1):
        for reference in (page.get("/Annots") or [])[:100]:
            annotation = reference.get_object()
            action = annotation.get("/A") if annotation.get("/Subtype") == "/Link" else None
            if not action:
                continue
            action = action.get_object()
            url = str(action.get("/URI", ""))
            try:
                address = urlsplit(url)
                host = address.hostname or ""
            except ValueError:
                continue
            path = address.path.strip("/").split("/")
            github = host in {"github.com", "www.github.com"} and len(path) == 1 and bool(path[0])
            linkedin = (host == "linkedin.com" or host.endswith(".linkedin.com")) and len(path) > 1 and path[0] in {"in", "pub"}
            if address.scheme == "https" and not address.username and len(url) < 1500 and (github or linkedin):
                links.append(f"PDF hyperlink on page {number}: {url}")
    text = "\n".join([*dict.fromkeys(links[:20]), text])
sys.stdout.buffer.write(text[:120_000].encode("utf-8"))
