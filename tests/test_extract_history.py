import fitz
import pytest

from app import store
from app.pdf_core import annotate, extract, pages, textedit


# --- interval splitting -----------------------------------------------------

def test_interval_ranges_even_division():
    """20 pages split every 2 gives exactly 10 files."""
    assert len(pages.interval_ranges(20, 2)) == 10


def test_interval_ranges_keeps_short_final_chunk():
    ranges = pages.interval_ranges(21, 2)
    assert len(ranges) == 11
    assert ranges[-1] == (20, 20)


def test_interval_ranges_covers_every_page_once():
    covered = [p for start, end in pages.interval_ranges(17, 5) for p in range(start, end + 1)]
    assert covered == list(range(17))


def test_interval_larger_than_document_gives_one_file():
    assert pages.interval_ranges(3, 10) == [(0, 2)]


@pytest.mark.parametrize("every", [0, -1])
def test_interval_rejects_non_positive(every):
    with pytest.raises(ValueError):
        pages.interval_ranges(10, every)


def test_interval_split_produces_usable_pdfs(sample_pdf):
    parts = pages.split_pdf(sample_pdf, pages.interval_ranges(3, 2))
    assert len(parts) == 2
    counts = []
    for part in parts:
        with fitz.open(stream=part, filetype="pdf") as doc:
            counts.append(doc.page_count)
    assert counts == [2, 1]


# --- markdown extraction ----------------------------------------------------

@pytest.fixture
def structured_pdf():
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 70), "Main Title", fontsize=24, fontname="hebo")
    page.insert_text((50, 120), "Body copy at the normal size for this document.", fontsize=11)
    page.insert_text((50, 150), "Second body line also at the normal size here.", fontsize=11)
    page.insert_text((50, 190), "A Subheading", fontsize=15, fontname="hebo")
    page.insert_text((50, 220), "Closing body paragraph at the normal size again.", fontsize=11)
    data = doc.tobytes()
    doc.close()
    return data


def test_markdown_detects_top_level_heading(structured_pdf):
    assert "# Main Title" in extract.to_markdown(structured_pdf)


def test_markdown_detects_subheading(structured_pdf):
    md = extract.to_markdown(structured_pdf)
    assert "## A Subheading" in md or "### A Subheading" in md


def test_markdown_keeps_body_text_unheaded(structured_pdf):
    for line in extract.to_markdown(structured_pdf).splitlines():
        if "Body copy at the normal size" in line:
            assert not line.startswith("#")


def test_markdown_marks_italic(sample_pdf):
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 100), "slanted words", fontsize=11, fontname="tiit")
    data = doc.tobytes()
    doc.close()
    assert "*slanted words*" in extract.to_markdown(data)


def test_markdown_page_breaks_can_be_disabled(sample_pdf):
    assert "<!-- page" not in extract.to_markdown(sample_pdf, page_breaks=False)


def test_markdown_page_breaks_present_by_default(sample_pdf):
    assert "<!-- page 2 -->" in extract.to_markdown(sample_pdf)


def test_markdown_respects_page_selection(sample_pdf):
    md = extract.to_markdown(sample_pdf, page_indices=[0])
    assert "Sample 1" in md
    assert "Sample 2" not in md


def test_markdown_of_empty_selection_is_empty(sample_pdf):
    assert extract.to_markdown(sample_pdf, page_indices=[]) == ""


def test_markdown_ignores_out_of_range_pages(sample_pdf):
    assert extract.to_markdown(sample_pdf, page_indices=[99]) == ""


def test_page_stats_reports_text_layer(sample_pdf):
    stats = extract.page_stats(sample_pdf)
    assert stats["page_count"] == 3
    assert stats["has_text_layer"] is True


def test_page_stats_flags_a_scan_with_no_text():
    doc = fitz.open()
    doc.new_page()
    data = doc.tobytes()
    doc.close()
    assert extract.page_stats(data)["has_text_layer"] is False


def test_plain_text_extraction(sample_pdf):
    assert "Sample 2" in extract.to_plain_text(sample_pdf, page_indices=[1])


# --- highlighter sweep ------------------------------------------------------

def test_list_words_returns_each_word(sample_pdf):
    words = annotate.list_words(sample_pdf, 0)
    assert [w["text"] for w in words] == ["Sample", "1"]


def test_list_words_geometry_is_percentages(sample_pdf):
    for word in annotate.list_words(sample_pdf, 0):
        for key in ("x_pct", "y_pct", "w_pct", "h_pct"):
            assert 0 <= word[key] <= 100


def test_sweep_makes_one_annotation_for_many_words(sample_pdf):
    words = annotate.list_words(sample_pdf, 0)
    updated = annotate.add_highlight_boxes(sample_pdf, 0, words)
    with fitz.open(stream=updated, filetype="pdf") as doc:
        page = doc[0]
        annots = list(page.annots())
        assert len(annots) == 1
        assert annots[0].type[1] == "Highlight"


def test_sweep_covers_one_quad_per_word(sample_pdf):
    words = annotate.list_words(sample_pdf, 0)
    updated = annotate.add_highlight_boxes(sample_pdf, 0, words)
    with fitz.open(stream=updated, filetype="pdf") as doc:
        page = doc[0]
        assert len(next(page.annots()).vertices) // 4 == len(words)


def test_sweep_applies_colour(sample_pdf):
    words = annotate.list_words(sample_pdf, 0)
    updated = annotate.add_highlight_boxes(sample_pdf, 0, words, color=(0, 1, 0))
    with fitz.open(stream=updated, filetype="pdf") as doc:
        page = doc[0]
        assert next(page.annots()).colors["stroke"] == [0.0, 1.0, 0.0]


def test_sweep_with_no_boxes_is_rejected(sample_pdf):
    with pytest.raises(ValueError):
        annotate.add_highlight_boxes(sample_pdf, 0, [])


# --- font preservation on text edit -----------------------------------------

def _first_span(data):
    with fitz.open(stream=data, filetype="pdf") as doc:
        for block in doc[0].get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    return span
    return None


def _edit_first_span(data, new_text):
    span = textedit.list_spans(data, 0)[0]
    return textedit.replace_span(
        data, 0, span["x_pct"], span["y_pct"], span["w_pct"], span["h_pct"], new_text
    )


@pytest.mark.parametrize("fontname,expected", [
    ("hebo", "Helvetica-Bold"),
    ("tiit", "Times-Italic"),
    ("cour", "Courier"),
])
def test_edit_keeps_standard_font(fontname, expected):
    doc = fitz.open()
    doc.new_page().insert_text((50, 100), "Original words", fontsize=13, fontname=fontname)
    data = doc.tobytes()
    doc.close()

    span = _first_span(_edit_first_span(data, "Replacement words"))
    assert span["font"] == expected


def test_edit_keeps_font_size():
    doc = fitz.open()
    doc.new_page().insert_text((50, 100), "Original words", fontsize=17, fontname="helv")
    data = doc.tobytes()
    doc.close()

    assert _first_span(_edit_first_span(data, "Replacement"))["size"] == pytest.approx(17, abs=0.1)


def test_edit_keeps_colour():
    doc = fitz.open()
    doc.new_page().insert_text((50, 100), "Red words", fontsize=12,
                               fontname="helv", color=(1, 0, 0))
    data = doc.tobytes()
    doc.close()

    assert _first_span(_edit_first_span(data, "Still red"))["color"] == 0xFF0000


def test_edit_keeps_bold_flag():
    doc = fitz.open()
    doc.new_page().insert_text((50, 100), "Bold words", fontsize=12, fontname="hebo")
    data = doc.tobytes()
    doc.close()

    assert _first_span(_edit_first_span(data, "Still bold"))["flags"] & 16


def test_explicit_font_size_overrides_the_original():
    doc = fitz.open()
    doc.new_page().insert_text((50, 100), "Original", fontsize=12, fontname="helv")
    data = doc.tobytes()
    doc.close()

    span = textedit.list_spans(data, 0)[0]
    out = textedit.replace_span(data, 0, span["x_pct"], span["y_pct"],
                                span["w_pct"], span["h_pct"], "Bigger", font_size=20)
    assert _first_span(out)["size"] == pytest.approx(20, abs=0.1)


# --- undo / redo ------------------------------------------------------------

def test_redo_restores_an_undone_change(sample_pdf):
    token = store.new_doc("t.pdf", sample_pdf)
    store.update_doc(token, b"%PDF-second", label="edit")
    assert store.undo(token) is True
    assert store.get_doc(token).data == sample_pdf
    assert store.redo(token) is True
    assert store.get_doc(token).data == b"%PDF-second"
    store.drop_doc(token)


def test_redo_without_an_undo_does_nothing(sample_pdf):
    token = store.new_doc("t.pdf", sample_pdf)
    assert store.redo(token) is False
    store.drop_doc(token)


def test_editing_after_undo_clears_the_redo_stack(sample_pdf):
    token = store.new_doc("t.pdf", sample_pdf)
    store.update_doc(token, b"%PDF-a", label="a")
    store.undo(token)
    store.update_doc(token, b"%PDF-b", label="b")      # forks the timeline
    assert store.redo(token) is False
    store.drop_doc(token)


def test_undo_redo_round_trips_repeatedly(sample_pdf):
    token = store.new_doc("t.pdf", sample_pdf)
    store.update_doc(token, b"%PDF-1", label="1")
    store.update_doc(token, b"%PDF-2", label="2")
    assert store.undo(token) and store.undo(token)
    assert store.get_doc(token).data == sample_pdf
    assert store.redo(token) and store.redo(token)
    assert store.get_doc(token).data == b"%PDF-2"
    store.drop_doc(token)


def test_history_is_capped(sample_pdf):
    token = store.new_doc("t.pdf", sample_pdf)
    for i in range(store.HISTORY_LIMIT + 10):
        store.update_doc(token, f"%PDF-{i}".encode(), label=str(i))
    assert len(store.get_doc(token).history) == store.HISTORY_LIMIT
    store.drop_doc(token)
