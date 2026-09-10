import fitz

from app.pdf_core import redact, textedit


def test_redact_text_removes_content(sample_pdf):
    updated, count = redact.redact_text(sample_pdf, "Sample 2")
    assert count >= 1
    with fitz.open(stream=updated, filetype="pdf") as doc:
        assert "Sample 2" not in doc[1].get_text()


def test_redact_text_no_match_returns_zero(sample_pdf):
    _, count = redact.redact_text(sample_pdf, "nonexistent-xyz")
    assert count == 0


def test_redact_areas(sample_pdf):
    updated = redact.redact_areas(
        sample_pdf, [{"page_index": 0, "x_pct": 0, "y_pct": 0, "width_pct": 100, "height_pct": 100}]
    )
    with fitz.open(stream=updated, filetype="pdf") as doc:
        assert "Sample 1" not in doc[0].get_text()


def test_find_and_replace(sample_pdf):
    updated, count = textedit.find_and_replace(sample_pdf, "Sample 1", "Renamed")
    assert count == 1
    with fitz.open(stream=updated, filetype="pdf") as doc:
        assert "Sample 1" not in doc[0].get_text()
        assert "Renamed" in doc[0].get_text()
