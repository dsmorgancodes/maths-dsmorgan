import json
from datetime import date
from pathlib import Path

import pytest

from app import create_app
from app.catalog import CatalogError, published_entries, read_entry

EIGEN = """
title = "Eigenvectors <by> example"
summary = "Directions a matrix only stretches."
subjects = ["linear-algebra"]
written = 2026-10-01
published = true
"""


def test_empty_site_renders(client):
    for path in ("/", "/notes", "/papers", "/projects", "/graduate-proofs", "/about"):
        response = client.get(path)
        assert response.status_code == 200, path
    assert b"Nothing has been published yet." in client.get("/").data


def test_only_published_entries_are_public(client, content):
    content("notes", "eigenvectors", EIGEN)
    content("notes", "draft-idea", 'title = "Unfinished"\n')

    listing = client.get("/notes").data
    assert b"Eigenvectors &lt;by&gt; example" in listing
    assert b"Unfinished" not in listing
    assert b"Eigenvectors" in client.get("/").data

    entry = client.get("/notes/eigenvectors")
    assert entry.status_code == 200
    assert b"Directions a matrix only stretches." in entry.data
    assert b"October 1, 2026" in entry.data

    assert client.get("/notes/draft-idea").status_code == 404
    assert client.get("/notes/missing").status_code == 404
    assert client.get("/papers/eigenvectors").status_code == 404


def test_entries_are_newest_first_and_undated_last(content):
    content(
        "papers", "older", 'title = "Older"\nwritten = 2025-01-01\npublished = true\n'
    )
    content("papers", "undated", 'title = "Undated"\npublished = true\n')
    content(
        "papers", "newer", 'title = "Newer"\nwritten = 2026-01-01\npublished = true\n'
    )

    entries = published_entries(content.root / "papers")
    assert [entry.slug for entry in entries] == ["newer", "older", "undated"]


def test_subject_filter(client, content):
    content("projects", "eigen", EIGEN)
    content(
        "projects",
        "graphs",
        'title = "Spectral graphs"\nsubjects = ["graph-theory"]\npublished = true\n',
    )

    filtered = client.get("/projects?subject=graph-theory").data
    assert b"Spectral graphs" in filtered
    assert b"Eigenvectors" not in filtered
    assert (
        b"Nothing in projects on Topology yet."
        in client.get("/projects?subject=topology").data
    )
    assert client.get("/projects?subject=astrology").status_code == 404


def test_reads_valid_metadata(content):
    entry = read_entry(content("notes", "eigenvectors", EIGEN))
    assert entry.written == date(2026, 10, 1)
    assert entry.subject_items == (("linear-algebra", "Linear Algebra"),)
    assert entry.published is True


@pytest.mark.parametrize(
    ("slug", "text"),
    [
        ("missing-title", "published = true\n"),
        ("blank-title", 'title = "  "\n'),
        ("bad-subject", 'title = "T"\nsubjects = ["astrology"]\n'),
        ("bad-date", 'title = "T"\nwritten = "October"\n'),
        ("datetime", 'title = "T"\nwritten = 2026-10-01T09:00:00\n'),
        ("bad-flag", 'title = "T"\npublished = "yes"\n'),
        ("typo-field", 'title = "T"\npublshed = true\n'),
        ("bad-toml", 'title = "T\n'),
        ("Not_A_Slug", 'title = "T"\n'),
    ],
)
def test_rejects_invalid_metadata(content, slug, text):
    with pytest.raises(CatalogError):
        read_entry(content("notes", slug, text))


def test_check_content_command(app, content):
    content("notes", "eigenvectors", EIGEN)
    content("notes", "draft", 'title = "Draft"\n')
    runner = app.test_cli_runner()

    result = runner.invoke(args=["check-content"])
    assert result.exit_code == 0
    assert "1 published, 1 drafts." in result.output

    content("papers", "broken", 'title = "T"\nsubjects = ["astrology"]\n')
    result = runner.invoke(args=["check-content"])
    assert result.exit_code == 1
    assert "unknown subjects astrology" in result.output


def test_navigation_and_about(client):
    about = client.get("/about").data
    assert b'href="https://dsmorgan.com"' in about
    assert b'<a href="/about" aria-current="page">About</a>' in about
    for anchor in (
        b'id="mission"',
        b'id="presuppositions"',
        b'id="code"',
        b'id="using"',
    ):
        assert anchor in about

    missing = client.get("/no-such-page")
    assert missing.status_code == 404
    assert b'name="robots" content="noindex"' in missing.data


COURSE = """
title = "Foundations"
summary = "Statements and proof."
published = true
"""


def built_course(content, toml=COURSE):
    directory = content("notes", "foundations", toml)
    (directory / "body.html").write_text("<p>Body with \\(x^2\\)</p>\n")
    (directory / "files" / "theorems").mkdir(parents=True)
    (directory / "files" / "foundations.pdf").write_bytes(b"%PDF-course")
    (directory / "files" / "theorems" / "sqrt2.pdf").write_bytes(b"%PDF-note")
    (directory / "theorems").mkdir()
    (directory / "theorems" / "sqrt2.html").write_text(
        '<div class="theorem">Note</div>'
    )
    (directory / "theorems.json").write_text(
        json.dumps(
            [
                {
                    "slug": "sqrt2",
                    "name": "\\(\\sqrt2\\) is irrational",
                    "number": "6.1",
                    "anchor": "x1-7002r1",
                }
            ]
        )
    )
    return directory


def test_built_entry_shows_document_pdf_and_theorems(client, content):
    built_course(content)
    page = client.get("/notes/foundations").data.decode()
    assert "<p>Body with \\(x^2\\)</p>" in page
    assert "mathjax@3" in page and "absStar" in page
    assert 'href="/notes/foundations/files/foundations.pdf"' in page
    assert 'href="/notes/foundations/theorems/sqrt2">6.1</a>' in page

    pdf = client.get("/notes/foundations/files/foundations.pdf")
    assert pdf.status_code == 200 and pdf.data == b"%PDF-course"
    assert client.get("/notes/foundations/files/../entry.toml").status_code == 404
    assert client.get("/notes/foundations/files/missing.png").status_code == 404


def test_unbuilt_entry_has_no_mathjax(client, content):
    content("notes", "eigenvectors", EIGEN)
    page = client.get("/notes/eigenvectors").data
    assert b"mathjax" not in page and b"PDF" not in page


def test_theorem_page(client, content):
    built_course(content)
    page = client.get("/notes/foundations/theorems/sqrt2").data.decode()
    assert '<div class="theorem">Note</div>' in page
    assert "Theorem 6.1 of" in page
    assert 'href="/notes/foundations#x1-7002r1"' in page
    assert 'href="/notes/foundations/files/theorems/sqrt2.pdf"' in page
    assert "<title>\\sqrt2 is irrational | Foundations" in page
    assert 'aria-current="page">Notes' in page

    for path in (
        "/notes/foundations/theorems/missing",
        "/notes/foundations/theorems/Bad.slug",
    ):
        assert client.get(path).status_code == 404


def test_drafts_are_hidden_unless_previewing(content):
    built_course(content, COURSE.replace("true", "false"))
    for drafts, status in ((False, 404), (True, 200)):
        client = create_app(
            {"TESTING": True, "CONTENT_DIR": content.root, "SHOW_DRAFTS": drafts}
        ).test_client()
        for path in (
            "/notes/foundations",
            "/notes/foundations/theorems/sqrt2",
            "/notes/foundations/files/foundations.pdf",
        ):
            assert client.get(path).status_code == status, (path, drafts)
        listing = client.get("/notes").data
        assert (b'href="/notes/foundations"' in listing) is drafts


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200 and response.json == {"status": "ok"}


def test_serves_build_and_checks_content_by_default():
    app = create_app()
    root = Path(app.root_path).parent
    assert app.config["CONTENT_DIR"] == root / "build"
    assert app.config["SOURCE_DIR"] == root / "content"


def test_dates_are_optional(client, content):
    content("notes", "eigenvectors", EIGEN)
    content("notes", "timeless", 'title = "Timeless"\npublished = true\n')
    assert b"Undated" not in client.get("/notes").data
    page = client.get("/notes/timeless").data
    assert b"Undated" not in page and b"<time" not in page
    assert b'class="entry-meta"' not in page
    assert b"October 1, 2026" in client.get("/notes/eigenvectors").data
