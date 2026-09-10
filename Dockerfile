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

# Hugging Face Spaces (Docker SDK) expects the container to listen on 7860.
ENV PORT=7860
EXPOSE 7860

# Writable dirs for a non-root user (Spaces runs containers as a non-root uid).
RUN useradd -m appuser && chown -R appuser /app
USER appuser

# Single worker: uploaded PDFs live in an in-process memory store keyed by a
# session token (see app/store.py) rather than a shared cache like Redis, to
# keep the stack simple for a low-traffic internal tool. Multiple workers
# would each have their own store and could "lose" a document mid-session.
CMD ["gunicorn", "--bind", "0.0.0.0:7860", "--workers", "1", "--threads", "4", "--timeout", "180", "run:app"]
