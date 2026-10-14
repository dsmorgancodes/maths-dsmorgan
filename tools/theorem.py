"""Theorem notes: one theorem per file, input into the chapters that use it.

    uv run tools/theorem.py new complex-analysis cauchy-goursat "Cauchy--Goursat"
    uv run tools/theorem.py build complex-analysis termwise-differentiation
    uv run tools/theorem.py build complex-analysis --all

A note lives at content/notes/<course>/theorems/<slug>.tex. "build" compiles
the course master first (so numbers are current), then the note on its own as
theorems/<slug>.pdf. It keeps its number from the master ("Theorem 2.1"), and
its \\cref links to other results resolve against the master.
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NOTES = ROOT / "content" / "notes"
SLUG = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")

NOTE = """\
%! TEX root = ../master.tex
\\begin{{theorem}}[{name}]\\label{{thm:{label}}}
  % TODO: statement.
  \\thmsource{{\\cite[ch.~N]{{key}}}}
\\end{{theorem}}

% Optional: only for results that matter.
% \\begin{{proof}}
% \\end{{proof}}
"""

WRAPPER = """\
\\documentclass[11pt,a4paper]{{article}}
\\usepackage{{dsmorgan}}
\\usepackage{{xr}}
\\externaldocument{{external}}
\\title{{{name}}}
\\subtitle{{{course}, Theorem {number}}}
\\author{{Drew M. Schaffner}}
\\date{{}}
\\begin{{document}}
\\maketitle
\\renewcommand{{\\thetheorem}}{{{number}}}
\\input{{theorems/{slug}}}
{references}\\end{{document}}
"""

THEOREM = re.compile(
    r"\\begin\{theorem\}(?:\[(?P<name>[^\]]*)\])?\s*\\label\{(?P<label>[^}]+)\}"
)
NEWLABEL = re.compile(r"\\newlabel\{(?P<label>[^}]+)\}\{\{(?P<number>[^}]*)\}")
TITLE = re.compile(r"\\title\{([^}]*)\}")
LABEL_WARNING = re.compile(
    r"(?:Reference|Citation|Label) `[^']+' (?:on page \d+ undefined|multiply defined)"
)


def parse_note(text: str) -> tuple[str, str]:
    """Return (name, label) of the single theorem in a note."""
    found = list(THEOREM.finditer(text))
    if len(found) != 1:
        raise ValueError(f"expected exactly one labelled theorem, found {len(found)}")
    m = found[0]
    return (m["name"] or "Theorem"), m["label"]


def label_number(aux: str, label: str) -> str:
    for m in NEWLABEL.finditer(aux):
        if m["label"] == label:
            return m["number"]
    raise KeyError(f"{label} is not in the master; is the note \\input by a chapter?")


def external_aux(aux: str, label: str) -> str:
    """The master's labels, minus the note's own (it is defined again locally)."""
    keep = []
    for line in aux.splitlines():
        m = NEWLABEL.match(line)
        if m and m["label"] not in (label, label + "@cref"):
            keep.append(line)
    return "\n".join(keep) + "\n"


def wrapper(name: str, course: str, number: str, slug: str, references: bool) -> str:
    return WRAPPER.format(
        name=name,
        course=course,
        number=number,
        slug=slug,
        references="\\input{references}\n" if references else "",
    )


def latexmk(tex: Path, outdir: Path, env: dict | None = None) -> None:
    """Compile tex into outdir. Never writes beside the source, so an editor's
    continuous build (VimTeX's latexmk -pvc) of the same file is untouched."""
    result = subprocess.run(
        [
            "latexmk",
            "-pdf",
            "-interaction=nonstopmode",
            "-halt-on-error",
            "-quiet",
            f"-outdir={outdir}",
            tex.name,
        ],
        check=False,
        cwd=tex.parent,
        env=env,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        log = outdir / f"{tex.stem}.log"
        text = log.read_text(errors="replace") if log.exists() else result.stdout
        errors = [
            m.group(0) for m in re.finditer(r"^!.*(?:\n.*){0,3}", text, re.MULTILINE)
        ]
        detail = "\n".join(errors) or text[-2000:]
        raise RuntimeError(f"latexmk failed on {tex}:\n{detail}")
    log = (outdir / f"{tex.stem}.log").read_text(errors="replace")
    problems = sorted(set(LABEL_WARNING.findall(log)))
    if problems:
        raise RuntimeError(f"{tex.name}: " + "; ".join(problems))


def course_dir(course: str) -> Path:
    path = NOTES / course
    if not (path / "master.tex").exists():
        raise SystemExit(f"no course at {path}")
    return path


def new(course: str, slug: str, name: str) -> Path:
    if not SLUG.fullmatch(slug):
        raise SystemExit(f"bad slug {slug!r}: use lowercase words joined by hyphens")
    path = course_dir(course) / "theorems" / f"{slug}.tex"
    if path.exists():
        raise SystemExit(f"{path} already exists")
    path.parent.mkdir(exist_ok=True)
    path.write_text(NOTE.format(name=name, label=slug))
    return path


def build(course: str, slugs: list[str]) -> list[Path]:
    root = course_dir(course)
    title = TITLE.search((root / "master.tex").read_text())
    course_title = title[1] if title else course
    references = (root / "references.tex").exists()
    env = os.environ | {"TEXINPUTS": f"{root}//{os.pathsep}"}
    built = []
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        latexmk(root / "master.tex", tmp / "master")
        aux = (tmp / "master" / "master.aux").read_text()
        for slug in slugs:
            name, label = parse_note((root / "theorems" / f"{slug}.tex").read_text())
            work = tmp / slug
            work.mkdir()
            (work / "external.aux").write_text(external_aux(aux, label))
            tex = work / f"{slug}.tex"
            tex.write_text(
                wrapper(name, course_title, label_number(aux, label), slug, references)
            )
            latexmk(tex, work, env)
            out = root / "theorems" / f"{slug}.pdf"
            shutil.copyfile(work / f"{slug}.pdf", out)
            built.append(out)
    return built


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    p_new = sub.add_parser("new", help="start a theorem note")
    p_new.add_argument("course")
    p_new.add_argument("slug")
    p_new.add_argument("name", help='display name, e.g. "Cauchy--Goursat"')
    p_build = sub.add_parser("build", help="compile theorem notes as standalone PDFs")
    p_build.add_argument("course")
    p_build.add_argument("slugs", nargs="*")
    p_build.add_argument("--all", action="store_true", help="every note in the course")
    args = parser.parse_args(argv)

    if args.command == "new":
        print(new(args.course, args.slug, args.name).relative_to(ROOT))
        return
    slugs = args.slugs
    if args.all:
        slugs = sorted(
            p.stem for p in (course_dir(args.course) / "theorems").glob("*.tex")
        )
    if not slugs:
        parser.error("name some notes or pass --all")
    for out in build(args.course, slugs):
        print(out.relative_to(ROOT))


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError, KeyError) as err:
        sys.exit(str(err))
