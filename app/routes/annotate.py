from __future__ import annotations

import base64
import json

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for

from app import store
from app.doc_session import require_current_doc
from app.pdf_core import annotate as pdf_annotate
from app.pdf_core import draw as pdf_draw
from app.pdf_core import pages as pdf_pages
from app.pdf_core import textedit as pdf_textedit

annotate_bp = Blueprint("annotate", __name__, url_prefix="/annotate")


def _parse_color(raw: str | None, default: tuple[float, float, float]):
    """Turn a '#rrggbb' form value into PyMuPDF's 0-1 RGB triple.

    Anything unparseable falls back to the default rather than failing the
    whole annotation - a bad colour shouldn't lose the user's text.
    """
    if not raw:
        return default
    value = raw.strip().lstrip("#")
    if len(value) != 6:
        return default
    try:
        return tuple(int(value[i:i + 2], 16) / 255 for i in (0, 2, 4))
    except ValueError:
        return default


@annotate_bp.route("", methods=["GET"])
def annotate_page():
    token, doc = require_current_doc()
    page_count = pdf_pages.get_page_count(doc.data)
    page_index = int(request.args.get("page", 0))
    page_index = max(0, min(page_index, page_count - 1))
    return render_template(
        "annotate.html",
        filename=doc.filename,
        page_count=page_count,
        page_index=page_index,
    )


@annotate_bp.route("/text", methods=["POST"])
def add_text():
    token, doc = require_current_doc()
    try:
        updated = pdf_annotate.add_freetext(
            doc.data,
            int(request.form["page"]),
            float(request.form["x_pct"]),
            float(request.form["y_pct"]),
            request.form.get("text", ""),
            width_pct=float(request.form.get("width_pct", 30)),
            font_size=float(request.form.get("font_size", 12)),
            color=_parse_color(request.form.get("color"), (0, 0, 0)),
        )
    except Exception as exc:
        flash(f"Could not add text: {exc}", "error")
        return redirect(url_for("annotate.annotate_page", page=request.form.get("page", 0)))
    store.update_doc(token, updated, label="add text annotation")
    flash("Text annotation added.", "success")
    return redirect(url_for("annotate.annotate_page", page=request.form.get("page", 0)))


@annotate_bp.route("/highlight", methods=["POST"])
def add_highlight():
    token, doc = require_current_doc()
    try:
        updated = pdf_annotate.add_highlight(
            doc.data,
            int(request.form["page"]),
            float(request.form["x_pct"]),
            float(request.form["y_pct"]),
            float(request.form.get("width_pct", 20)),
            float(request.form.get("height_pct", 4)),
            color=_parse_color(request.form.get("color"), (1, 0.92, 0.23)),
        )
    except Exception as exc:
        flash(f"Could not add highlight: {exc}", "error")
        return redirect(url_for("annotate.annotate_page", page=request.form.get("page", 0)))
    store.update_doc(token, updated, label="add highlight")
    flash("Highlight added.", "success")
    return redirect(url_for("annotate.annotate_page", page=request.form.get("page", 0)))


@annotate_bp.route("/stamp", methods=["POST"])
def add_stamp():
    token, doc = require_current_doc()
    file = request.files.get("image")
    if not file or not file.filename:
        flash("Choose an image to stamp onto the page.", "error")
        return redirect(url_for("annotate.annotate_page", page=request.form.get("page", 0)))
    try:
        updated = pdf_annotate.add_image_stamp(
            doc.data,
            int(request.form["page"]),
            float(request.form["x_pct"]),
            float(request.form["y_pct"]),
            float(request.form.get("width_pct", 25)),
            file.read(),
        )
    except Exception as exc:
        flash(f"Could not add stamp: {exc}", "error")
        return redirect(url_for("annotate.annotate_page", page=request.form.get("page", 0)))
    store.update_doc(token, updated, label="add stamp")
    flash("Stamp added.", "success")
    return redirect(url_for("annotate.annotate_page", page=request.form.get("page", 0)))


@annotate_bp.route("/signature", methods=["POST"])
def add_signature():
    token, doc = require_current_doc()
    data_url = request.form.get("signature_data", "")
    if not data_url or "," not in data_url:
        flash("Draw a signature before placing it.", "error")
        return redirect(url_for("annotate.annotate_page", page=request.form.get("page", 0)))
    try:
        png_bytes = base64.b64decode(data_url.split(",", 1)[1])
        updated = pdf_annotate.add_image_stamp(
            doc.data,
            int(request.form["page"]),
            float(request.form["x_pct"]),
            float(request.form["y_pct"]),
            float(request.form.get("width_pct", 25)),
            png_bytes,
        )
    except Exception as exc:
        flash(f"Could not add signature: {exc}", "error")
        return redirect(url_for("annotate.annotate_page", page=request.form.get("page", 0)))
    store.update_doc(token, updated, label="add signature")
    flash("Signature added.", "success")
    return redirect(url_for("annotate.annotate_page", page=request.form.get("page", 0)))


def _back(page_value):
    return redirect(url_for("annotate.annotate_page", page=page_value))


@annotate_bp.route("/ink", methods=["POST"])
def add_ink():
    token, doc = require_current_doc()
    page_value = request.form.get("page", 0)
    try:
        strokes = json.loads(request.form.get("strokes", "[]"))
    except json.JSONDecodeError:
        flash("Could not read the drawing.", "error")
        return _back(page_value)
    try:
        updated = pdf_draw.add_ink(
            doc.data,
            int(request.form["page"]),
            strokes,
            color=_parse_color(request.form.get("color"), (0, 0, 0)),
            width=float(request.form.get("width", 1.5)),
        )
    except Exception as exc:
        flash(f"Could not add drawing: {exc}", "error")
        return _back(page_value)
    store.update_doc(token, updated, label="add drawing")
    flash("Drawing added.", "success")
    return _back(page_value)


@annotate_bp.route("/shape", methods=["POST"])
def add_shape():
    token, doc = require_current_doc()
    page_value = request.form.get("page", 0)
    fill = (
        _parse_color(request.form.get("fill_color"), (1, 1, 1))
        if request.form.get("filled")
        else None
    )
    try:
        updated = pdf_draw.add_shape(
            doc.data,
            int(request.form["page"]),
            request.form.get("kind", "rect"),
            float(request.form["x0_pct"]),
            float(request.form["y0_pct"]),
            float(request.form["x1_pct"]),
            float(request.form["y1_pct"]),
            color=_parse_color(request.form.get("color"), (0, 0, 0)),
            fill=fill,
            width=float(request.form.get("width", 1.5)),
        )
    except Exception as exc:
        flash(f"Could not add shape: {exc}", "error")
        return _back(page_value)
    store.update_doc(token, updated, label="add shape")
    flash("Shape added.", "success")
    return _back(page_value)


@annotate_bp.route("/whiteout", methods=["POST"])
def whiteout():
    token, doc = require_current_doc()
    page_value = request.form.get("page", 0)
    try:
        updated = pdf_draw.whiteout(
            doc.data,
            int(request.form["page"]),
            float(request.form["x0_pct"]),
            float(request.form["y0_pct"]),
            float(request.form["x1_pct"]),
            float(request.form["y1_pct"]),
        )
    except Exception as exc:
        flash(f"Could not white out that area: {exc}", "error")
        return _back(page_value)
    store.update_doc(token, updated, label="whiteout area")
    flash("Area whited out - the covered content was permanently removed.", "success")
    return _back(page_value)


@annotate_bp.route("/spans/<int:index>")
def text_spans(index: int):
    """Text runs on a page, for the click-to-edit overlay."""
    _token, doc = require_current_doc()
    try:
        return jsonify(spans=pdf_textedit.list_spans(doc.data, index))
    except Exception as exc:
        return jsonify(spans=[], error=str(exc)), 400


@annotate_bp.route("/edit-text", methods=["POST"])
def edit_text():
    token, doc = require_current_doc()
    page_value = request.form.get("page", 0)
    try:
        updated = pdf_textedit.replace_span(
            doc.data,
            int(request.form["page"]),
            float(request.form["x_pct"]),
            float(request.form["y_pct"]),
            float(request.form["w_pct"]),
            float(request.form["h_pct"]),
            request.form.get("new_text", ""),
            font_size=float(request.form["font_size"])
            if request.form.get("font_size")
            else None,
        )
    except Exception as exc:
        flash(f"Could not edit that text: {exc}", "error")
        return _back(page_value)
    store.update_doc(token, updated, label="edit text")
    flash("Text updated. Check the result - fonts are approximated.", "success")
    return _back(page_value)


@annotate_bp.route("/words/<int:index>")
def page_words(index: int):
    """Word boxes for the highlighter's snap-to-text behaviour."""
    _token, doc = require_current_doc()
    try:
        return jsonify(words=pdf_annotate.list_words(doc.data, index))
    except Exception as exc:
        return jsonify(words=[], error=str(exc)), 400


@annotate_bp.route("/highlight-sweep", methods=["POST"])
def highlight_sweep():
    """Apply one highlighter stroke and answer in JSON.

    The highlighter is a continuous gesture, so this returns JSON instead of a
    redirect - reloading the whole page after every swipe would make the tool
    unusable.
    """
    token, doc = require_current_doc()
    payload = request.get_json(silent=True) or {}
    boxes = payload.get("boxes") or []
    try:
        page_index = int(payload.get("page", 0))
    except (TypeError, ValueError):
        return jsonify(ok=False, error="Bad page index."), 400

    try:
        updated = pdf_annotate.add_highlight_boxes(
            doc.data,
            page_index,
            boxes,
            color=_parse_color(payload.get("color"), (1, 0.92, 0.23)),
        )
    except Exception as exc:
        return jsonify(ok=False, error=str(exc)), 400

    store.update_doc(token, updated, label="highlight text")
    return jsonify(ok=True, count=len(boxes))
