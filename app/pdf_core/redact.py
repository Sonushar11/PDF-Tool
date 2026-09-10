"""True redaction: permanently removes the underlying text/image content in
the marked area (not just a black rectangle drawn on top, which could still
be lifted off by anyone opening the file)."""
from __future__ import annotations

import fitz  # PyMuPDF

from app.pdf_core.pages import open_doc, save_doc_bytes


def redact_areas(file_bytes: bytes, redactions: list[dict]) -> bytes:
    """redactions: list of {page_index, x_pct, y_pct, width_pct, height_pct}."""
    with open_doc(file_bytes) as doc:
        touched_pages = set()
        for r in redactions:
            page = doc[int(r["page_index"])]
            rect = fitz.Rect(
                page.rect.width * float(r["x_pct"]) / 100,
                page.rect.height * float(r["y_pct"]) / 100,
                page.rect.width * (float(r["x_pct"]) + float(r["width_pct"])) / 100,
                page.rect.height * (float(r["y_pct"]) + float(r["height_pct"])) / 100,
            )
            page.add_redact_annot(rect, fill=(0, 0, 0))
            touched_pages.add(page.number)
        for page_number in touched_pages:
            doc[page_number].apply_redactions()
        return save_doc_bytes(doc)


def redact_text(file_bytes: bytes, search_text: str) -> tuple[bytes, int]:
    """Finds every occurrence of `search_text` and redacts it. Returns the
    updated PDF bytes and the number of occurrences redacted."""
    if not search_text.strip():
        raise ValueError("Enter text to search for.")
    count = 0
    with open_doc(file_bytes) as doc:
        for page in doc:
            hits = page.search_for(search_text)
            for rect in hits:
                page.add_redact_annot(rect, fill=(0, 0, 0))
                count += 1
            if hits:
                page.apply_redactions()
        return save_doc_bytes(doc), count
