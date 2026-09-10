from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for

from app import store
from app.doc_session import require_current_doc
from app.pdf_core import enhance as pdf_enhance
from app.pdf_core import ocr as pdf_ocr
from app.pdf_core import pages as pdf_pages
from app.pdf_core import render as pdf_render

convert_bp = Blueprint("convert", __name__, url_prefix="/convert")


@convert_bp.route("", methods=["GET"])
def convert_page():
    token, doc = require_current_doc()
    page_count = pdf_pages.get_page_count(doc.data)
    return render_template("convert.html", filename=doc.filename, page_count=page_count)


@convert_bp.route("/dpi", methods=["POST"])
def change_dpi():
    token, doc = require_current_doc()
    try:
        dpi = int(request.form.get("dpi", 150))
        if not (30 <= dpi <= 1200):
            raise ValueError("DPI must be between 30 and 1200.")
        updated = pdf_render.rasterize_pdf(doc.data, dpi)
    except Exception as exc:
        flash(f"Could not change DPI: {exc}", "error")
        return redirect(url_for("convert.convert_page"))
    store.update_doc(token, updated, label=f"rasterize at {dpi} DPI")
    flash(f"Rasterized all pages at {dpi} DPI.", "success")
    return redirect(url_for("convert.convert_page"))


@convert_bp.route("/enhance", methods=["POST"])
def enhance():
    token, doc = require_current_doc()
    try:
        dpi = int(request.form.get("dpi", 200))
        updated = pdf_enhance.enhance_pdf(
            doc.data,
            dpi=dpi,
            deskew="deskew" in request.form,
            denoise="denoise" in request.form,
            contrast="contrast" in request.form,
            sharpen="sharpen" in request.form,
            grayscale="grayscale" in request.form,
        )
    except Exception as exc:
        flash(f"Could not enhance pages: {exc}", "error")
        return redirect(url_for("convert.convert_page"))
    store.update_doc(token, updated, label="enhance scan")
    flash("Applied legibility enhancement to all pages. This sharpens/contrasts "
          "existing pixels only - it does not invent any missing data.", "success")
    return redirect(url_for("convert.convert_page"))


@convert_bp.route("/ocr", methods=["POST"])
def ocr():
    token, doc = require_current_doc()
    try:
        updated = pdf_ocr.ocr_pdf(
            doc.data,
            language=request.form.get("language", "eng"),
            force_ocr="force_ocr" in request.form,
            deskew="deskew" in request.form,
        )
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(url_for("convert.convert_page"))
    except Exception as exc:
        flash(f"OCR failed: {exc}", "error")
        return redirect(url_for("convert.convert_page"))
    store.update_doc(token, updated, label="OCR")
    flash("OCR complete - the PDF now has a searchable text layer.", "success")
    return redirect(url_for("convert.convert_page"))
