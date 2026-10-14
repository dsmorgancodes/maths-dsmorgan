import shutil

import pytest

from tools.import_obsidian import convert, main, postprocess, preprocess

needs_pandoc = pytest.mark.skipif(shutil.which("pandoc") is None, reason="no pandoc")


@pytest.fixture
def vault(tmp_path):
    root = tmp_path / "vault"
    (root / "Course" / "Graphics").mkdir(parents=True)
    (root / "Course" / "Graphics" / "Pasted image 1.png").write_bytes(b"\x89PNG")
    return root


def write(vault, text, name="Problem 1.md"):
    note = vault / "Course" / name
    note.write_text(text, encoding="utf-8")
    return note


@needs_pandoc
def test_prove_callout_becomes_exercise_then_proof(vault):
    note = write(vault, "> [!Prove]\n> The sum is $1$.\n\nBecause $x$.\n")
    latex = convert(note, vault)
    assert latex.index(r"\begin{exercise}") < latex.index("The sum is")
    assert latex.index(r"\end{exercise}") < latex.index(r"\begin{proof}")
    assert latex.index("Because") < latex.index(r"\end{proof}")


@needs_pandoc
def test_problem_callout_is_followed_by_a_solution(vault):
    latex = convert(write(vault, ">[!Problem]\n>Find $x$.\n\nIt is $2$.\n"), vault)
    assert r"\begin{solution}" in latex and r"\end{solution}" in latex


@needs_pandoc
def test_chained_display_maths_is_aligned_on_equals(vault):
    note = write(vault, "Set equal:\n$$2x = a^{2}$$$$x = a^{2}/2$$\nDone.\n")
    latex = convert(note, vault)
    assert "\\begin{align*}\n  2x &= a^{2} \\\\\n  x &= a^{2}/2\n\\end{align*}" in latex


@needs_pandoc
def test_rows_without_equals_are_gathered(vault):
    latex = convert(write(vault, "$$a+b$$\n$$c = d$$\n"), vault)
    assert r"\begin{gather*}" in latex and "&" not in latex


@needs_pandoc
def test_single_display_maths_uses_brackets(vault):
    latex = convert(write(vault, "$$\nx = 1\n$$\n"), vault)
    assert "\\[\n  x = 1\n\\]" in latex


@needs_pandoc
def test_embed_is_copied_to_figures(vault, tmp_path):
    figures = tmp_path / "figures"
    latex = convert(write(vault, "![[Pasted image 1.png]]\n"), vault, figures)
    assert (figures / "course-problem-1-1.png").read_bytes() == b"\x89PNG"
    assert r"\includegraphics[width=0.6\linewidth]{course-problem-1-1}" in latex


@needs_pandoc
def test_title_names_the_section_and_figures(vault, tmp_path):
    figures = tmp_path / "figures"
    note = write(vault, "![[Pasted image 1.png]]\n")
    latex = convert(note, vault, figures, title="Tangent Ratios")
    assert latex.startswith(r"\section{Tangent Ratios}")
    assert (figures / "tangent-ratios-1.png").exists()


def test_missing_embed_is_flagged(vault):
    markdown, notes = preprocess("![[nowhere.png]]\n", vault, None, "x")
    assert "TODO-EMBED nowhere.png" in markdown
    assert notes[0] == "missing embed nowhere.png"


def test_wikilinks_become_text(vault):
    markdown, _ = preprocess(
        "See [[Odd Proofs|odd]] and [[Euclidean]].\n", vault, None, "x"
    )
    assert "See odd and Euclidean." in markdown


def test_note_without_callout_is_flagged(vault):
    _, notes = preprocess("Let $f$ be entire.\n", vault, None, "x")
    assert "no callout" in notes[-1]


def test_headings_start_at_subsection_and_stop_at_subsubsection(vault):
    markdown, _ = preprocess("### A\n#### B\n###### C\n", vault, None, "x")
    assert markdown.splitlines()[:3] == ["## A", "### B", "### C"]


def test_postprocess_uses_house_macros_and_ascii():
    latex = postprocess("\\(x \\in \\mathbb{R}\\), 20° ≠ ◾️\n\\tightlist\n")
    assert latex == (
        "\\(x \\in \\R\\), 20\\ensuremath{^\\circ} \\ensuremath{\\neq} "
        "\\ensuremath{\\square}\n"
    )


def test_title_with_several_notes_is_an_error(vault):
    a = write(vault, "a\n", "a.md")
    b = write(vault, "b\n", "b.md")
    with pytest.raises(SystemExit):
        main([str(a), str(b), "--title", "T", "--vault", str(vault)])
