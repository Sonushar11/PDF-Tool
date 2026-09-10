from __future__ import annotations

import json

from flask import Blueprint, flash, redirect, render_template, request, url_for

from app import store
from app.doc_session import require_current_doc
from app.pdf_core import pages as pdf_pages
from app.pdf_core import redact as pdf_redact

redact_bp = Blueprint("redact", __name__, url_prefix="/redact")


@redact_bp.route("", methods=["GET"])
def redact_page():
    token, doc = require_current_doc()
    page_count = pdf_pages.get_page_count(doc.data)
    page_index = int(request.args.get("page", 0))
    page_index = max(0, min(page_index, page_count - 1))
    return render_template(
        "redact.html", filename=doc.filename, page_count=page_count, page_index=page_index
    )


@redact_bp.route("/area", methods=["POST"])
def redact_area():
    token, doc = require_current_doc()
    try:
        box = json.loads(request.form["box"])
        updated = pdf_redact.redact_areas(
            doc.data,
            [
                {
                    "page_index": int(request.form["page"]),
                    "x_pct": box["x_pct"],
                    "y_pct": box["y_pct"],
                    "width_pct": box["width_pct"],
                    "height_pct": box["height_pct"],
                }
            ],
        )
    except Exception as exc:
        flash(f"Could not redact area: {exc}", "error")
        return redirect(url_for("redact.redact_page", page=request.form.get("page", 0)))
    store.update_doc(token, updated, label="redact area")
    flash("Area permanently redacted.", "success")
    return redirect(url_for("redact.redact_page", page=request.form.get("page", 0)))


@redact_bp.route("/text", methods=["POST"])
def redact_text():
    token, doc = require_current_doc()
    search_text = request.form.get("search_text", "")
    try:
        updated, count = pdf_redact.redact_text(doc.data, search_text)
    except Exception as exc:
        flash(f"Could not redact text: {exc}", "error")
        return redirect(url_for("redact.redact_page"))
    if count == 0:
        flash(f"No occurrences of '{search_text}' were found.", "info")
        return redirect(url_for("redact.redact_page"))
    store.update_doc(token, updated, label="redact text")
    flash(f"Redacted {count} occurrence(s) of '{search_text}'.", "success")
    return redirect(url_for("redact.redact_page"))
