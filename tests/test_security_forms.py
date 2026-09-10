import pytest

from app.pdf_core import formsio, security


def test_encrypt_decrypt_roundtrip(sample_pdf):
    encrypted = security.encrypt_pdf(sample_pdf, "userpw", "ownerpw")
    assert security.is_encrypted(encrypted) is True
    decrypted = security.decrypt_pdf(encrypted, "userpw")
    assert security.is_encrypted(decrypted) is False


def test_decrypt_wrong_password_raises(sample_pdf):
    encrypted = security.encrypt_pdf(sample_pdf, "userpw")
    with pytest.raises(ValueError):
        security.decrypt_pdf(encrypted, "wrongpw")


def test_encrypt_requires_password(sample_pdf):
    with pytest.raises(ValueError):
        security.encrypt_pdf(sample_pdf, "")


def test_list_fields(form_pdf):
    fields = formsio.list_fields(form_pdf)
    assert len(fields) == 1
    assert fields[0].name == "full_name"


def test_fill_fields(form_pdf):
    updated = formsio.fill_fields(form_pdf, {"full_name": "Jane Doe"})
    fields = formsio.list_fields(updated)
    assert fields[0].value == "Jane Doe"


def test_has_form_fields(form_pdf, sample_pdf):
    assert formsio.has_form_fields(form_pdf) is True
    assert formsio.has_form_fields(sample_pdf) is False
