---
title: PDF Tool
emoji: 📄
colorFrom: blue
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
---

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

## Deploying to Hugging Face Spaces

1. Create a new Space, SDK = **Docker**, visibility = Public.
2. Push this repo to the Space's git remote.
3. In the Space's **Settings → Repository secrets**, set:
   - `APP_PASSWORD` — the shared password colleagues will use to log in.
   - `FLASK_SECRET_KEY` — any long random string (used to sign session cookies).
4. The Space builds the `Dockerfile` and serves on port 7860 automatically.

No file is ever written to persistent storage — uploads are processed
in-memory / short-lived temp files per request only.
