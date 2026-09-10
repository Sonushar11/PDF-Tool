import fitz
import pytest

from app.pdf_core import pages


def test_get_page_count(sample_pdf):
    assert pages.get_page_count(sample_pdf) == 3


def test_delete_pages(sample_pdf):
    updated = pages.delete_pages(sample_pdf, [1])
    assert pages.get_page_count(updated) == 2


def test_rotate_pages(sample_pdf):
    updated = pages.rotate_pages(sample_pdf, [0], 90)
    with fitz.open(stream=updated, filetype="pdf") as doc:
        assert doc[0].rotation == 90


def test_reorder_pages(sample_pdf):
    updated = pages.reorder_pages(sample_pdf, [2, 0, 1])
    with fitz.open(stream=updated, filetype="pdf") as doc:
        assert "Sample 3" in doc[0].get_text()
        assert "Sample 1" in doc[1].get_text()
        assert "Sample 2" in doc[2].get_text()


def test_extract_pages(sample_pdf):
    updated = pages.extract_pages(sample_pdf, [0, 2])
    with fitz.open(stream=updated, filetype="pdf") as doc:
        assert doc.page_count == 2
        assert "Sample 1" in doc[0].get_text()
        assert "Sample 3" in doc[1].get_text()


def test_merge_pdfs(sample_pdf):
    other = pages.extract_pages(sample_pdf, [0])
    merged = pages.merge_pdfs([sample_pdf, other])
    assert pages.get_page_count(merged) == 4


def test_merge_pdfs_requires_input():
    with pytest.raises(ValueError):
        pages.merge_pdfs([])


def test_split_pdf(sample_pdf):
    parts = pages.split_pdf(sample_pdf, [(0, 0), (1, 2)])
    assert len(parts) == 2
    assert pages.get_page_count(parts[0]) == 1
    assert pages.get_page_count(parts[1]) == 2


def test_split_pdf_invalid_range(sample_pdf):
    with pytest.raises(ValueError):
        pages.split_pdf(sample_pdf, [(0, 10)])
