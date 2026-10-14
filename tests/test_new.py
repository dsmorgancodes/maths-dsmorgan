import shutil
import tomllib
from datetime import date
from pathlib import Path

import pytest

from app.catalog import read_entry
from tools.new import create, main

REPO = Path(__file__).resolve().parent.parent


@pytest.fixture
def root(tmp_path):
    shutil.copytree(REPO / "shared" / "templates", tmp_path / "shared" / "templates")
    return tmp_path


def test_proof_is_a_valid_draft_with_title_filled_in(root):
    target = create(
        "proof",
        "cauchy-schwarz",
        'Cauchy–Schwarz "inequality"',
        ["linear-algebra"],
        root=root,
    )

    assert target == root / "content" / "graduate-proofs" / "cauchy-schwarz"
    entry = read_entry(target)
    assert entry.title == 'Cauchy–Schwarz "inequality"'
    assert entry.subjects == ("linear-algebra",)
    assert entry.published is False
    assert '\\title{Cauchy–Schwarz "inequality"}' in (target / "proof.tex").read_text()


def test_course_dates_the_first_lecture(root):
    target = create(
        "course", "calculus", "Calculus & Analysis", root=root, today=date(2026, 10, 13)
    )

    assert target == root / "content" / "notes" / "calculus"
    assert "\\title{Calculus \\& Analysis}" in (target / "master.tex").read_text()
    assert "\\lecture{1}{Tue 13 Oct 2026}" in (target / "lec_01.tex").read_text()
    assert (target / "figures").is_dir()
    assert tomllib.loads((target / "entry.toml").read_text())["subjects"] == [
        "calculus"
    ]


def test_build_files_in_the_template_are_not_copied(root):
    (root / "shared" / "templates" / "graduate-proof" / "proof.pdf").write_bytes(
        b"%PDF"
    )
    target = create("proof", "euler", "Euler", root=root)
    assert not (target / "proof.pdf").exists()


@pytest.mark.parametrize(
    ("kind", "slug", "subjects", "message"),
    [
        ("poem", "x", None, "kind"),
        ("proof", "Bad Slug", None, "slug"),
        ("proof", "fine", ["astrology"], "subject"),
    ],
)
def test_rejects_bad_input(root, kind, slug, subjects, message):
    with pytest.raises(ValueError, match=message):
        create(kind, slug, "Title", subjects, root=root)


def test_never_overwrites_an_existing_entry(root):
    create("proof", "euler", "Euler", root=root)
    with pytest.raises(FileExistsError):
        create("proof", "euler", "Euler again", root=root)


def test_cli_reports_errors_without_a_traceback(capsys):
    assert main(["proof", "Not A Slug", "Title"]) == 1
    assert "error: slug" in capsys.readouterr().err
