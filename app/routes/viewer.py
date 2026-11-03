from __future__ import annotations

import io

from flask import Blueprint, abort, flash, redirect, request, send_file, session, url_for
from flask import render_template

from app import store
from app.doc_session import SESSION_KEY, get_current_doc, require_current_doc, set_current_doc
from app.pdf_core import pages as pdf_pages
from app.pdf_core import render as pdf_render

viewer_bp = Blueprint("viewer", __name__)

_current_doc = get_current_doc
_require_doc = require_current_doc


def _parse_indices(raw: str) -> list[int]:
    """Parses a comma/space separated list of 1-based page numbers into 0-based indices."""
    if not raw:
        return []
    result = []
    for part in raw.replace(",", " ").split():
        result.append(int(part) - 1)
    return result


@viewer_bp.route("/", methods=["GET"])
def index():
    token, doc = _current_doc()
    if doc is None:
        return render_template("upload.html")
    page_count = pdf_pages.get_page_count(doc.data)
    size_kb = len(doc.data) / 1024
    return render_template(
        "editor.html",
        filename=doc.filename,
        page_count=page_count,
        size_label=f"{size_kb / 1024:.1f} MB" if size_kb >= 1024 else f"{size_kb:.0f} KB",
        edit_count=len(doc.history),
        can_undo=bool(doc.history),
    )


@viewer_bp.route("/upload", methods=["POST"])
def upload():
    file = request.files.get("file")
    if not file or not file.filename:
        flash("Choose a PDF file to upload.", "error")
        return redirect(url_for("viewer.index"))
    data = file.read()
    try:
        pdf_pages.get_page_count(data)  # validates it opens as a PDF
    except Exception:
        flash("That file doesn't look like a valid PDF.", "error")
        return redirect(url_for("viewer.index"))
    token = store.new_doc(file.filename, data)
    set_current_doc(token)
    flash(f"Loaded {file.filename}.", "success")
    return redirect(url_for("viewer.index"))


@viewer_bp.route("/pages/thumb/<int:index>.png")
def thumbnail(index: int):
    _, doc = _require_doc()
    try:
        png = pdf_render.render_thumbnail_png(doc.data, index)
    except Exception:
        abort(404)
    return send_file(io.BytesIO(png), mimetype="image/png")

@viewer_bp.route("/pages/preview/<int:index>.png")
def preview(index: int):
    _, doc = _require_doc()
    try:
        png = pdf_render.render_page_png(doc.data, index, dpi=150)
    except Exception:
        abort(404)
    return send_file(io.BytesIO(png), mimetype="image/png")


@viewer_bp.route("/pages/delete", methods=["POST"])
def delete_pages():
    token, doc = _require_doc()
    indices = _parse_indices(request.form.get("pages", ""))
    if not indices:
        flash("Select at least one page to delete.", "error")
        return redirect(url_for("viewer.index"))
    try:
        updated = pdf_pages.delete_pages(doc.data, indices)
    except Exception as exc:
        flash(f"Could not delete pages: {exc}", "error")
        return redirect(url_for("viewer.index"))
    store.update_doc(token, updated, label="delete pages")
    flash(f"Deleted {len(indices)} page(s).", "success")
    return redirect(url_for("viewer.index"))


@viewer_bp.route("/pages/rotate", methods=["POST"])
def rotate_pages():
    token, doc = _require_doc()
    indices = _parse_indices(request.form.get("pages", ""))
    angle = int(request.form.get("angle", 90))
    if not indices:
        flash("Select at least one page to rotate.", "error")
        return redirect(url_for("viewer.index"))
    try:
        updated = pdf_pages.rotate_pages(doc.data, indices, angle)
    except Exception as exc:
        flash(f"Could not rotate pages: {exc}", "error")
        return redirect(url_for("viewer.index"))
    store.update_doc(token, updated, label="rotate pages")
    flash(f"Rotated {len(indices)} page(s).", "success")
    return redirect(url_for("viewer.index"))


@viewer_bp.route("/pages/reorder", methods=["POST"])
def reorder_pages():
    token, doc = _require_doc()
    order_raw = request.form.get("order", "")
    try:
        new_order = [int(i) for i in order_raw.split(",") if i != ""]
    except ValueError:
        flash("Invalid page order.", "error")
        return redirect(url_for("viewer.index"))
    page_count = pdf_pages.get_page_count(doc.data)
    if sorted(new_order) != list(range(page_count)):
        flash("Page order must include every page exactly once.", "error")
        return redirect(url_for("viewer.index"))
    updated = pdf_pages.reorder_pages(doc.data, new_order)
    store.update_doc(token, updated, label="reorder pages")
    flash("Page order updated.", "success")
    return redirect(url_for("viewer.index"))


@viewer_bp.route("/pages/extract", methods=["POST"])
def extract_pages():
    _, doc = _require_doc()
    indices = _parse_indices(request.form.get("pages", ""))
    if not indices:
        flash("Select at least one page to extract.", "error")
        return redirect(url_for("viewer.index"))
    try:
        extracted = pdf_pages.extract_pages(doc.data, indices)
    except Exception as exc:
        flash(f"Could not extract pages: {exc}", "error")
        return redirect(url_for("viewer.index"))
    return send_file(
        io.BytesIO(extracted),
        mimetype="application/pdf",
        as_attachment=True,
        download_name="extracted.pdf",
    )


def _safe_next() -> str:
    """Where to return after undo/redo - the page the user was actually on.

    Only same-site absolute paths are honoured; anything else (a full URL, a
    protocol-relative '//evil.example') falls back to the editor so this can't
    be used as an open redirect.
    """
    target = request.form.get("next", "")
    if target.startswith("/") and not target.startswith("//"):
        return target
    return url_for("viewer.index")


@viewer_bp.route("/undo", methods=["POST"])
def undo():
    token, _ = _require_doc()
    if store.undo(token):
        flash("Reverted last change.", "info")
    else:
        flash("Nothing to undo.", "error")
    return redirect(_safe_next())


@viewer_bp.route("/redo", methods=["POST"])
def redo():
    token, _ = _require_doc()
    if store.redo(token):
        flash("Reapplied change.", "info")
    else:
        flash("Nothing to redo.", "error")
    return redirect(_safe_next())


@viewer_bp.route("/download")
def download():
    _, doc = _require_doc()
    return send_file(
        io.BytesIO(doc.data),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=doc.filename or "document.pdf",
    )


@viewer_bp.route("/reset", methods=["POST"])
def reset():
    token = session.pop(SESSION_KEY, None)
    if token:
        store.drop_doc(token)
    flash("Cleared. Upload a new PDF to start again.", "info")
    return redirect(url_for("viewer.index"))
