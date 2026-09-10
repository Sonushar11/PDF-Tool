# PDF Tool

Internal web tool to view, edit and write PDFs: page operations (merge, split,
delete, reorder, rotate, extract), DPI/rasterization, scanned-image
enhancement, OCR, annotations, signatures, forms, redaction, encryption and
best-effort text find & replace.

## Access

The app is gated by a single shared password (see `APP_PASSWORD` below) —
anyone with the URL still needs the password to use it.

## Running locally

```bash
pip install -r requirements.txt
# also install system deps locally: tesseract-ocr, ghostscript, qpdf
set APP_PASSWORD=change-me   # PowerShell: $env:APP_PASSWORD="change-me"
set FLASK_SECRET_KEY=dev-secret
python run.py
```

## Deploying to Render (free tier)

Render's free Web Service tier supports arbitrary Dockerfiles at no cost (no
credit card), which is what this app needs for the `tesseract-ocr` /
`ghostscript` / `qpdf` system packages. (Hugging Face Spaces' Docker SDK,
originally targeted here, became a paid-only feature as of July 2026, so this
project targets Render instead.)

1. Push this repo to a GitHub (or GitLab) repository.
2. On [render.com](https://render.com), **New → Web Service**, connect that repo.
3. Render should auto-detect the `Dockerfile`. Environment: **Docker**. Instance type: **Free**.
4. Under **Environment**, add:
   - `APP_PASSWORD` — the shared password colleagues will use to log in.
   - `FLASK_SECRET_KEY` — any long random string (used to sign session cookies).
5. Deploy. Render assigns its own `$PORT` at runtime and the container's
   `CMD` binds to it automatically (see `Dockerfile`).

**Free tier limits to plan around:**
- **512MB RAM, 0.1 CPU.** Rasterizing/enhancing a page at high DPI holds
  several full-resolution image buffers in memory at once, so `app/limits.py`
  caps the DPI the UI allows (see `MAX_SAFE_DPI`) to keep a single page's
  working set well clear of that ceiling. If OCR or enhancement on an
  unusually large or high-page-count PDF still fails with an out-of-memory
  error, split the file into smaller batches first (the Split tab).
- The service **spins down after ~15 minutes of inactivity** and takes about
  a minute to wake back up on the next request.
- **750 free instance-hours per month** across your Render account.

No file is ever written to persistent storage — uploads are processed
in-memory / short-lived temp files per request only.
