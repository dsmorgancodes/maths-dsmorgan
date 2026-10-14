from datetime import date

import pytest

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
    for anchor in (b'id="mission"', b'id="presuppositions"', b'id="code"', b'id="using"'):
        assert anchor in about

    missing = client.get("/no-such-page")
    assert missing.status_code == 404
    assert b'name="robots" content="noindex"' in missing.data
