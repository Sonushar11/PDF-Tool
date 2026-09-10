"""OCR via ocrmypdf (Tesseract + Ghostscript under the hood).

ocrmypdf's API works on real file paths, not in-memory streams, so this is
the one place we touch disk -- always via NamedTemporaryFile, always cleaned
up in a `finally` block, and only for the lifetime of a single request.
"""
from __future__ import annotations

import os
import tempfile

import ocrmypdf
from ocrmypdf.exceptions import PriorOcrFoundError


def ocr_pdf(
    file_bytes: bytes,
    *,
    language: str = "eng",
    force_ocr: bool = False,
    deskew: bool = True,
    optimize: int = 1,
) -> bytes:
    in_fd, in_path = tempfile.mkstemp(suffix=".pdf")
    out_fd, out_path = tempfile.mkstemp(suffix=".pdf")
    os.close(in_fd)
    os.close(out_fd)
    try:
        with open(in_path, "wb") as fh:
            fh.write(file_bytes)
        try:
            ocrmypdf.ocr(
                in_path,
                out_path,
                language=language,
                force_ocr=force_ocr,
                deskew=deskew,
                optimize=optimize,
                progress_bar=False,
            )
        except PriorOcrFoundError as exc:
            raise ValueError(
                "This PDF already has a text layer. Tick 'force OCR' to redo it anyway."
            ) from exc
        with open(out_path, "rb") as fh:
            return fh.read()
    finally:
        for path in (in_path, out_path):
            try:
                os.remove(path)
            except OSError:
                pass
