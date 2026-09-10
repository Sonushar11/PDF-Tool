"""AcroForm field read/write.

'Flatten' is deliberately implemented as rasterizing the page (reusing
render.rasterize_pdf) after filling values in, rather than a bespoke
content-stream bake: it's an honest trade-off (the page becomes a static
image, so text stops being selectable) rather than a half-working attempt at
true PDF flattening, which is notoriously fiddly to get right for every field
type/appearance stream.
"""
from __future__ import annotations

from dataclasses import dataclass

import fitz  # PyMuPDF

from app.pdf_core.pages import open_doc, save_doc_bytes


@dataclass
class FieldInfo:
    page_index: int
    name: str
    field_type: str
    value: str
    rect: tuple[float, float, float, float]


def list_fields(file_bytes: bytes) -> list[FieldInfo]:
    fields = []
    with open_doc(file_bytes) as doc:
        for page_index, page in enumerate(doc):
            for widget in page.widgets() or []:
                fields.append(
                    FieldInfo(
                        page_index=page_index,
                        name=widget.field_name or "",
                        field_type=widget.field_type_string or "",
                        value=str(widget.field_value) if widget.field_value is not None else "",
                        rect=tuple(widget.rect),
                    )
                )
    return fields


def fill_fields(file_bytes: bytes, values: dict[str, str]) -> bytes:
    with open_doc(file_bytes) as doc:
        for page in doc:
            for widget in page.widgets() or []:
                if widget.field_name in values:
                    widget.field_value = values[widget.field_name]
                    widget.update()
        return save_doc_bytes(doc)


def has_form_fields(file_bytes: bytes) -> bool:
    with open_doc(file_bytes) as doc:
        return bool(doc.is_form_pdf)
