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
    *,
    color: tuple[float, float, float] | None = None,
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
        if color is not None:
            # Highlights carry their colour on the stroke channel, not fill.
            annot.set_colors(stroke=color)
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


def list_words(file_bytes: bytes, page_index: int) -> list[dict]:
    """Word boxes on a page as percentages, for the snap-to-text highlighter.

    The browser uses these to work out which words a highlighter sweep passed
    over, so the resulting highlight follows the text instead of being a loose
    rectangle drawn by hand.
    """
    with open_doc(file_bytes) as doc:
        page = doc[page_index]
        page_w, page_h = page.rect.width, page.rect.height
        if not page_w or not page_h:
            return []

        words = []
        for x0, y0, x1, y1, word, *_rest in page.get_text("words"):
            if not word.strip():
                continue
            words.append({
                "text": word,
                "x_pct": round(x0 / page_w * 100, 4),
                "y_pct": round(y0 / page_h * 100, 4),
                "w_pct": round((x1 - x0) / page_w * 100, 4),
                "h_pct": round((y1 - y0) / page_h * 100, 4),
            })
        return words


def add_highlight_boxes(
    file_bytes: bytes,
    page_index: int,
    boxes: list[dict],
    *,
    color: tuple[float, float, float] | None = None,
) -> bytes:
    """Highlight several boxes as one annotation.

    A sweep across three words is one highlight with three quads, not three
    separate annotations - that is how a PDF reader expects multi-word
    highlights to be stored, and it keeps undo to a single step.
    """
    with open_doc(file_bytes) as doc:
        page = doc[page_index]
        quads = []
        for box in boxes:
            x0 = page.rect.width * float(box["x_pct"]) / 100
            y0 = page.rect.height * float(box["y_pct"]) / 100
            rect = fitz.Rect(
                x0, y0,
                x0 + page.rect.width * float(box["w_pct"]) / 100,
                y0 + page.rect.height * float(box["h_pct"]) / 100,
            )
            if not rect.is_empty:
                quads.append(rect.quad)
        if not quads:
            raise ValueError("Nothing to highlight.")

        annot = page.add_highlight_annot(quads=quads)
        if color is not None:
            annot.set_colors(stroke=color)
        annot.update()
        return save_doc_bytes(doc)
