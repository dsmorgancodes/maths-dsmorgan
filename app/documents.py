"""Reads what tools/publish.py built for an entry: its HTML, PDF and theorems."""

import json
import re
from dataclasses import dataclass
from pathlib import Path

from markupsafe import Markup

SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


@dataclass(frozen=True)
class TheoremNote:
    slug: str
    name: str
    number: str
    anchor: str


@dataclass(frozen=True)
class Document:
    body: Markup | None
    pdf: str | None
    theorems: tuple[TheoremNote, ...]


def load_document(directory: Path) -> Document:
    body = directory / "body.html"
    pdf = directory / "files" / f"{directory.name}.pdf"
    index = directory / "theorems.json"
    theorems = ()
    if index.is_file():
        theorems = tuple(
            TheoremNote(**note) for note in json.loads(index.read_text("utf-8"))
        )
    return Document(
        body=Markup(body.read_text("utf-8")) if body.is_file() else None,
        pdf=pdf.name if pdf.is_file() else None,
        theorems=theorems,
    )


def load_theorem(directory: Path, slug: str) -> tuple[TheoremNote, Markup] | None:
    if not SLUG.fullmatch(slug):
        return None
    note = next((t for t in load_document(directory).theorems if t.slug == slug), None)
    page = directory / "theorems" / f"{slug}.html"
    if note is None or not page.is_file():
        return None
    return note, Markup(page.read_text("utf-8"))
