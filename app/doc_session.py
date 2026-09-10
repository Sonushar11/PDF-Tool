"""Shared helper for routes that operate on "the PDF currently loaded in the
editor" (as opposed to merge/split, which take fresh uploads per request).
All feature pages (convert, annotate, forms, redact, security, textedit) work
against this same in-memory working copy so edits compose across pages.
"""
from __future__ import annotations

from flask import abort, session

from app import store

SESSION_KEY = "doc_token"


def get_current_doc():
    token = session.get(SESSION_KEY)
    if not token:
        return None, None
    doc = store.get_doc(token)
    if doc is None:
        session.pop(SESSION_KEY, None)
        return None, None
    return token, doc


def require_current_doc():
    token, doc = get_current_doc()
    if doc is None:
        abort(400, "No document loaded. Upload a PDF in the Editor tab first.")
    return token, doc


def set_current_doc(token: str) -> None:
    session[SESSION_KEY] = token
