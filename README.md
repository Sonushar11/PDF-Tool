# PDF Tool

[![CI](https://github.com/Sonushar11/PDF-Tool/actions/workflows/ci.yml/badge.svg)](https://github.com/Sonushar11/PDF-Tool/actions/workflows/ci.yml)

**Live demo: [pdf-tool-muwq.onrender.com](https://pdf-tool-muwq.onrender.com/)**

A web application to view, edit and write PDFs: page operations (merge, split,
delete, reorder, rotate, extract), DPI/rasterization, scanned-image
enhancement, OCR, annotations, signatures, forms, redaction, encryption and
best-effort text find & replace.

Flask and PyMuPDF, containerised with Docker, with 85 unit tests running in CI
on every push.

> The demo runs on a free tier that spins down after ~15 minutes idle, so the
> first request may take about a minute to wake.

## Access

The app is gated by a single shared password (see `APP_PASSWORD` below) —
anyone with the URL still needs the password to use it.

This is deliberate rather than leftover. Uploaded documents live in process
memory (see `app/store.py`), so the deployment cannot absorb arbitrary public
traffic on 512MB without being knocked over. The gate keeps usage to people
who have been given the password.

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest tests/ -v
```

85 tests across the PDF core: page operations, ink and shape annotation, text
extraction and markdown export, undo/redo history, redaction, rendering and
enhancement, encryption and form handling. They run automatically on every
push and pull request through GitHub Actions (`.github/workflows/ci.yml`) on a
clean Ubuntu runner with the same system packages the Dockerfile installs.

Note `python -m pytest` rather than bare `pytest`: the `-m` form puts the
repository root on `sys.path`, so `from app.pdf_core import ...` resolves.

## Running locally

```bash
pip install -r requirements.txt
# also install system deps locally: tesseract-ocr, ghostscript, qpdf
set APP_PASSWORD=change-me   # PowerShell: $env:APP_PASSWORD="change-me"
set FLASK_SECRET_KEY=dev-secret
python run.py
```

Or with Docker, which bundles the system dependencies:

```bash
docker build -t pdf-tool .
docker run -p 7860:7860 -e APP_PASSWORD=change-me -e FLASK_SECRET_KEY=dev-secret pdf-tool
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
   - `APP_PASSWORD` — the shared password users will log in with.
   - `FLASK_SECRET_KEY` — a long random string used to sign session cookies.
     Generate one with `python -c "import secrets; print(secrets.token_hex(32))"`.
     This is the real security boundary: login state lives in a signed cookie,
     so anyone who knows the key can forge a logged-in session regardless of
     the password.
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

## Architecture notes

No file is ever written to persistent storage. An uploaded PDF lives only in
the Gunicorn process's memory, keyed by a random token held in the browser
session cookie, and is dropped after an hour of inactivity (`app/store.py`).

That means **the app cannot scale horizontally as written**. A second worker
would have its own store and could not see a document uploaded through the
first, which is why the container runs a single worker with two threads. It is
a deliberate trade for a low-traffic tool: simplicity over scale, with no Redis
or object store to operate. Moving the store behind Redis, or writing uploads
to object storage keyed by session token, is the first change needed to run
more than one instance.
