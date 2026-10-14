"""Reads entry metadata from content/<collection>/<slug>/entry.toml."""

import re
import tomllib
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

METADATA_FILE = "entry.toml"
SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
FIELDS = {"title", "summary", "subjects", "written", "published"}

SUBJECTS = {
    "artificial-intelligence": "Artificial Intelligence",
    "group-theory": "Group Theory",
    "data-science": "Data Science",
    "linear-algebra": "Linear Algebra",
    "real-analysis": "Real Analysis",
    "calculus": "Calculus",
    "graph-theory": "Graph Theory",
    "topology": "Topology",
    "complex-analysis": "Complex Analysis",
    "analytic-geometry": "Analytic Geometry",
    "foundations": "Foundations",
    "classical-mechanics": "Classical Mechanics",
}


class CatalogError(ValueError):
    pass


@dataclass(frozen=True)
class Entry:
    slug: str
    title: str
    summary: str = ""
    subjects: tuple[str, ...] = ()
    written: date | None = None
    published: bool = False

    @property
    def subject_items(self) -> tuple[tuple[str, str], ...]:
        return tuple((subject, SUBJECTS[subject]) for subject in self.subjects)


def read_entry(directory: Path) -> Entry:
    path = directory / METADATA_FILE
    if not SLUG.fullmatch(directory.name):
        raise CatalogError(
            f"{directory}: folder names must be lowercase words joined by hyphens"
        )
    try:
        with path.open("rb") as file:
            data = tomllib.load(file)
    except tomllib.TOMLDecodeError as error:
        raise CatalogError(f"{path}: {error}") from error

    unknown = sorted(set(data) - FIELDS)
    if unknown:
        raise CatalogError(f"{path}: unknown fields {', '.join(unknown)}")

    title = data.get("title")
    if not isinstance(title, str) or not title.strip():
        raise CatalogError(f"{path}: title is required")

    summary = data.get("summary", "")
    if not isinstance(summary, str):
        raise CatalogError(f"{path}: summary must be text")

    subjects = data.get("subjects", [])
    if not isinstance(subjects, list) or not all(isinstance(s, str) for s in subjects):
        raise CatalogError(f"{path}: subjects must be a list of text")
    unknown_subjects = [s for s in subjects if s not in SUBJECTS]
    if unknown_subjects:
        raise CatalogError(
            f"{path}: unknown subjects {', '.join(unknown_subjects)}; "
            f"choose from {', '.join(SUBJECTS)}"
        )

    # TOML datetimes are also dates in Python, so reject them explicitly.
    written = data.get("written")
    if written is not None and (
        not isinstance(written, date) or isinstance(written, datetime)
    ):
        raise CatalogError(f"{path}: written must be a date such as 2026-10-11")

    published = data.get("published", False)
    if not isinstance(published, bool):
        raise CatalogError(f"{path}: published must be true or false")

    return Entry(
        slug=directory.name,
        title=title.strip(),
        summary=summary.strip(),
        subjects=tuple(subjects),
        written=written,
        published=published,
    )


def all_entries(collection_dir: Path) -> list[Entry]:
    if not collection_dir.is_dir():
        return []
    return [
        read_entry(directory)
        for directory in sorted(collection_dir.iterdir())
        if directory.is_dir() and (directory / METADATA_FILE).is_file()
    ]


def published_entries(collection_dir: Path, drafts: bool = False) -> list[Entry]:
    """Published entries (and drafts, if asked), newest first; undated last."""
    entries = sorted(
        (e for e in all_entries(collection_dir) if e.published or drafts),
        key=lambda entry: entry.title.lower(),
    )
    return sorted(entries, key=lambda entry: entry.written or date.min, reverse=True)


def find_published(
    collection_dir: Path, slug: str, drafts: bool = False
) -> Entry | None:
    directory = collection_dir / slug
    if not SLUG.fullmatch(slug) or not (directory / METADATA_FILE).is_file():
        return None
    entry = read_entry(directory)
    return entry if entry.published or drafts else None
