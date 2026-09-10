"""Scanned-page legibility enhancement.

Deliberately non-generative: every operation here (denoise, contrast,
sharpen, deskew) only rearranges or rescales pixel values that are already
present on the page. Nothing here invents, upscales, or hallucinates detail
that isn't in the source scan -- important for figures like bank-statement
amounts, where a wrong guess is worse than an illegible original.
"""
from __future__ import annotations

import cv2
import fitz
import numpy as np

from app.pdf_core.pages import open_doc, save_doc_bytes
from app.pdf_core.render import _pixmap_for_dpi


def _pixmap_to_bgr(pix) -> np.ndarray:
    arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    if pix.n == 4:
        return cv2.cvtColor(arr, cv2.COLOR_RGBA2BGR)
    if pix.n == 1:
        return cv2.cvtColor(arr, cv2.COLOR_GRAY2BGR)
    return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)


def _deskew(img: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]
    coords = np.column_stack(np.where(thresh > 0))
    if coords.shape[0] < 20:
        return img  # not enough ink to estimate an angle reliably
    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle
    if abs(angle) < 0.1 or abs(angle) > 20:
        return img  # ignore near-zero or implausibly large "corrections"
    h, w = img.shape[:2]
    matrix = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    return cv2.warpAffine(img, matrix, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)


def _clahe_contrast(img: np.ndarray) -> np.ndarray:
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    l = clahe.apply(l)
    return cv2.cvtColor(cv2.merge((l, a, b)), cv2.COLOR_LAB2BGR)


def _sharpen(img: np.ndarray) -> np.ndarray:
    blurred = cv2.GaussianBlur(img, (0, 0), sigmaX=3)
    return cv2.addWeighted(img, 1.5, blurred, -0.5, 0)


def _denoise(img: np.ndarray) -> np.ndarray:
    return cv2.fastNlMeansDenoisingColored(img, None, h=6, hColor=6, templateWindowSize=7, searchWindowSize=21)


def enhance_pixmap_png(
    pix,
    *,
    deskew: bool = True,
    denoise: bool = True,
    contrast: bool = True,
    sharpen: bool = True,
    grayscale: bool = False,
) -> bytes:
    img = _pixmap_to_bgr(pix)
    if deskew:
        img = _deskew(img)
    if denoise:
        img = _denoise(img)
    if contrast:
        img = _clahe_contrast(img)
    if sharpen:
        img = _sharpen(img)
    if grayscale:
        img = cv2.cvtColor(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), cv2.COLOR_GRAY2BGR)
    ok, buf = cv2.imencode(".png", img)
    if not ok:
        raise RuntimeError("Failed to encode enhanced page image.")
    return buf.tobytes()


def enhance_pdf(
    file_bytes: bytes,
    *,
    dpi: int = 200,
    deskew: bool = True,
    denoise: bool = True,
    contrast: bool = True,
    sharpen: bool = True,
    grayscale: bool = False,
) -> bytes:
    """Rasterizes every page at `dpi` and re-embeds it after running the
    legibility pipeline above. Output is an image-based PDF (same approach as
    render.rasterize_pdf, but with enhancement applied to each page)."""
    out = fitz.open()
    try:
        with open_doc(file_bytes) as src:
            for page in src:
                pix = _pixmap_for_dpi(page, dpi)
                png = enhance_pixmap_png(
                    pix,
                    deskew=deskew,
                    denoise=denoise,
                    contrast=contrast,
                    sharpen=sharpen,
                    grayscale=grayscale,
                )
                img_page = out.new_page(width=page.rect.width, height=page.rect.height)
                img_page.insert_image(img_page.rect, stream=png)
        return save_doc_bytes(out)
    finally:
        out.close()
