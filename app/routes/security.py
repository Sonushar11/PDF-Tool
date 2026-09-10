from __future__ import annotations

import io

from flask import Blueprint, flash, redirect, render_template, request, send_file, url_for

from app import store
from app.doc_session import get_current_doc, set_current_doc
from app.pdf_core import security as pdf_security

security_bp = Blueprint("security", __name__, url_prefix="/security")


@security_bp.route("", methods=["GET"])
def security_page():
    token, doc = get_current_doc()
    return render_template("security.html", filename=doc.filename if doc else None)


@security_bp.route("/encrypt", methods=["POST"])
def encrypt():
    token, doc = get_current_doc()
    if doc is None:
        flash("Load a PDF in the Editor tab first.", "error")
        return redirect(url_for("security.security_page"))
    user_password = request.form.get("user_password", "")
    owner_password = request.form.get("owner_password") or None
    try:
        encrypted = pdf_security.encrypt_pdf(
            doc.data,
            user_password,
            owner_password,
            allow_printing="allow_printing" in request.form,
            allow_copy="allow_copy" in request.form,
            allow_modify="allow_modify" in request.form,
        )
    except Exception as exc:
        flash(f"Could not encrypt PDF: {exc}", "error")
        return redirect(url_for("security.security_page"))
    # Encryption is a terminal export step, not saved back into the editable
    # working copy: fitz can't reopen a password-protected stream without the
    # password, which would break every other page-op route.
    return send_file(
        io.BytesIO(encrypted),
        mimetype="application/pdf",
        as_attachment=True,
        download_name="encrypted.pdf",
    )


@security_bp.route("/decrypt", methods=["POST"])
def decrypt():
    file = request.files.get("file")
    password = request.form.get("password", "")
    if not file or not file.filename:
        flash("Choose an encrypted PDF file.", "error")
        return redirect(url_for("security.security_page"))
    try:
        decrypted = pdf_security.decrypt_pdf(file.read(), password)
    except Exception as exc:
        flash(f"Could not decrypt PDF: {exc}", "error")
        return redirect(url_for("security.security_page"))

    if "load_in_editor" in request.form:
        token = store.new_doc(file.filename, decrypted)
        set_current_doc(token)
        flash("Decrypted and loaded into the editor.", "success")
        return redirect(url_for("viewer.index"))

    return send_file(
        io.BytesIO(decrypted),
        mimetype="application/pdf",
        as_attachment=True,
        download_name="decrypted.pdf",
    )
