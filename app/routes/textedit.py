from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for

from app import store
from app.doc_session import require_current_doc
from app.pdf_core import textedit as pdf_textedit

textedit_bp = Blueprint("textedit", __name__, url_prefix="/textedit")


@textedit_bp.route("", methods=["GET"])
def textedit_page():
    token, doc = require_current_doc()
    return render_template("textedit.html", filename=doc.filename)


@textedit_bp.route("/replace", methods=["POST"])
def replace():
    token, doc = require_current_doc()
    find_text = request.form.get("find_text", "")
    replace_text = request.form.get("replace_text", "")
    try:
        updated, count = pdf_textedit.find_and_replace(doc.data, find_text, replace_text)
    except Exception as exc:
        flash(f"Could not replace text: {exc}", "error")
        return redirect(url_for("textedit.textedit_page"))
    if count == 0:
        flash(f"No occurrences of '{find_text}' were found.", "info")
        return redirect(url_for("textedit.textedit_page"))
    store.update_doc(token, updated, label="find & replace text")
    flash(f"Replaced {count} occurrence(s). Check the result carefully - "
          "font/position is approximated, not exact.", "success")
    return redirect(url_for("textedit.textedit_page"))
