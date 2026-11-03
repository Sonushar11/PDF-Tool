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


def list_spans(file_bytes: bytes, page_index: int) -> list[dict]:
    """Every visible text span on a page, with its box as page percentages.

    Drives click-to-edit in the browser: the UI overlays these boxes on the
    preview image so a click can be resolved to one specific run of text.
    """
    with open_doc(file_bytes) as doc:
        page = doc[page_index]
        page_w, page_h = page.rect.width, page.rect.height
        if not page_w or not page_h:
            return []

        spans = []
        for block in page.get_text("dict").get("blocks", []):
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = span.get("text", "")
                    if not text.strip():
                        continue
                    x0, y0, x1, y1 = span["bbox"]
                    spans.append({
                        "text": text,
                        "size": round(span.get("size", 12), 2),
                        "x_pct": round(x0 / page_w * 100, 4),
                        "y_pct": round(y0 / page_h * 100, 4),
                        "w_pct": round((x1 - x0) / page_w * 100, 4),
                        "h_pct": round((y1 - y0) / page_h * 100, 4),
                    })
        return spans


# Base-14 PostScript names -> the short codes insert_text expects.
_BASE14_CODES = {
    "courier": "cour", "courier-oblique": "coit", "courier-bold": "cobo",
    "courier-boldoblique": "cobi",
    "helvetica": "helv", "helvetica-oblique": "heit", "helvetica-bold": "hebo",
    "helvetica-boldoblique": "hebi",
    "times-roman": "tiro", "times-italic": "tiit", "times-bold": "tibo",
    "times-bolditalic": "tibi",
    "symbol": "symb", "zapfdingbats": "zadb",
}

# Fallbacks keyed by (bold, italic), picked from the span's style flags.
_MONO = {(False, False): "cour", (True, False): "cobo",
         (False, True): "coit", (True, True): "cobi"}
_SERIF = {(False, False): "tiro", (True, False): "tibo",
          (False, True): "tiit", (True, True): "tibi"}
_SANS = {(False, False): "helv", (True, False): "hebo",
         (False, True): "heit", (True, True): "hebi"}


def _bare_font_name(name: str) -> str:
    """'ABCDEF+Arial-BoldMT' -> 'arial-boldmt' (subset prefix dropped)."""
    return (name or "").split("+")[-1].strip().lower()


def _squash(name: str) -> str:
    return "".join(ch for ch in _bare_font_name(name) if ch.isalnum())


def _base14_from_flags(flags: int) -> str:
    style = (bool(flags & 16), bool(flags & 2))  # bold, italic
    if flags & 8:
        return _MONO[style]
    if flags & 4:
        return _SERIF[style]
    return _SANS[style]


def _resolve_font(doc, page, span) -> tuple[str, bytes | None]:
    """Work out how to redraw a span in its original typeface.

    Returns (fontname, fontbuffer). When a buffer comes back the font was
    embedded in the PDF and can be re-embedded verbatim; otherwise the name is
    a base-14 code chosen to match as closely as the standard fonts allow.
    """
    span_font = span.get("font", "")
    flags = span.get("flags", 0)

    # 1. The font is embedded - reuse the real thing.
    try:
        entries = page.get_fonts(full=True)
    except Exception:
        entries = []

    candidates = []
    for entry in entries:
        xref, _ext, _ftype, basefont, refname, *_ = entry
        if _squash(basefont) == _squash(span_font) or _squash(refname) == _squash(span_font):
            candidates.insert(0, xref)          # exact match wins
        elif _squash(span_font) and (
            _squash(span_font) in _squash(basefont) or _squash(basefont) in _squash(span_font)
        ):
            candidates.append(xref)             # partial match
    if not candidates and len(entries) == 1:
        candidates = [entries[0][0]]            # only one font on the page

    for xref in candidates:
        try:
            _name, ext, _ftype, buffer = doc.extract_font(xref)
        except Exception:
            continue
        if buffer and ext not in ("n/a", "", None):
            return f"EMB{xref}", buffer

    # 2. A standard font, referenced by name.
    code = _BASE14_CODES.get(_bare_font_name(span_font))
    if code:
        return code, None

    # 3. Nothing matched - approximate from the style flags.
    return _base14_from_flags(flags), None


def _span_at(page, rect):
    """The text span overlapping `rect` most - what the user clicked."""
    best_area, best_span = 0.0, None
    for block in page.get_text("dict").get("blocks", []):
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                overlap = fitz.Rect(span["bbox"]) & rect
                area = overlap.get_area() if not overlap.is_empty else 0.0
                if area > best_area:
                    best_area, best_span = area, span
    return best_span


def replace_span(
    file_bytes: bytes,
    page_index: int,
    x_pct: float,
    y_pct: float,
    w_pct: float,
    h_pct: float,
    new_text: str,
    *,
    font_size: float | None = None,
) -> bytes:
    """Rewrite the text inside one span's box, keeping its look where possible.

    The original run is removed and the replacement redrawn. Font, size, colour
    and baseline are taken from the span being replaced: if its typeface was
    embedded in the PDF it is re-embedded and reused verbatim, so the result
    matches. Only when the font cannot be recovered does this fall back to the
    closest standard font, and then the text will not be pixel-identical.
    """
    with open_doc(file_bytes) as doc:
        page = doc[page_index]
        x0 = page.rect.width * x_pct / 100
        y0 = page.rect.height * y_pct / 100
        rect = fitz.Rect(
            x0, y0,
            x0 + page.rect.width * w_pct / 100,
            y0 + page.rect.height * h_pct / 100,
        )
        if rect.is_empty:
            raise ValueError("That text box is too small to edit.")

        # Read the original's styling BEFORE redacting: applying a redaction
        # can drop the font resource once nothing on the page still uses it.
        span = _span_at(page, rect)
        fontname, fontbuffer = "helv", None
        color = (0, 0, 0)
        size = font_size
        baseline = None

        if span is not None:
            fontname, fontbuffer = _resolve_font(doc, page, span)
            color = tuple(c / 255 for c in fitz.sRGB_to_rgb(span.get("color", 0)))
            if size is None:
                size = span.get("size")
            if span.get("origin"):
                baseline = fitz.Point(span["bbox"][0], span["origin"][1])

        if not size:
            size = max(min(rect.height * 0.8, 24), 6)
        if baseline is None:
            baseline = fitz.Point(rect.x0, rect.y1 - rect.height * 0.2)

        page.add_redact_annot(rect, fill=(1, 1, 1))
        page.apply_redactions()

        if new_text:
            if fontbuffer:
                try:
                    page.insert_font(fontname=fontname, fontbuffer=fontbuffer)
                except Exception:
                    fontname = _base14_from_flags(span.get("flags", 0) if span else 0)
            try:
                page.insert_text(baseline, new_text, fontsize=size,
                                 fontname=fontname, color=color)
            except Exception:
                # Never lose the edit over a font problem.
                page.insert_text(baseline, new_text, fontsize=size,
                                 fontname="helv", color=color)
        return save_doc_bytes(doc)


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
