"""Rendering pages to images: thumbnails, full-size previews, and rebuilding
a PDF from pages rasterized at a chosen DPI."""
from __future__ import annotations

import fitz  # PyMuPDF

from app.pdf_core.pages import open_doc, save_doc_bytes

BASE_DPI = 72  # PDF's native unit; fitz.Matrix scale factors are relative to this.


def _pixmap_for_dpi(page: fitz.Page, dpi: int) -> fitz.Pixmap:
    zoom = dpi / BASE_DPI
    return page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))


def render_page_png(file_bytes: bytes, page_index: int, dpi: int = 150) -> bytes:
    with open_doc(file_bytes) as doc:
        page = doc[page_index]
        pix = _pixmap_for_dpi(page, dpi)
        return pix.tobytes("png")


def render_thumbnail_png(file_bytes: bytes, page_index: int, max_dim: int = 220) -> bytes:
    with open_doc(file_bytes) as doc:
        page = doc[page_index]
        rect = page.rect
        longest = max(rect.width, rect.height) or 1
        zoom = max_dim / longest
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
        return pix.tobytes("png")


def rasterize_pdf(file_bytes: bytes, dpi: int) -> bytes:
    """Rebuilds the PDF with every page replaced by a flattened image rendered
    at `dpi`. Useful for shrinking oversized scans or standardizing resolution
    before OCR. This only changes resolution/flattens content — it does not
    invent any pixel data beyond what's already on the page."""
    out = fitz.open()
    try:
        with open_doc(file_bytes) as src:
            for page in src:
                pix = _pixmap_for_dpi(page, dpi)
                img_page = out.new_page(width=page.rect.width, height=page.rect.height)
                img_page.insert_image(img_page.rect, pixmap=pix)
        return save_doc_bytes(out)
    finally:
        out.close()
