"""Turn a PDF's text layer into Markdown.

Headings are inferred from font size relative to the document's body size, and
bold/italic from the span style flags, because PDFs carry no semantic structure
of their own - only positioned glyphs with a typeface. That inference is the
whole game here, so it is deliberately conservative: when a document's sizing
is flat, everything comes out as paragraphs rather than inventing a hierarchy.

Tables are read with PyMuPDF's table finder and emitted as Markdown tables;
text inside a detected table is skipped so it isn't repeated as prose.

Scanned pages have no text layer and produce nothing - run OCR first.
"""
from __future__ import annotations

import re
from collections import Counter

import fitz  # PyMuPDF

from app.pdf_core.pages import open_doc

_BULLET = re.compile(r"^\s*[•●▪·\-\*–]\s+")
_NUMBERED = re.compile(r"^\s*(\d+)[.)]\s+")


def _clean(text: str) -> str:
    # PDFs often use non-breaking spaces between words; normalise for Markdown.
    return text.replace("\xa0", " ").replace("​", "").strip()


def _escape(text: str) -> str:
    """Escape only what would otherwise be read as Markdown syntax."""
    return re.sub(r"(?<!\\)([*_`\[\]<>])", r"\\\1", text)


def _style_runs(spans: list[dict]) -> str:
    """Join a line's spans, wrapping bold/italic runs in Markdown emphasis."""
    out = []
    for span in spans:
        text = _clean(span.get("text", ""))
        if not text:
            continue
        flags = span.get("flags", 0)
        bold = bool(flags & 16)
        italic = bool(flags & 2)
        mono = bool(flags & 8)

        body = _escape(text) if not mono else f"`{text}`"
        if bold and italic:
            body = f"***{body}***"
        elif bold:
            body = f"**{body}**"
        elif italic:
            body = f"*{body}*"
        out.append(body)
    return " ".join(out)


def _body_size(doc, page_indices) -> float:
    """The most common span size - treated as normal body text."""
    counter = Counter()
    for index in page_indices:
        for block in doc[index].get_text("dict").get("blocks", []):
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    if _clean(span.get("text", "")):
                        counter[round(span.get("size", 0), 1)] += len(span["text"])
    if not counter:
        return 0.0
    return counter.most_common(1)[0][0]


def _heading_level(size: float, body: float) -> int:
    """0 = not a heading, otherwise a Markdown heading level."""
    if not body:
        return 0
    ratio = size / body
    if ratio >= 1.8:
        return 1
    if ratio >= 1.45:
        return 2
    if ratio >= 1.15:
        return 3
    return 0


def _table_markdown(table) -> str:
    try:
        rows = table.extract()
    except Exception:
        return ""
    rows = [[_clean(str(c)) if c is not None else "" for c in row] for row in rows]
    rows = [r for r in rows if any(r)]
    if not rows:
        return ""

    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    header, *body = rows
    if not body:                      # a one-row table needs a header to be valid
        body = [[""] * width]

    lines = [
        "| " + " | ".join(c.replace("|", "\\|") for c in header) + " |",
        "| " + " | ".join("---" for _ in range(width)) + " |",
    ]
    for row in body:
        lines.append("| " + " | ".join(c.replace("|", "\\|") for c in row) + " |")
    return "\n".join(lines)


def to_markdown(
    file_bytes: bytes,
    *,
    page_indices: list[int] | None = None,
    include_tables: bool = True,
    page_breaks: bool = True,
) -> str:
    with open_doc(file_bytes) as doc:
        indices = page_indices if page_indices is not None else list(range(doc.page_count))
        indices = [i for i in indices if 0 <= i < doc.page_count]
        if not indices:
            return ""

        body = _body_size(doc, indices)
        chunks: list[str] = []

        for index in indices:
            page = doc[index]
            if page_breaks and len(indices) > 1:
                chunks.append(f"<!-- page {index + 1} -->")

            table_rects, table_blocks = [], []
            if include_tables:
                try:
                    for table in page.find_tables().tables:
                        markdown = _table_markdown(table)
                        if markdown:
                            table_rects.append(fitz.Rect(table.bbox))
                            table_blocks.append((fitz.Rect(table.bbox).y0, markdown))
                except Exception:
                    pass   # table detection is best-effort, never fatal

            text_blocks = []
            for block in page.get_text("dict").get("blocks", []):
                if block.get("type") != 0:
                    continue
                rect = fitz.Rect(block["bbox"])
                # Skip prose that is really a table cell.
                if any(rect.intersects(tr) and (rect & tr).get_area() > rect.get_area() * 0.5
                       for tr in table_rects):
                    continue

                lines, sizes = [], []
                for line in block.get("lines", []):
                    rendered = _style_runs(line.get("spans", []))
                    if rendered:
                        lines.append(rendered)
                        sizes.extend(s.get("size", 0) for s in line.get("spans", [])
                                     if _clean(s.get("text", "")))
                if not lines:
                    continue

                level = _heading_level(max(sizes) if sizes else 0, body)
                raw_first = _clean(block["lines"][0]["spans"][0].get("text", ""))

                if level and len(lines) <= 2:
                    text = " ".join(lines)
                    rendered = "#" * level + " " + re.sub(r"[*_]", "", text)
                elif _BULLET.match(raw_first):
                    rendered = "\n".join("- " + _BULLET.sub("", ln) for ln in lines)
                elif _NUMBERED.match(raw_first):
                    rendered = "\n".join(
                        f"{i}. " + _NUMBERED.sub("", ln) for i, ln in enumerate(lines, 1))
                else:
                    rendered = " ".join(lines)

                text_blocks.append((rect.y0, rendered))

            for _y, rendered in sorted(text_blocks + table_blocks, key=lambda item: item[0]):
                chunks.append(rendered)

        markdown = "\n\n".join(c for c in chunks if c.strip())
        return re.sub(r"\n{3,}", "\n\n", markdown).strip() + "\n" if markdown else ""


def to_plain_text(file_bytes: bytes, *, page_indices: list[int] | None = None) -> str:
    with open_doc(file_bytes) as doc:
        indices = page_indices if page_indices is not None else list(range(doc.page_count))
        return "\n\n".join(
            doc[i].get_text() for i in indices if 0 <= i < doc.page_count
        ).strip()


def page_stats(file_bytes: bytes) -> dict:
    """How much text is actually extractable - used to warn about scans."""
    with open_doc(file_bytes) as doc:
        chars = sum(len(page.get_text().strip()) for page in doc)
        return {
            "page_count": doc.page_count,
            "characters": chars,
            "has_text_layer": chars > 0,
        }
