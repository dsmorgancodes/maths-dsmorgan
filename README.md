# maths.dsmorgan.com

Notes, papers, projects, and graduate proofs by Drew M. Schaffner, served
by Flask. The repository is a public workshop; the website shows only entries
explicitly marked as published.

## Layout

```text
content/
  notes/  papers/  projects/  graduate-proofs/
    <slug>/entry.toml     # metadata; sources, code, and figures live beside it
  about/
shared/                   # bibliography and document templates
app/                      # Flask application
tools/                    # rendering and publishing scripts
tests/
build/                    # generated output (ignored)
```

## Entries

Each entry is a folder under a collection. Its folder name is the URL slug
(lowercase words joined by hyphens), so `content/notes/eigenvectors/` is
served at `/notes/eigenvectors`.

```toml
# content/notes/eigenvectors/entry.toml
title = "Eigenvectors by example"
summary = "Directions a matrix only stretches."
subjects = ["linear-algebra"]
written = 2026-10-01
published = false
```

Only `title` is required. Entries stay off the site until
`published = true`. Subjects must be one of: `artificial-intelligence`,
`group-theory`, `data-science`, `linear-algebra`, `real-analysis`,
`calculus`, `graph-theory`, `topology`, `complex-analysis`,
`analytic-geometry`, `foundations`, `classical-mechanics` (defined in
`app/catalog.py`).

## Writing

Proofs, papers, and course notes are LaTeX; projects with code are Quarto.
Every LaTeX document loads the house style with `\usepackage{dsmorgan}`
(`shared/latex/dsmorgan.sty`: EB Garamond, A4, boxed theorems, `\cref`,
`\lecture`). Make it visible to TeX once per machine:

```sh
mkdir -p ~/Library/texmf/tex/latex
ln -s "$PWD/shared/latex" ~/Library/texmf/tex/latex/dsmorgan
```

Start an entry from a template in `shared/templates`:

```sh
uv run tools/new.py proof cauchy-schwarz "The Cauchy-Schwarz Inequality" -s linear-algebra
uv run tools/new.py course calculus "Calculus" -s calculus
```

A course is one entry: `master.tex` inputs one `lec_NN.tex` per lecture.
Topic notes use `\chapter{2}{Power Series}` instead of `\lecture` (no date).
Images go in the entry's `figures/` folder: `\includegraphics{name}`.
Computations use `\begin{solution}`; arguments use `\begin{proof}`.
Compiled PDFs and LaTeX build files are ignored by git.

Each usable theorem is its own note, `theorems/<slug>.tex`: one labelled
`theorem` ending in `\thmsource{\cite[ch.~5]{key}}`, plus a proof only when
the result matters. Chapters `\input` the note and follow it with the worked
examples that use it. The bibliography lives in `references.tex`, which the
master inputs. Each note also builds as a standalone PDF that keeps its number
from the master:

```sh
uv run tools/theorem.py new complex-analysis cauchy-goursat "Cauchy--Goursat"
uv run tools/theorem.py build complex-analysis --all
```

Cite sources by chapter only unless the page or theorem number has been checked
against the book itself.

Validate every entry, including drafts, before publishing:

```sh
uv run flask --app app check-content
```

## Publishing

The site serves `build/`, not `content/`. `tools/publish.py` compiles each
entry's LaTeX twice: latexmk for the PDF download, and make4ht for the web page
(maths stays as TeX and MathJax renders it with the house macros). Course
theorem notes also get their own page, `/notes/<course>/theorems/<slug>`,
with a link back to the theorem in context and a standalone PDF.

```sh
uv run tools/publish.py                      # published entries only: what ships
uv run tools/publish.py --drafts             # every entry, to preview
uv run tools/publish.py notes/foundations    # rebuild one entry
```

Preview the built site, drafts included:

```sh
FLASK_CONTENT_DIR=build FLASK_SHOW_DRAFTS=1 uv run flask --app app run --debug --port 5001
```

A full build empties `build/` first, so a draft never ships by accident; the
site also hides unpublished entries unless `SHOW_DRAFTS` is set.

## Deploying

Cloud Run service `maths-dsmorgan` in project `dsmorgan-site`, region
`us-central1`, alongside dsmorgan.com. The image holds the app and `build/`
only (no LaTeX sources), served by gunicorn. One command builds the published
entries from scratch, runs the checks, and deploys:

```sh
tools/deploy.sh
```

`.gcloudignore` makes sure `build/` is uploaded even though git ignores it.
Cloud Run reserves paths ending in `z`, so the health check is `/health`.
CI (GitHub Actions) runs ruff and pytest and builds the image, but cannot
build documents: it has no TeX.

## Branches

- `working` - everyday writing and experiments.
- `publish` - what the website is built from.

Both are public if the repository is public. Never commit credentials,
personal data, or material you lack permission to redistribute.

## Design

Shares the dsmorgan.com palette and EB Garamond (self-hosted, SIL Open Font
License in `app/static/fonts`), with a practical layout: header navigation,
entry lists filterable by subject, and prose styles for proofs, code, tables,
and figures. The only JavaScript is MathJax, on document pages. CSS loads in
order:

- `css/tokens.css` - fonts, colors, type scale, spacing. Retheme here.
- `css/base.css` - paper background, typography, print rules.
- `css/components.css` - header, footer, entry lists, tags, filters.
- `css/pages.css` - home, entry pages, and document prose.

Inside rendered documents, statements are `.theorem`, `.definition`,
`.remark`, or `.proof` (which ends with a tombstone); `tools/publish.py`
produces these from the LaTeX. Use `.wide` for figures or animations that
should exceed the text width.

## Local development

```sh
uv sync
uv run flask --app app run --debug --port 5001
uv run pytest
uv run ruff check . && uv run ruff format --check .
```

Set `FLASK_CONTENT_DIR` to serve content from another directory. The debug
server is for local development only.
