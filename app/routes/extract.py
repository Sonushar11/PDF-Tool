from __future__ import annotations

import io

from flask import Blueprint, jsonify, render_template, request, send_file

from app.doc_session import require_current_doc
from app.pdf_core import extract as pdf_extract

extract_bp = Blueprint("extract", __name__, url_prefix="/extract")


def _parse_pages(raw: str, page_count: int) -> list[int] | None:
    """'1-3,7' -> [0,1,2,6]. Empty means the whole document."""
    raw = (raw or "").strip()
    if not raw:
        return None
    indices: list[int] = []
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "-" in chunk:
            start_s, end_s = chunk.split("-", 1)
            start, end = int(start_s), int(end_s)
        else:
            start = end = int(chunk)
        if start < 1 or end > page_count or start > end:
            raise ValueError(f"Range '{chunk}' is out of bounds for a {page_count}-page PDF.")
        indices.extend(range(start - 1, end))
    return indices or None


def _options():
    return {
        "include_tables": request.values.get("tables", "1") != "0",
        "page_breaks": request.values.get("breaks", "1") != "0",
    }


@extract_bp.route("", methods=["GET"])
def extract_page():
    _token, doc = require_current_doc()
    stats = pdf_extract.page_stats(doc.data)
    pages_raw = request.args.get("pages", "")
    error = None
    markdown = ""

    try:
        indices = _parse_pages(pages_raw, stats["page_count"])
        markdown = pdf_extract.to_markdown(doc.data, page_indices=indices, **_options())
    except ValueError as exc:
        error = str(exc)
    except Exception as exc:
        error = f"Could not extract text: {exc}"

    return render_template(
        "extract.html",
        filename=doc.filename,
        stats=stats,
        markdown=markdown,
        pages_raw=pages_raw,
        include_tables=request.args.get("tables", "1") != "0",
        page_breaks=request.args.get("breaks", "1") != "0",
        error=error,
    )


@extract_bp.route("/download.md")
def download_markdown():
    _token, doc = require_current_doc()
    stats = pdf_extract.page_stats(doc.data)
    indices = _parse_pages(request.args.get("pages", ""), stats["page_count"])
    markdown = pdf_extract.to_markdown(doc.data, page_indices=indices, **_options())
    name = (doc.filename or "document.pdf").rsplit(".", 1)[0] + ".md"
    return send_file(
        io.BytesIO(markdown.encode("utf-8")),
        # Flask appends the charset itself; naming it here duplicates it.
        mimetype="text/markdown",
        as_attachment=True,
        download_name=name,
    )


@extract_bp.route("/markdown.json")
def markdown_json():
    """Machine-readable extraction.

    Kept deliberately plain - document in, Markdown out - so an MCP server can
    wrap this endpoint directly without reshaping the response.
    """
    _token, doc = require_current_doc()
    stats = pdf_extract.page_stats(doc.data)
    try:
        indices = _parse_pages(request.args.get("pages", ""), stats["page_count"])
    except ValueError as exc:
        return jsonify(ok=False, error=str(exc)), 400

    try:
        markdown = pdf_extract.to_markdown(doc.data, page_indices=indices, **_options())
    except Exception as exc:
        return jsonify(ok=False, error=str(exc)), 400

    return jsonify(
        ok=True,
        filename=doc.filename,
        page_count=stats["page_count"],
        has_text_layer=stats["has_text_layer"],
        pages=[i + 1 for i in indices] if indices else list(range(1, stats["page_count"] + 1)),
        markdown=markdown,
    )


@extract_bp.route("/text.json")
def text_json():
    """Raw text layer, no Markdown inference applied."""
    _token, doc = require_current_doc()
    stats = pdf_extract.page_stats(doc.data)
    try:
        indices = _parse_pages(request.args.get("pages", ""), stats["page_count"])
    except ValueError as exc:
        return jsonify(ok=False, error=str(exc)), 400

    return jsonify(
        ok=True,
        filename=doc.filename,
        page_count=stats["page_count"],
        has_text_layer=stats["has_text_layer"],
        text=pdf_extract.to_plain_text(doc.data, page_indices=indices),
    )
