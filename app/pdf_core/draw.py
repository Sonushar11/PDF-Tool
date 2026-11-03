"""Page-content editing tools: freehand ink, vector shapes and whiteout.

Like annotate.py, every coordinate arrives as a percentage of the page's
width/height (0-100) so the browser only ever works in preview-image space and
never needs to know the PDF's point coordinate system.

Ink and shapes are added as real PDF annotations, so they stay selectable and
removable in other PDF readers. Whiteout is different: it applies a redaction,
which permanently destroys the covered content rather than drawing over it.
"""
from __future__ import annotations

import fitz  # PyMuPDF

from app.pdf_core.pages import open_doc, save_doc_bytes

SHAPE_KINDS = ("rect", "ellipse", "line", "arrow")


def _point(page: fitz.Page, x_pct: float, y_pct: float) -> fitz.Point:
    return fitz.Point(page.rect.width * x_pct / 100, page.rect.height * y_pct / 100)


def _rect_from_corners(page: fitz.Page, x0_pct, y0_pct, x1_pct, y1_pct) -> fitz.Rect:
    """Normalised so dragging up/left produces the same rect as down/right."""
    a = _point(page, x0_pct, y0_pct)
    b = _point(page, x1_pct, y1_pct)
    return fitz.Rect(min(a.x, b.x), min(a.y, b.y), max(a.x, b.x), max(a.y, b.y))


def add_ink(
    file_bytes: bytes,
    page_index: int,
    strokes: list[list[tuple[float, float]]],
    *,
    color: tuple[float, float, float] = (0, 0, 0),
    width: float = 1.5,
) -> bytes:
    """strokes: a list of polylines, each a list of (x_pct, y_pct) pairs."""
    with open_doc(file_bytes) as doc:
        page = doc[page_index]
        # A single-point stroke has no geometry to draw; PyMuPDF rejects it.
        # add_ink_annot wants plain (x, y) float pairs, not Point objects.
        paths = [
            [(page.rect.width * x / 100, page.rect.height * y / 100) for x, y in stroke]
            for stroke in strokes
            if len(stroke) >= 2
        ]
        if not paths:
            raise ValueError("Nothing was drawn.")
        annot = page.add_ink_annot(paths)
        annot.set_colors(stroke=color)
        annot.set_border(width=width)
        annot.update()
        return save_doc_bytes(doc)


def add_shape(
    file_bytes: bytes,
    page_index: int,
    kind: str,
    x0_pct: float,
    y0_pct: float,
    x1_pct: float,
    y1_pct: float,
    *,
    color: tuple[float, float, float] = (0, 0, 0),
    fill: tuple[float, float, float] | None = None,
    width: float = 1.5,
) -> bytes:
    if kind not in SHAPE_KINDS:
        raise ValueError(f"Unknown shape: {kind}")

    with open_doc(file_bytes) as doc:
        page = doc[page_index]

        if kind in ("line", "arrow"):
            # Lines keep their direction - normalising would flip the arrowhead.
            start = _point(page, x0_pct, y0_pct)
            end = _point(page, x1_pct, y1_pct)
            annot = page.add_line_annot(start, end)
            if kind == "arrow":
                annot.set_line_ends(fitz.PDF_ANNOT_LE_NONE, fitz.PDF_ANNOT_LE_CLOSED_ARROW)
        else:
            rect = _rect_from_corners(page, x0_pct, y0_pct, x1_pct, y1_pct)
            if rect.is_empty:
                raise ValueError("Drag out a larger shape.")
            annot = (
                page.add_rect_annot(rect)
                if kind == "rect"
                else page.add_circle_annot(rect)
            )

        annot.set_colors(stroke=color, fill=fill)
        annot.set_border(width=width)
        annot.update()
        return save_doc_bytes(doc)


def whiteout(
    file_bytes: bytes,
    page_index: int,
    x0_pct: float,
    y0_pct: float,
    x1_pct: float,
    y1_pct: float,
) -> bytes:
    """Permanently remove everything inside the box and leave it white.

    This is a redaction, not a white rectangle drawn on top - the underlying
    text and images are destroyed, so they cannot be recovered by selecting
    the area or inspecting the content stream.
    """
    with open_doc(file_bytes) as doc:
        page = doc[page_index]
        rect = _rect_from_corners(page, x0_pct, y0_pct, x1_pct, y1_pct)
        if rect.is_empty:
            raise ValueError("Drag out a larger area to white out.")
        page.add_redact_annot(rect, fill=(1, 1, 1))
        page.apply_redactions()
        return save_doc_bytes(doc)
