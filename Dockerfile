FROM python:3.11-slim

# System dependencies required by ocrmypdf (tesseract + ghostscript) and
# pikepdf/qpdf edge cases. unpaper is optional deskew/cleanup used by ocrmypdf.
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    ghostscript \
    qpdf \
    unpaper \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Default port for local/Docker runs. Render (and most PaaS hosts) inject
# their own $PORT at runtime, which the shell-form CMD below picks up.
ENV PORT=7860
EXPOSE 7860

# Writable dirs for a non-root user (most container platforms, Render
# included, run containers as a non-root uid).
RUN useradd -m appuser && chown -R appuser /app
USER appuser

# Single worker: uploaded PDFs live in an in-process memory store keyed by a
# session token (see app/store.py) rather than a shared cache like Redis, to
# keep the stack simple for a low-traffic internal tool. Multiple workers
# would each have their own store and could "lose" a document mid-session.
# Only 2 threads (not more): the free-tier host has 512MB RAM total, and each
# concurrent OCR/enhance request can use a few hundred MB (see app/limits.py)
# -- capping concurrency bounds how many of those can pile up at once.
# Shell form (not exec-array form) so ${PORT} is expanded at container start.
CMD sh -c 'gunicorn --bind 0.0.0.0:${PORT:-7860} --workers 1 --threads 2 --timeout 180 run:app'
