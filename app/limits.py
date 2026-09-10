"""Resource caps for the deployment target's free tier (Render: 512MB RAM,
0.1 CPU). Rasterizing/enhancing a page holds several full-resolution pixel
buffers in memory at once (OpenCV denoise/CLAHE/sharpen each make a copy), so
DPI is the main lever to keep a single page's working set well under the RAM
ceiling even with a few pages processed back-to-back.

At MAX_SAFE_DPI (400) on an A4-ish page, one working buffer is roughly
3300x4700x3 bytes =~ 46MB; the enhancement pipeline's handful of intermediate
copies keeps peak usage for one page in the low hundreds of MB, leaving
headroom for Python/Flask/gunicorn's own baseline footprint. Higher DPI than
this risks an OOM kill on the free tier rather than a clean error.
"""

MIN_DPI = 30
MAX_SAFE_DPI = 400

PAGE_COUNT_WARNING_THRESHOLD = 150  # heavier ops (enhance/OCR) get slower and
# riskier past this; pages are still processed one at a time, not all held in
# memory together, so this is a soft warning rather than a hard block.


def clamp_dpi(dpi: int) -> int:
    if not (MIN_DPI <= dpi <= MAX_SAFE_DPI):
        raise ValueError(f"DPI must be between {MIN_DPI} and {MAX_SAFE_DPI} on this deployment.")
    return dpi
