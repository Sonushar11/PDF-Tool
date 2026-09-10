"""Best-effort text find & replace.

This is NOT true WYSIWYG PDF text editing -- that requires parsing and
rewriting the page's content stream in a way that reliably preserves fonts,
kerning and layout, which is not achievable in general for arbitrary PDFs.
Instead: find each occurrence, redact (permanently remove) that region, and
insert replacement text at the same position using a built-in font sized to
approximate the original. Works well for simple cases (single-line labels,
form-like text); may look visually different from the original font/kerning
on complex layouts. Callers should treat this as a labelled, limited feature.
"""
from __future__ import annotations

import fitz  # PyMuPDF

from app.pdf_core.pages import open_doc, save_doc_bytes


def find_and_replace(file_bytes: bytes, find_text: str, replace_text: str) -> tuple[bytes, int]:
    if not find_text:
        raise ValueError("Enter text to find.")
    count = 0
    with open_doc(file_bytes) as doc:
        for page in doc:
            hits = page.search_for(find_text)
            if not hits:
                continue
            for rect in hits:
                page.add_redact_annot(rect, fill=(1, 1, 1))
            page.apply_redactions()
            for rect in hits:
                font_size = max(min(rect.height * 0.8, 24), 6)
                origin = fitz.Point(rect.x0, rect.y1 - rect.height * 0.2)
                page.insert_text(origin, replace_text, fontsize=font_size, fontname="helv")
                count += 1
        return save_doc_bytes(doc), count
