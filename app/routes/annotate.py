from __future__ import annotations

import base64

from flask import Blueprint, flash, redirect, render_template, request, url_for

from app import store
from app.doc_session import require_current_doc
from app.pdf_core import annotate as pdf_annotate
from app.pdf_core import pages as pdf_pages

annotate_bp = Blueprint("annotate", __name__, url_prefix="/annotate")


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
