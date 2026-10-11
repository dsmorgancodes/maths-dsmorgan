from dataclasses import dataclass
from datetime import date
from pathlib import Path

from flask import (
    Blueprint,
    abort,
    current_app,
    redirect,
    render_template,
    request,
    url_for,
)

from app.catalog import SUBJECTS, find_published, published_entries

pages = Blueprint("pages", __name__)


@dataclass(frozen=True)
class Section:
    endpoint: str
    title: str
    description: str
    folder: str | None = None


# Navigation order. Sections with a folder are collections under content/.
SECTIONS = (
    Section(
        "notes",
        "Notes",
        "Working notes on definitions, examples, and computations.",
        "notes",
    ),
    Section(
        "papers",
        "Papers",
        "Finished papers with their sources and figures.",
        "papers",
    ),
    Section(
        "projects",
        "Projects",
        "Computational projects with Python code, experiments, and graphics.",
        "projects",
    ),
    Section(
        "graduate_proofs",
        "Graduate Proofs",
        "Proofs written during graduate study in mathematics.",
        "graduate-proofs",
    ),
    Section(
        "about",
        "About",
        "About this archive and its author.",
    ),
)
COLLECTIONS = tuple(section for section in SECTIONS if section.folder)


def collection_dir(section: Section) -> Path:
    return Path(current_app.config["CONTENT_DIR"]) / section.folder


@pages.app_context_processor
def navigation():
    endpoint = (request.endpoint or "").removeprefix("pages.").removesuffix("_entry")
    current = next((s for s in SECTIONS if s.endpoint == endpoint), None)
    return {"sections": SECTIONS, "current_section": current}


@pages.get("/")
def index():
    recent = [
        (section, entry)
        for section in COLLECTIONS
        for entry in published_entries(collection_dir(section))
    ]
    recent.sort(key=lambda item: item[1].written or date.min, reverse=True)
    return render_template(
        "pages/index.html", collections=COLLECTIONS, recent=recent[:8]
    )


@pages.get("/about")
def about():
    return render_template("pages/about.html", subjects=SUBJECTS)


def register_collection(section: Section) -> None:
    def listing():
        entries = published_entries(collection_dir(section))
        subject = request.args.get("subject")
        if subject is not None:
            if subject not in SUBJECTS:
                abort(404)
            entries = [entry for entry in entries if subject in entry.subjects]
        return render_template(
            "pages/collection.html",
            section=section,
            entries=entries,
            subjects=SUBJECTS,
            active_subject=subject,
        )

    def entry(slug):
        found = find_published(collection_dir(section), slug)
        if found is None:
            abort(404)
        return render_template("pages/entry.html", section=section, entry=found)

    pages.add_url_rule(f"/{section.folder}", section.endpoint, listing)
    pages.add_url_rule(f"/{section.folder}/<slug>", f"{section.endpoint}_entry", entry)


for _section in COLLECTIONS:
    register_collection(_section)


@pages.get("/favicon.ico")
def favicon():
    return redirect(url_for("static", filename="favicon.svg"), code=301)
