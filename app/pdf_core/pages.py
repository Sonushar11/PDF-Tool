"""Page-level PDF operations: merge, split, delete, reorder, rotate, extract.

All functions take and return raw PDF bytes so callers (Flask routes) never
need to touch the filesystem — everything happens in memory.
"""
from __future__ import annotations

import fitz  # PyMuPDF


def open_doc(file_bytes: bytes) -> fitz.Document:
    return fitz.open(stream=file_bytes, filetype="pdf")


def save_doc_bytes(doc: fitz.Document) -> bytes:
    return doc.tobytes(garbage=4, deflate=True)


def get_page_count(file_bytes: bytes) -> int:
    with open_doc(file_bytes) as doc:
        return doc.page_count


def delete_pages(file_bytes: bytes, page_indices: list[int]) -> bytes:
    """page_indices are 0-based indices to remove."""
    with open_doc(file_bytes) as doc:
        doc.delete_pages(page_indices)
        return save_doc_bytes(doc)


def reorder_pages(file_bytes: bytes, new_order: list[int]) -> bytes:
    """new_order is a permutation of 0-based original page indices giving the
    desired output order, e.g. [2, 0, 1] moves the last page first."""
    with open_doc(file_bytes) as doc:
        doc.select(new_order)
        return save_doc_bytes(doc)


def rotate_pages(file_bytes: bytes, page_indices: list[int], angle: int) -> bytes:
    """angle is added to each page's current rotation (e.g. 90, 180, 270, -90)."""
    with open_doc(file_bytes) as doc:
        for i in page_indices:
            page = doc[i]
            page.set_rotation((page.rotation + angle) % 360)
        return save_doc_bytes(doc)


def extract_pages(file_bytes: bytes, page_indices: list[int]) -> bytes:
    """Returns a new PDF containing only the given pages, in the given order."""
    with open_doc(file_bytes) as doc:
        doc.select(page_indices)
        return save_doc_bytes(doc)


def merge_pdfs(file_bytes_list: list[bytes]) -> bytes:
    if not file_bytes_list:
        raise ValueError("No files provided to merge.")
    merged = fitz.open()
    try:
        for file_bytes in file_bytes_list:
            with open_doc(file_bytes) as src:
                merged.insert_pdf(src)
        return save_doc_bytes(merged)
    finally:
        merged.close()


def split_pdf(file_bytes: bytes, ranges: list[tuple[int, int]]) -> list[bytes]:
    """ranges is a list of (start, end) 0-based inclusive page index pairs.
    Returns one PDF's bytes per range."""
    outputs = []
    with open_doc(file_bytes) as doc:
        for start, end in ranges:
            if start < 0 or end >= doc.page_count or start > end:
                raise ValueError(f"Invalid page range: {start}-{end}")
            part = fitz.open()
            try:
                part.insert_pdf(doc, from_page=start, to_page=end)
                outputs.append(save_doc_bytes(part))
            finally:
                part.close()
    return outputs


def interval_ranges(page_count: int, every: int) -> list[tuple[int, int]]:
    """Ranges that cut a document into fixed-size chunks.

    `every=2` over 20 pages gives 10 pairs. A trailing chunk shorter than
    `every` is kept rather than dropped, so 21 pages give 10 pairs plus a
    single-page file.
    """
    if every < 1:
        raise ValueError("Split interval must be at least 1 page.")
    if page_count < 1:
        raise ValueError("That PDF has no pages.")
    return [
        (start, min(start + every, page_count) - 1)
        for start in range(0, page_count, every)
    ]
