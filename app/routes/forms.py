from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for

from app import store
from app.doc_session import require_current_doc
from app.pdf_core import formsio as pdf_formsio
from app.pdf_core import render as pdf_render

forms_bp = Blueprint("forms", __name__, url_prefix="/forms")


@forms_bp.route("", methods=["GET"])
def forms_page():
    token, doc = require_current_doc()
    fields = pdf_formsio.list_fields(doc.data)
    return render_template("forms.html", filename=doc.filename, fields=fields)


@forms_bp.route("/fill", methods=["POST"])
def fill():
    token, doc = require_current_doc()
    values = {
        key[len("field:"):]: value
        for key, value in request.form.items()
        if key.startswith("field:")
    }
    try:
        updated = pdf_formsio.fill_fields(doc.data, values)
    except Exception as exc:
        flash(f"Could not fill form: {exc}", "error")
        return redirect(url_for("forms.forms_page"))
    store.update_doc(token, updated, label="fill form fields")
    flash("Form fields updated.", "success")
    return redirect(url_for("forms.forms_page"))


@forms_bp.route("/flatten", methods=["POST"])
def flatten():
    token, doc = require_current_doc()
    try:
        dpi = int(request.form.get("dpi", 200))
        updated = pdf_render.rasterize_pdf(doc.data, dpi)
    except Exception as exc:
        flash(f"Could not flatten form: {exc}", "error")
        return redirect(url_for("forms.forms_page"))
    store.update_doc(token, updated, label="flatten form")
    flash("Form flattened to a static image - fields are no longer editable.", "success")
    return redirect(url_for("forms.forms_page"))
