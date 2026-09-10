"""Annotations (freetext notes, highlights) and signature/stamp placement.

Positions are expressed as percentages of the page's width/height (0-100) so
the browser only ever needs to know where the user clicked on a rendered
preview image, not the PDF's internal point coordinate system.
"""
from __future__ import annotations

import io

import fitz  # PyMuPDF
from PIL import Image

from app.pdf_core.pages import open_doc, save_doc_bytes


def _pct_point(rect: fitz.Rect, x_pct: float, y_pct: float) -> fitz.Point:
    return fitz.Point(rect.width * x_pct / 100, rect.height * y_pct / 100)


def add_freetext(
    file_bytes: bytes,
    page_index: int,
    x_pct: float,
    y_pct: float,
    text: str,
    *,
    width_pct: float = 30,
    font_size: float = 12,
    color: tuple[float, float, float] = (0, 0, 0),
) -> bytes:
    with open_doc(file_bytes) as doc:
        page = doc[page_index]
        origin = _pct_point(page.rect, x_pct, y_pct)
        width = page.rect.width * width_pct / 100
        lines = max(text.count("\n") + 1, 1)
        height = font_size * 1.4 * lines + 8
        rect = fitz.Rect(origin.x, origin.y, origin.x + width, origin.y + height)
        annot = page.add_freetext_annot(rect, text, fontsize=font_size, text_color=color)
        annot.update()
        return save_doc_bytes(doc)


def add_highlight(
    file_bytes: bytes,
    page_index: int,
    x_pct: float,
    y_pct: float,
    width_pct: float,
    height_pct: float,
) -> bytes:
    with open_doc(file_bytes) as doc:
        page = doc[page_index]
        rect = fitz.Rect(
            page.rect.width * x_pct / 100,
            page.rect.height * y_pct / 100,
            page.rect.width * (x_pct + width_pct) / 100,
            page.rect.height * (y_pct + height_pct) / 100,
        )
        annot = page.add_highlight_annot(rect)
        annot.update()
        return save_doc_bytes(doc)


def add_image_stamp(
    file_bytes: bytes,
    page_index: int,
    x_pct: float,
    y_pct: float,
    width_pct: float,
    image_bytes: bytes,
) -> bytes:
    with open_doc(file_bytes) as doc:
        page = doc[page_index]
        with Image.open(io.BytesIO(image_bytes)) as im:
            img_w, img_h = im.size
        width_pts = page.rect.width * width_pct / 100
        height_pts = width_pts * (img_h / img_w) if img_w else width_pts
        x0 = page.rect.width * x_pct / 100
        y0 = page.rect.height * y_pct / 100
        rect = fitz.Rect(x0, y0, x0 + width_pts, y0 + height_pts)
        page.insert_image(rect, stream=image_bytes)
        return save_doc_bytes(doc)
