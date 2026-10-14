import shutil

import pytest

from tools import theorem

AUX = r"""\relax
\citation{saff-snider}
\newlabel{thm:a}{{1.1}{1}{A}{theorem.1.1}{}}
\newlabel{thm:a@cref}{{[theorem][1][1]1.1}{[1][1][]1}{}{}{}}
\newlabel{thm:b}{{2.3}{2}{B}{theorem.2.3}{}}
\newlabel{thm:b@cref}{{[theorem][3][2]2.3}{[1][2][]2}{}{}{}}
\bibcite{saff-snider}{1}
"""


def test_parse_note_reads_name_and_label():
    text = "\\begin{theorem}[Ratio test]\\label{thm:ratio-test}\n x \n\\end{theorem}"
    assert theorem.parse_note(text) == ("Ratio test", "thm:ratio-test")


def test_parse_note_rejects_zero_or_two_theorems():
    with pytest.raises(ValueError):
        theorem.parse_note("no theorem here")
    one = "\\begin{theorem}\\label{thm:x}\\end{theorem}"
    with pytest.raises(ValueError):
        theorem.parse_note(one + one)


def test_label_number_finds_the_master_number():
    assert theorem.label_number(AUX, "thm:b") == "2.3"
    with pytest.raises(KeyError):
        theorem.label_number(AUX, "thm:missing")


def test_external_aux_keeps_other_labels_only():
    out = theorem.external_aux(AUX, "thm:b")
    assert "{thm:a}" in out and "{thm:a@cref}" in out
    assert "thm:b" not in out
    assert "bibcite" not in out and "citation" not in out


def test_wrapper_numbers_the_theorem_and_inputs_references():
    tex = theorem.wrapper("B", "Complex Analysis", "2.3", "b", references=True)
    assert "\\renewcommand{\\thetheorem}{2.3}" in tex
    assert "\\input{theorems/b}" in tex
    assert "\\input{references}" in tex
    assert "\\input{references}" not in theorem.wrapper(
        "B", "C", "1", "b", references=False
    )


@pytest.fixture
def notes(tmp_path, monkeypatch):
    course = tmp_path / "demo"
    course.mkdir()
    (course / "master.tex").write_text(
        "\\documentclass{article}\\usepackage{dsmorgan}\\title{Demo}\n"
        "\\begin{document}\\section{One}\\input{theorems/first}\\input{theorems/second}\n"
        "\\input{references}\\end{document}\n"
    )
    (course / "references.tex").write_text(
        "\\begin{thebibliography}{9}\\bibitem{book} A Book.\\end{thebibliography}\n"
    )
    monkeypatch.setattr(theorem, "NOTES", tmp_path)
    return course


def test_new_writes_a_note_once(notes):
    path = theorem.new("demo", "first", "First")
    assert path == notes / "theorems" / "first.tex"
    assert theorem.parse_note(path.read_text()) == ("First", "thm:first")
    with pytest.raises(SystemExit):
        theorem.new("demo", "first", "First")
    with pytest.raises(SystemExit):
        theorem.new("demo", "Bad_Slug", "x")


@pytest.mark.skipif(shutil.which("latexmk") is None, reason="needs a TeX install")
def test_build_keeps_master_number_and_resolves_refs(notes):
    (notes / "theorems").mkdir()
    (notes / "theorems" / "first.tex").write_text(
        "\\begin{theorem}[First]\\label{thm:first}x\\thmsource{\\cite{book}}\\end{theorem}\n"
    )
    (notes / "theorems" / "second.tex").write_text(
        "\\begin{theorem}[Second]\\label{thm:second}See \\cref{thm:first}.\\end{theorem}\n"
    )

    [pdf] = theorem.build("demo", ["second"])

    assert pdf == notes / "theorems" / "second.pdf"
    assert pdf.read_bytes().startswith(b"%PDF")
