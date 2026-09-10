from __future__ import annotations

import io
import zipfile

from flask import Blueprint, flash, redirect, render_template, request, send_file, url_for

from app.pdf_core import pages as pdf_pages

merge_split_bp = Blueprint("merge_split", __name__)


@merge_split_bp.route("/merge", methods=["GET"])
def merge_page():
    return render_template("merge.html")


@merge_split_bp.route("/merge", methods=["POST"])
def merge_submit():
    files = request.files.getlist("files")
    files = [f for f in files if f and f.filename]
    if len(files) < 2:
        flash("Choose at least two PDF files to merge.", "error")
        return redirect(url_for("merge_split.merge_page"))
    try:
        merged = pdf_pages.merge_pdfs([f.read() for f in files])
    except Exception as exc:
        flash(f"Could not merge files: {exc}", "error")
        return redirect(url_for("merge_split.merge_page"))
    return send_file(
        io.BytesIO(merged),
        mimetype="application/pdf",
        as_attachment=True,
        download_name="merged.pdf",
    )


@merge_split_bp.route("/split", methods=["GET"])
def split_page():
    return render_template("split.html")


def _parse_ranges(raw: str, page_count: int) -> list[tuple[int, int]]:
    ranges = []
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
        ranges.append((start - 1, end - 1))
    if not ranges:
        raise ValueError("Enter at least one page range, e.g. 1-3,4-6")
    return ranges


@merge_split_bp.route("/split", methods=["POST"])
def split_submit():
    file = request.files.get("file")
    ranges_raw = request.form.get("ranges", "")
    if not file or not file.filename:
        flash("Choose a PDF file to split.", "error")
        return redirect(url_for("merge_split.split_page"))
    data = file.read()
    try:
        page_count = pdf_pages.get_page_count(data)
        ranges = _parse_ranges(ranges_raw, page_count)
        parts = pdf_pages.split_pdf(data, ranges)
    except Exception as exc:
        flash(f"Could not split file: {exc}", "error")
        return redirect(url_for("merge_split.split_page"))

    if len(parts) == 1:
        return send_file(
            io.BytesIO(parts[0]),
            mimetype="application/pdf",
            as_attachment=True,
            download_name="split_part1.pdf",
        )

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for i, part in enumerate(parts, start=1):
            zf.writestr(f"split_part{i}.pdf", part)
    buffer.seek(0)
    return send_file(buffer, mimetype="application/zip", as_attachment=True, download_name="split_parts.zip")
