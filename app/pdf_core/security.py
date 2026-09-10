"""Password protection / encryption using pikepdf (qpdf), which handles PDF
encryption more robustly than PyMuPDF for this purpose."""
from __future__ import annotations

import io

import pikepdf


def is_encrypted(file_bytes: bytes) -> bool:
    try:
        with pikepdf.open(io.BytesIO(file_bytes)):
            return False
    except pikepdf.PasswordError:
        return True


def encrypt_pdf(
    file_bytes: bytes,
    user_password: str,
    owner_password: str | None = None,
    *,
    allow_printing: bool = True,
    allow_copy: bool = True,
    allow_modify: bool = False,
) -> bytes:
    if not user_password:
        raise ValueError("A user password is required to encrypt the PDF.")
    permissions = pikepdf.Permissions(
        extract=allow_copy,
        print_lowres=allow_printing,
        print_highres=allow_printing,
        modify_annotation=allow_modify,
        modify_assembly=allow_modify,
        modify_form=allow_modify,
        modify_other=allow_modify,
    )
    with pikepdf.open(io.BytesIO(file_bytes)) as pdf:
        out = io.BytesIO()
        pdf.save(
            out,
            encryption=pikepdf.Encryption(
                user=user_password,
                owner=owner_password or user_password,
                allow=permissions,
            ),
        )
        return out.getvalue()


def decrypt_pdf(file_bytes: bytes, password: str) -> bytes:
    try:
        with pikepdf.open(io.BytesIO(file_bytes), password=password) as pdf:
            out = io.BytesIO()
            pdf.save(out)
            return out.getvalue()
    except pikepdf.PasswordError as exc:
        raise ValueError("Incorrect password.") from exc
