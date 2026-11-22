"""Isolated-process text extraction for uploaded documents."""
import sys

from pypdf import PdfReader

if sys.platform != "win32":
    import resource

    resource.setrlimit(resource.RLIMIT_AS, (384 * 1024 * 1024, 384 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_CPU, (12, 12))

reader = PdfReader(sys.argv[1], strict=True)
if reader.is_encrypted or len(reader.pages) > 24:
    raise SystemExit("Encrypted or oversized document")
text = "\n".join(page.extract_text() or "" for page in reader.pages)
sys.stdout.buffer.write(text[:120_000].encode("utf-8"))
