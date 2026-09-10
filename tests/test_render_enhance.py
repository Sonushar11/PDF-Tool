from app.pdf_core import enhance, pages, render


def test_render_thumbnail_png(sample_pdf):
    png = render.render_thumbnail_png(sample_pdf, 0)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


def test_render_page_png(sample_pdf):
    png = render.render_page_png(sample_pdf, 0, dpi=100)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


def test_rasterize_pdf_preserves_page_count(sample_pdf):
    updated = render.rasterize_pdf(sample_pdf, dpi=100)
    assert pages.get_page_count(updated) == 3


def test_enhance_pdf_preserves_page_count(sample_pdf):
    updated = enhance.enhance_pdf(sample_pdf, dpi=100)
    assert pages.get_page_count(updated) == 3


def test_enhance_pdf_grayscale_option(sample_pdf):
    updated = enhance.enhance_pdf(sample_pdf, dpi=100, grayscale=True)
    assert pages.get_page_count(updated) == 3
