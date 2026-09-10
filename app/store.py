"""In-memory, per-process store for the PDF currently being edited.

No file ever touches disk or a database here. A document lives only in this
process's RAM, keyed by a random token held in the browser's session cookie,
and is dropped after TTL_SECONDS of inactivity. This is deliberately simple
(a single dict, no Redis) because the app runs as a single Gunicorn worker
for a small internal user base -- see the Dockerfile comment.
"""
from __future__ import annotations

import secrets
import time
from dataclasses import dataclass, field

TTL_SECONDS = 60 * 60  # drop documents untouched for an hour


@dataclass
class StoredDoc:
    filename: str
    data: bytes
    updated_at: float = field(default_factory=time.time)
    history: list[tuple[str, bytes]] = field(default_factory=list)  # (label, data) for undo


_docs: dict[str, StoredDoc] = {}


def _sweep() -> None:
    cutoff = time.time() - TTL_SECONDS
    stale = [token for token, doc in _docs.items() if doc.updated_at < cutoff]
    for token in stale:
        _docs.pop(token, None)


def new_doc(filename: str, data: bytes) -> str:
    _sweep()
    token = secrets.token_urlsafe(24)
    _docs[token] = StoredDoc(filename=filename, data=data)
    return token


def get_doc(token: str) -> StoredDoc | None:
    doc = _docs.get(token)
    if doc is None:
        return None
    doc.updated_at = time.time()
    return doc


def update_doc(token: str, data: bytes, label: str = "edit") -> None:
    doc = _docs.get(token)
    if doc is None:
        raise KeyError("Unknown document token.")
    doc.history.append((label, doc.data))
    doc.history = doc.history[-20:]  # cap undo history
    doc.data = data
    doc.updated_at = time.time()


def undo(token: str) -> bool:
    doc = _docs.get(token)
    if not doc or not doc.history:
        return False
    _, previous = doc.history.pop()
    doc.data = previous
    doc.updated_at = time.time()
    return True


def drop_doc(token: str) -> None:
    _docs.pop(token, None)
