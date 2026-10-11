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
`graph-theory`, `topology` (defined in `app/catalog.py`).

Validate every entry, including drafts, before publishing:

```sh
uv run flask --app app check-content
```

## Branches

- `working` - everyday writing and experiments.
- `publish` - what the website is built from.

Both are public if the repository is public. Never commit credentials,
personal data, or material you lack permission to redistribute.

## Design

Shares the dsmorgan.com palette and EB Garamond (self-hosted, SIL Open Font
License in `app/static/fonts`), with a practical layout: header navigation,
entry lists filterable by subject, and prose styles for proofs, code, tables,
and figures. No JavaScript. CSS loads in order:

- `css/tokens.css` - fonts, colors, type scale, spacing. Retheme here.
- `css/base.css` - paper background, typography, print rules.
- `css/components.css` - header, footer, entry lists, tags, filters.
- `css/pages.css` - home, entry pages, and document prose.

Inside rendered documents, wrap statements in `.theorem`, `.definition`,
`.lemma`, or `.proof` (which ends with a tombstone), and use `.wide` for
figures or animations that should exceed the text width.

## Local development

```sh
uv sync
uv run flask --app app run --debug --port 5001
uv run pytest
uv run ruff check . && uv run ruff format --check .
```

Set `FLASK_CONTENT_DIR` to serve content from another directory. The debug
server is for local development only.
