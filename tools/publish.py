"""Build the site's documents into build/, which is what gets deployed.

    uv run tools/publish.py                       # published entries (what ships)
    uv run tools/publish.py --drafts              # every entry, for local preview
    uv run tools/publish.py notes/foundations     # just these entries

For each entry, latexmk makes the PDF and make4ht makes the HTML (maths stays
as TeX for MathJax). The HTML is cleaned into a fragment that the site's
templates wrap. Each course theorem note also gets its own page and PDF.

    build/<folder>/<slug>/
        entry.toml  body.html  theorems.json  theorems/<note>.html
        files/<slug>.pdf  files/figures/...  files/theorems/<note>.pdf

Preview the result with:

    FLASK_CONTENT_DIR=build FLASK_SHOW_DRAFTS=1 uv run flask --app app run --debug
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from bs4 import BeautifulSoup, Comment, NavigableString

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.catalog import METADATA_FILE, all_entries
from tools import theorem

CONTENT = ROOT / "content"
BUILD = ROOT / "build"

# The LaTeX file that is the document, per collection.
MAIN = {"notes": "master.tex", "graduate-proofs": "proof.tex", "papers": "paper.tex"}

SOURCE_JUNK = shutil.ignore_patterns(
    "*.pdf", "*.aux", "*.log", "*.fls", "*.fdb_latexmk", "*.synctex.gz",
    "*.toc", "*.out", "*.thm", ".DS_Store",
)  # fmt: skip

# tex4ht's version of \newlabel: the anchor it links to, then the number.
LABEL = re.compile(
    r"\\newlabel\{(?P<label>[^}@]+)\}\{\{\\rEfLiNK\{(?P<anchor>[^}]+)\}"
    r"\{\\csname :autoref\\endcsname\{[^}]*\}(?P<number>[^}]*)\}"
)
MARKED_NOTE = re.compile(
    r"<!--\s*note:(?P<slug>[\w-]+)\s*-->(?P<html>.*?)<!--\s*/note:(?P=slug)\s*-->",
    re.DOTALL,
)
NOTE_START = re.compile(r"<!--\s*note:(?P<slug>[\w-]+)\s*-->")
NOTE_END = re.compile(r"<!--\s*/note:(?P<slug>[\w-]+)\s*-->")
# \abs*{x} sizes its bars; MathJax gets \absStar (see _mathjax.html).
STARRED = re.compile(r"\\(abs|norm|set|ip)\s*\*")
# make4ht -l names fonts like rm-lmri-10x-x-109: Latin Modern roman italic.
FONT = re.compile(r"^(?:rm|ss|tt)-lm(?P<font>[a-z]+?)-?\d")
TEX_LABEL = re.compile(r"\\label\s*\{([^}]*)\}")

# Statement environments, by the word that starts their heading.
KINDS = {
    "Theorem": "theorem",
    "Lemma": "theorem",
    "Proposition": "theorem",
    "Corollary": "theorem",
    "Definition": "definition",
    "Axiom": "definition",
}


def labels(aux: str) -> dict[str, tuple[str, str]]:
    """label -> (HTML anchor, printed number), from make4ht's .aux file."""
    return {m["label"]: (m["anchor"], m["number"]) for m in LABEL.finditer(aux)}


def mark_notes(source: Path) -> None:
    """Bracket each theorem note with HTML comments so it can be cut out of
    the course page. \\HCode only exists under tex4ht, so the PDF is unchanged."""
    for note in sorted((source / "theorems").glob("*.tex")):
        slug = note.stem
        note.write_text(
            f"\\ifdefined\\HCode\\HCode{{<!--note:{slug}-->}}\\fi\n"
            + note.read_text()
            + f"\n\\ifdefined\\HCode\\HCode{{<!--/note:{slug}-->}}\\fi\n"
        )


def make4ht(tex: Path, out: Path, work: Path) -> None:
    result = subprocess.run(
        ["make4ht", "-l", "-u", "-d", str(out), "-B", str(work), "-f", "html5",
         tex.name, "mathjax"],
        cwd=tex.parent,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        check=False,
    )  # fmt: skip
    html = out / f"{tex.stem}.html"
    if result.returncode != 0 or not html.exists():
        log = work / f"{tex.stem}.log"
        text = log.read_text(errors="replace") if log.exists() else result.stdout
        errors = re.findall(r"^!.*(?:\n.*){0,3}", text, re.MULTILINE)
        detail = "\n".join(errors[:5]) or result.stdout[-2000:]
        raise RuntimeError(f"make4ht failed on {tex}:\n{detail}")


def statement_kind(box) -> str:
    head = box.find("span", class_="head")
    word = head.get_text(" ", strip=True).split(" ")[0] if head else ""
    return KINDS.get(word, "remark")


def clean(html: str, *, refs: dict, link_base: str = "", asset_base: str) -> str:
    """Turn make4ht output (a page or a fragment of one) into the HTML that
    goes inside the site's .prose block."""
    html = STARRED.sub(r"\\\1Star", html)
    soup = BeautifulSoup(html, "html.parser")
    root = soup.body or soup

    for comment in root.find_all(string=lambda s: isinstance(s, Comment)):
        comment.extract()
    for tag in root.find_all(["script", "style", "link", "meta"]):
        tag.decompose()
    for tag in root.find_all("div", class_="maketitle"):
        tag.decompose()

    # Unit headings ("Chapter 2: Numbers and Parity") arrive as paragraphs.
    for p in root.find_all("p", id=re.compile(r"^(chapter|lecture)-")):
        p.name = "h2"
        p.attrs = {"id": p["id"], "class": ["unit"]}

    # Fonts: keep italics, bold, and small capitals; drop the rest.
    for span in root.find_all("span", class_=FONT):
        font = FONT.match(" ".join(span["class"]))["font"]
        if font.startswith("bx"):
            span.name = "strong"
            span.attrs = {}
        elif font.endswith(("i", "o")):
            span.name = "em"
            span.attrs = {}
        elif font == "csc":
            span.attrs = {"class": ["sc"]}
        else:
            span.unwrap()
    for span in root.find_all("span", class_="small-caps"):
        span.attrs = {"class": ["sc"]}

    # The rule above each unit heading.
    for p in root.find_all("p"):
        if re.fullmatch(r"\s*_{10,}\s*", p.get_text()):
            p.decompose()

    # tcolorbox > tcolorbox-content > newtheorem  ->  div.theorem
    for box in root.find_all("div", class_="tcolorbox"):
        box.attrs = {"class": [statement_kind(box)]}
        for inner in box.find_all("div", class_=["tcolorbox-content", "newtheorem"]):
            inner.unwrap()
    for box in root.find_all("div", class_="newtheorem"):
        box.attrs = {"class": [statement_kind(box)]}

    # The stylesheet draws the tombstone.
    for proof in root.find_all("div", class_="proof"):
        proof.attrs = {"class": ["proof"]}
        for text in proof.find_all(string=re.compile("\u25a1\\s*$")):
            text.replace_with(re.sub("\\s*\u25a1\\s*$", "", str(text)))

    # Numbered equations: LaTeX's numbers, as \tag, with the anchor links use.
    for env in root.find_all("div", class_="mathjax-env"):
        tex = env.get_text()
        found = [refs[name] for name in TEX_LABEL.findall(tex) if name in refs]
        tex = TEX_LABEL.sub(
            lambda m: f"\\tag{{{refs[m[1]][1]}}}" if m[1] in refs else "", tex
        )
        env.clear()
        env.append(NavigableString(tex))
        env.attrs = {"class": ["mathjax-block"]}
        if found:
            env["id"] = found[0][0]
            for anchor, _ in found[1:]:
                env.insert_before(soup.new_tag("a", id=anchor))

    for tag in root.find_all(class_="mathjax-block"):
        tag.attrs = {k: v for k, v in tag.attrs.items() if k in ("id", "class")}

    for a in root.find_all("a", href=True):
        if a["href"].startswith("#"):
            a["href"] = link_base + a["href"]
    for img in root.find_all("img", src=True):
        if not re.match(r"^(?:[a-z]+:|/)", img["src"]):
            img["src"] = f"{asset_base}/{img['src']}"
        # tex4ht's pixel sizes are too small; the stylesheet sizes figures.
        for size in ("width", "height", "style"):
            img.attrs.pop(size, None)
        if img.get("alt") == "PIC":
            figure = img.find_parent("figure")
            caption = figure.find("figcaption") if figure else None
            img["alt"] = caption.get_text(" ", strip=True) if caption else ""

    for p in root.find_all("p"):
        p.attrs = {k: v for k, v in p.attrs.items() if k == "id"}
        if not p.get_text(strip=True) and not p.find(["img", "a", "math"]):
            p.decompose()
    for div in root.find_all("div", class_="tableofcontents"):
        div.attrs = {"class": ["toc"]}

    return root.decode_contents().strip() + "\n"


def display_name(name: str) -> str:
    """A note's LaTeX name as page text: $x$ becomes \\(x\\) for MathJax."""
    name = re.sub(r"\$([^$]+)\$", r"\\(\1\\)", name)
    return name.replace("---", "\u2014").replace("--", "\u2013")


def theorem_notes(course_html: str, source: Path, refs: dict, base: str):
    """Yield (slug, name, number, anchor, html) for each note the course uses."""
    for m in MARKED_NOTE.finditer(course_html):
        slug = m["slug"]
        name, label = theorem.parse_note(
            (source / "theorems" / f"{slug}.tex").read_text()
        )
        anchor, number = refs.get(label, ("", ""))
        name = display_name(name)
        html = clean(m["html"], refs=refs, link_base=base, asset_base=f"{base}/files")
        yield slug, name, number, anchor, html


def link_notes(course_html: str, base: str) -> str:
    """In the course page, end each theorem note with a link to its own page."""
    course_html = NOTE_START.sub("", course_html)
    return NOTE_END.sub(
        lambda m: (
            f'<a class="theorem-link" href="{base}/theorems/{m["slug"]}">'
            "Theorem page</a>"
        ),
        course_html,
    )


def publish(folder: str, slug: str, out: Path) -> None:
    source = CONTENT / folder / slug
    base = f"/{folder}/{slug}"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    shutil.copyfile(source / METADATA_FILE, out / METADATA_FILE)

    main = MAIN.get(folder)
    if main is None or not (source / main).exists():
        return
    tex = source / main
    files = out / "files"
    files.mkdir()

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        theorem.latexmk(tex, tmp / "pdf")
        shutil.copyfile(tmp / "pdf" / f"{tex.stem}.pdf", files / f"{slug}.pdf")

        work = tmp / "src"
        shutil.copytree(source, work, ignore=SOURCE_JUNK)
        has_notes = (work / "theorems").is_dir()
        if has_notes:
            mark_notes(work)
        make4ht(work / main, tmp / "html", tmp / "aux")
        html = (tmp / "html" / f"{tex.stem}.html").read_text()
        refs = labels((tmp / "aux" / f"{tex.stem}.aux").read_text())

        # Figures, and anything else make4ht wrote beside the page.
        if (source / "figures").is_dir():
            shutil.copytree(source / "figures", files / "figures")
        for path in (tmp / "html").rglob("*"):
            if path.is_file() and path.suffix not in (".html", ".css"):
                target = files / path.relative_to(tmp / "html")
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, target)

    if has_notes:
        notes = list(theorem_notes(html, source, refs, base))
        if notes:
            (out / "theorems").mkdir()
            (files / "theorems").mkdir()
            index = []
            for note, name, number, anchor, note_html in notes:
                (out / "theorems" / f"{note}.html").write_text(note_html)
                index.append(
                    {"slug": note, "name": name, "number": number, "anchor": anchor}
                )
            (out / "theorems.json").write_text(json.dumps(index, indent=2) + "\n")
            for pdf in theorem.build(slug, [n["slug"] for n in index]):
                shutil.copyfile(pdf, files / "theorems" / pdf.name)
        html = link_notes(html, base)

    (out / "body.html").write_text(clean(html, refs=refs, asset_base=f"{base}/files"))


def targets(names: list[str], drafts: bool) -> list[tuple[str, str]]:
    if names:
        found = []
        for name in names:
            folder, _, slug = name.strip("/").partition("/")
            if not (CONTENT / folder / slug / METADATA_FILE).is_file():
                raise SystemExit(f"no entry at content/{folder}/{slug}")
            found.append((folder, slug))
        return found
    return [
        (folder, entry.slug)
        for folder in sorted(p.name for p in CONTENT.iterdir() if p.is_dir())
        for entry in all_entries(CONTENT / folder)
        if drafts or entry.published
    ]


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("entries", nargs="*", help="e.g. notes/foundations")
    parser.add_argument("--drafts", action="store_true", help="include drafts")
    args = parser.parse_args(argv)

    chosen = targets(args.entries, args.drafts)
    if not args.entries and BUILD.exists():
        shutil.rmtree(BUILD)  # a full build starts clean, so nothing stale ships
    failed = []
    for folder, slug in chosen:
        print(f"{folder}/{slug} ...", flush=True)
        try:
            publish(folder, slug, BUILD / folder / slug)
        except RuntimeError as error:
            failed.append(f"{folder}/{slug}")
            print(error, file=sys.stderr)
    print(f"built {len(chosen) - len(failed)} of {len(chosen)} into build/")
    if failed:
        raise SystemExit("failed: " + ", ".join(failed))


if __name__ == "__main__":
    main()
