import fitz
import pytest

from app.pdf_core import annotate, draw, textedit


# PyMuPDF annotations only weakly reference their page, so the page has to be
# held in a local for as long as the annotation is read - and plain values must
# be extracted before the document closes.

def annot_types(data, page_index=0):
    with fitz.open(stream=data, filetype="pdf") as doc:
        page = doc[page_index]
        return [a.type[1] for a in page.annots()]


def first_annot_colors(data, page_index=0):
    with fitz.open(stream=data, filetype="pdf") as doc:
        page = doc[page_index]
        return dict(next(page.annots()).colors)


def first_annot_rect(data, page_index=0):
    with fitz.open(stream=data, filetype="pdf") as doc:
        page = doc[page_index]
        rect = next(page.annots()).rect
        return (rect.x0, rect.y0, rect.x1, rect.y1)


# --- freehand ink -----------------------------------------------------------

def test_add_ink_creates_ink_annot(sample_pdf):
    updated = draw.add_ink(sample_pdf, 0, [[(10, 10), (20, 20), (30, 15)]])
    assert annot_types(updated) == ["Ink"]


def test_add_ink_applies_colour(sample_pdf):
    updated = draw.add_ink(sample_pdf, 0, [[(10, 10), (20, 20)]], color=(1, 0, 0))
    assert first_annot_colors(updated)["stroke"] == [1.0, 0.0, 0.0]


def test_add_ink_rejects_strokes_with_no_length(sample_pdf):
    with pytest.raises(ValueError):
        draw.add_ink(sample_pdf, 0, [[(5, 5)]])


def test_add_ink_rejects_empty_input(sample_pdf):
    with pytest.raises(ValueError):
        draw.add_ink(sample_pdf, 0, [])


# --- shapes -----------------------------------------------------------------

@pytest.mark.parametrize(
    "kind,expected",
    [("rect", "Square"), ("ellipse", "Circle"), ("line", "Line"), ("arrow", "Line")],
)
def test_add_shape_kinds(sample_pdf, kind, expected):
    updated = draw.add_shape(sample_pdf, 0, kind, 10, 10, 40, 30)
    assert annot_types(updated) == [expected]


def test_add_shape_fill_is_applied(sample_pdf):
    updated = draw.add_shape(sample_pdf, 0, "rect", 10, 10, 40, 30, fill=(1, 1, 0))
    assert first_annot_colors(updated)["fill"] == [1.0, 1.0, 0.0]


def test_add_shape_unfilled_has_no_fill(sample_pdf):
    updated = draw.add_shape(sample_pdf, 0, "rect", 10, 10, 40, 30, fill=None)
    assert not first_annot_colors(updated)["fill"]


def test_add_shape_rejects_unknown_kind(sample_pdf):
    with pytest.raises(ValueError):
        draw.add_shape(sample_pdf, 0, "triangle", 10, 10, 40, 30)


def test_add_shape_normalises_reversed_drag(sample_pdf):
    """Dragging bottom-right to top-left must give the same box."""
    forward = first_annot_rect(draw.add_shape(sample_pdf, 0, "rect", 10, 10, 40, 30))
    backward = first_annot_rect(draw.add_shape(sample_pdf, 0, "rect", 40, 30, 10, 10))
    assert forward == pytest.approx(backward, abs=0.01)


def test_line_keeps_its_direction(sample_pdf):
    """Arrows must not be normalised - that would flip the arrowhead."""
    forward = first_annot_rect(draw.add_shape(sample_pdf, 0, "arrow", 10, 10, 40, 30))
    backward = first_annot_rect(draw.add_shape(sample_pdf, 0, "arrow", 40, 30, 10, 10))
    # Same bounding box, but the annotation records opposite endpoints.
    assert forward == pytest.approx(backward, abs=0.01)


# --- whiteout ---------------------------------------------------------------

def test_whiteout_removes_underlying_text(sample_pdf):
    updated = draw.whiteout(sample_pdf, 0, 0, 0, 100, 100)
    with fitz.open(stream=updated, filetype="pdf") as doc:
        assert "Sample 1" not in doc[0].get_text()


def test_whiteout_leaves_other_pages_alone(sample_pdf):
    updated = draw.whiteout(sample_pdf, 0, 0, 0, 100, 100)
    with fitz.open(stream=updated, filetype="pdf") as doc:
        assert "Sample 2" in doc[1].get_text()


def test_whiteout_rejects_empty_box(sample_pdf):
    with pytest.raises(ValueError):
        draw.whiteout(sample_pdf, 0, 20, 20, 20, 20)


# --- highlight colour -------------------------------------------------------

def test_highlight_uses_given_colour(sample_pdf):
    updated = annotate.add_highlight(sample_pdf, 0, 10, 10, 30, 5, color=(0, 1, 0))
    assert first_annot_colors(updated)["stroke"] == [0.0, 1.0, 0.0]


def test_highlight_without_colour_still_works(sample_pdf):
    updated = annotate.add_highlight(sample_pdf, 0, 10, 10, 30, 5)
    assert annot_types(updated) == ["Highlight"]


# --- click-to-edit text -----------------------------------------------------

def test_list_spans_finds_page_text(sample_pdf):
    spans = textedit.list_spans(sample_pdf, 0)
    assert len(spans) == 1
    assert spans[0]["text"].strip() == "Sample 1"


def test_list_spans_returns_percentage_geometry(sample_pdf):
    span = textedit.list_spans(sample_pdf, 0)[0]
    for key in ("x_pct", "y_pct", "w_pct", "h_pct"):
        assert 0 <= span[key] <= 100


def test_list_spans_skips_blank_runs(sample_pdf):
    assert all(s["text"].strip() for s in textedit.list_spans(sample_pdf, 0))


def test_replace_span_swaps_the_text(sample_pdf):
    span = textedit.list_spans(sample_pdf, 0)[0]
    updated = textedit.replace_span(
        sample_pdf, 0, span["x_pct"], span["y_pct"], span["w_pct"], span["h_pct"], "Renamed"
    )
    with fitz.open(stream=updated, filetype="pdf") as doc:
        text = doc[0].get_text()
        assert "Sample 1" not in text
        assert "Renamed" in text


def test_replace_span_with_empty_text_just_deletes(sample_pdf):
    span = textedit.list_spans(sample_pdf, 0)[0]
    updated = textedit.replace_span(
        sample_pdf, 0, span["x_pct"], span["y_pct"], span["w_pct"], span["h_pct"], ""
    )
    with fitz.open(stream=updated, filetype="pdf") as doc:
        assert "Sample 1" not in doc[0].get_text()


def test_replace_span_rejects_empty_box(sample_pdf):
    with pytest.raises(ValueError):
        textedit.replace_span(sample_pdf, 0, 10, 10, 0, 0, "x")
