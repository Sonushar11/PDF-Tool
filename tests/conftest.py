import fitz
import pytest


def make_pdf(n_pages=3, label="page", widget=False):
    doc = fitz.open()
    for i in range(n_pages):
        page = doc.new_page()
        page.insert_text((72, 72), f"{label} {i + 1}")
        if widget and i == 0:
            w = fitz.Widget()
            w.field_name = "full_name"
            w.field_type = fitz.PDF_WIDGET_TYPE_TEXT
            w.rect = fitz.Rect(72, 120, 300, 150)
            w.field_value = ""
            page.add_widget(w)
    data = doc.tobytes()
    doc.close()
    return data


@pytest.fixture
def sample_pdf():
    return make_pdf(3, "Sample")


@pytest.fixture
def form_pdf():
    return make_pdf(1, "Form", widget=True)
