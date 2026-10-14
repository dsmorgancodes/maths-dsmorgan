"""Start a new entry by copying a template from shared/templates.

    uv run tools/new.py proof cauchy-schwarz "The Cauchy-Schwarz Inequality" -s linear-algebra
    uv run tools/new.py course calculus "Calculus" -s calculus

The slug becomes the folder name and the URL: content/notes/calculus is served
at /notes/calculus. The entry starts as a draft (published = false).
"""

import argparse
import json
import re
import shutil
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.catalog import SLUG, SUBJECTS

# kind: (template folder in shared/templates, collection folder in content)
KINDS = {
    "proof": ("graduate-proof", "graduate-proofs"),
    "course": ("course", "notes"),
}

# Build output that may be lying around in a template folder after a test compile.
BUILD_FILES = shutil.ignore_patterns(
    "*.pdf", "*.aux", "*.log", "*.fls", "*.fdb_latexmk", "*.synctex.gz",
    "*.toc", "*.out", ".DS_Store",
)  # fmt: skip

TEX_SPECIAL = {c: "\\" + c for c in "&%$#_"}


def tex_escape(text: str) -> str:
    return "".join(TEX_SPECIAL.get(c, c) for c in text)


def lecture_date(day: date) -> str:
    return f"{day:%a} {day.day} {day:%b %Y}"


def create(
    kind: str,
    slug: str,
    title: str,
    subjects: list[str] | None = None,
    root: Path = ROOT,
    today: date | None = None,
) -> Path:
    """Copy the template for `kind` to content/<collection>/<slug> and fill it in."""
    if kind not in KINDS:
        raise ValueError(f"kind must be one of: {', '.join(KINDS)}")
    if not SLUG.fullmatch(slug):
        raise ValueError(f"slug {slug!r} must be lowercase words joined by hyphens")
    unknown = [s for s in subjects or [] if s not in SUBJECTS]
    if unknown:
        raise ValueError(
            f"unknown subject {unknown[0]!r}; choose from: {', '.join(SUBJECTS)}"
        )

    template_name, collection = KINDS[kind]
    target = root / "content" / collection / slug
    if target.exists():
        raise FileExistsError(f"{target.relative_to(root)} already exists")
    shutil.copytree(
        root / "shared" / "templates" / template_name, target, ignore=BUILD_FILES
    )

    entry = target / "entry.toml"
    text = entry.read_text(encoding="utf-8")
    text = re.sub(
        r"^title = .*$",
        lambda _: f"title = {json.dumps(title, ensure_ascii=False)}",
        text,
        count=1,
        flags=re.MULTILINE,
    )
    if subjects:
        text = re.sub(
            r"^subjects = .*$",
            lambda _: f"subjects = {json.dumps(subjects)}",
            text,
            count=1,
            flags=re.MULTILINE,
        )
    entry.write_text(text, encoding="utf-8")

    day = today or date.today()
    for tex in target.glob("*.tex"):
        source = tex.read_text(encoding="utf-8")
        source = re.sub(
            r"\\title\{[^}]*\}",
            lambda _: f"\\title{{{tex_escape(title)}}}",
            source,
            count=1,
        )
        source = re.sub(
            r"\\lecture\{1\}\{[^}]*\}",
            lambda _: f"\\lecture{{1}}{{{lecture_date(day)}}}",
            source,
            count=1,
        )
        tex.write_text(source, encoding="utf-8")

    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Start a new entry from a template.")
    parser.add_argument("kind", choices=KINDS, help="what to create")
    parser.add_argument("slug", help="folder name and URL, e.g. cauchy-schwarz")
    parser.add_argument(
        "title", help='display title, e.g. "The Cauchy-Schwarz Inequality"'
    )
    parser.add_argument(
        "-s",
        "--subject",
        action="append",
        dest="subjects",
        help="subject key; repeat for more",
    )
    args = parser.parse_args(argv)

    try:
        target = create(args.kind, args.slug, args.title, args.subjects)
    except (ValueError, FileExistsError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    print(f"Created {target.relative_to(ROOT)}/")
    for path in sorted(target.iterdir()):
        print(f"  {path.name}")
    print(
        "Next: edit the summary in entry.toml, then open the .tex file and press <leader>mc."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
