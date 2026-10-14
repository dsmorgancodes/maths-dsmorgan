from tools import publish

AUX = r"""
\newlabel{eq:poly}{{\rEfLiNK{x1-2001r1}{\csname :autoref\endcsname{equation}2.1}}{\rEfLiNK{x1-2001r1}{\csname :autoref\endcsname{equation}1}}{}{equation.1}{}}
\newlabel{eq:poly@cref}{{[equation][1][2]2.1}{[1][1][]1}{}{}{}}
\newlabel{thm:sqrt2}{{\rEfLiNK{x1-7002r1}{\csname :autoref\endcsname{theorem}6.1}}{\rEfLiNK{x1-7002r1}{\csname :autoref\endcsname{theorem}1}}{}{theorem.1}{}}
"""

PAGE = """<html><head><script>MathJax</script><link href='master.css'/></head><body>
<div class='maketitle'><h1 class='titleHead'>Foundations</h1></div>
<!-- l. 3 --><p class='noindent'>______________________________
</p><p class='noindent' id='chapter-1-statements'><span class='rm-lmcsc-10x-x-120'>Chapter 1: Statements</span></p>
<div class='tcolorbox tcolorbox' id='tcolobox-2'><div class='tcolorbox-content'><a id='x1-1'></a>
<div class='newtheorem'><p class='noindent'><span class='head'><span class='rm-lmcsc-10x-x-109'>Theorem </span>6.1 <span class='rm-lmri-10x-x-109'>(Name)</span>.</span>
<span class='rm-lmri-10x-x-109'>Statement</span> <span class='rm-lmbx-10x-x-109'>bold</span> <span class='rm-lmr-10x-x-109'>plain</span></p></div>
<p class='noindent'></p></div></div>
<div class='tcolorbox'><div class='tcolorbox-content'><div class='newtheorem'><p><span class='head'>Definition 1.2.</span> A thing.</p></div></div></div>
<div class='newtheorem'><p><span class='head'><span class='rm-lmri-10x-x-109'>Remark </span>1.3.</span> Note.</p></div>
<div class='proof'><p class='indent'>Since <span class='mathjax-inline'>\\(\\abs*{x}\\)</span>, see <a href='#x1-2001r1'>2.1</a>.          \u25a1
</p></div>
<div class='mathjax-env mathjax-equation'>\\begin{equation}\\label {eq:poly} x^2 = x + 1 \\end{equation}</div>
<figure class='figure'><img alt='PIC' height='300' src='figures/a.png' width='300' /><figcaption class='caption'>Figure 1: A square.</figcaption></figure>
<a href='https://example.com'>out</a>
</body></html>"""


def cleaned(**kwargs):
    return publish.clean(
        PAGE,
        refs=publish.labels(AUX),
        asset_base="/notes/foundations/files",
        **kwargs,
    )


def test_labels_read_anchor_and_number():
    refs = publish.labels(AUX)
    assert refs["eq:poly"] == ("x1-2001r1", "2.1")
    assert refs["thm:sqrt2"] == ("x1-7002r1", "6.1")
    assert "eq:poly@cref" not in refs


def test_clean_drops_page_furniture():
    html = cleaned()
    assert "<script" not in html and "<link" not in html
    assert "maketitle" not in html and "<!--" not in html
    assert "____" not in html
    assert '<h2 class="unit" id="chapter-1-statements">' in html


def test_clean_maps_fonts_and_statements():
    html = cleaned()
    assert "rm-lm" not in html
    assert '<span class="sc">Theorem </span>' in html
    assert "<em>(Name)</em>" in html
    assert "<strong>bold</strong>" in html
    assert " plain" in html and "<span>plain" not in html
    assert '<div class="theorem">' in html
    assert '<div class="definition">' in html
    assert '<div class="remark">' in html
    assert "tcolorbox" not in html and "newtheorem" not in html


def test_clean_math_links_and_figures():
    html = cleaned()
    assert "\\absStar{x}" in html
    assert "\u25a1" not in html
    assert (
        '<div class="mathjax-block" id="x1-2001r1">'
        "\\begin{equation}\\tag{2.1} x^2 = x + 1 \\end{equation}</div>"
    ) in html
    assert 'href="#x1-2001r1"' in html
    assert 'href="https://example.com"' in html
    assert (
        '<img alt="Figure 1: A square." src="/notes/foundations/files/figures/a.png"/>'
        in html
    )


def test_clean_points_fragment_links_at_the_course():
    html = cleaned(link_base="/notes/foundations")
    assert 'href="/notes/foundations#x1-2001r1"' in html


def test_marked_notes_are_cut_out_and_linked(tmp_path):
    (tmp_path / "theorems").mkdir()
    note = tmp_path / "theorems" / "sqrt2.tex"
    note.write_text(
        "\\begin{theorem}[$\\sqrt2$ is irrational]\\label{thm:sqrt2}\nX\n\\end{theorem}\n"
    )
    work = tmp_path / "work"
    (work / "theorems").mkdir(parents=True)
    (work / "theorems" / "sqrt2.tex").write_text(note.read_text())
    publish.mark_notes(work)
    marked = (work / "theorems" / "sqrt2.tex").read_text()
    assert marked.startswith("\\ifdefined\\HCode\\HCode{<!--note:sqrt2-->}\\fi")
    assert marked.rstrip().endswith("\\HCode{<!--/note:sqrt2-->}\\fi")

    course = (
        "<p>Before</p><p><!-- note:sqrt2 --></p><div class='newtheorem'>"
        "<p><span class='head'>Theorem 6.1.</span> See <a href='#x9'>1.1</a></p></div>"
        "<p><!-- /note:sqrt2 --></p><p>After</p>"
    )
    refs = publish.labels(AUX)
    [(slug, name, number, anchor, html)] = publish.theorem_notes(
        course, tmp_path, refs, "/notes/foundations"
    )
    assert (slug, name, number, anchor) == (
        "sqrt2",
        "\\(\\sqrt2\\) is irrational",
        "6.1",
        "x1-7002r1",
    )
    assert "Before" not in html and "After" not in html
    assert 'href="/notes/foundations#x9"' in html

    linked = publish.link_notes(course, "/notes/foundations")
    assert "note:" not in linked
    assert (
        '<a class="theorem-link" href="/notes/foundations/theorems/sqrt2">'
        "Theorem page</a>"
    ) in linked


def test_display_name():
    assert publish.display_name("Cauchy--Goursat") == "Cauchy\u2013Goursat"
    assert publish.display_name("$ML$-inequality") == "\\(ML\\)-inequality"


def test_targets(tmp_path, monkeypatch):
    content = tmp_path / "content"
    for folder, slug, published in [
        ("notes", "done", "true"),
        ("notes", "draft", "false"),
        ("graduate-proofs", "proof", "true"),
    ]:
        (content / folder / slug).mkdir(parents=True)
        (content / folder / slug / "entry.toml").write_text(
            f'title = "T"\npublished = {published}\n'
        )
    monkeypatch.setattr(publish, "CONTENT", content)
    assert publish.targets([], drafts=False) == [
        ("graduate-proofs", "proof"),
        ("notes", "done"),
    ]
    assert ("notes", "draft") in publish.targets([], drafts=True)
    assert publish.targets(["notes/draft"], drafts=False) == [("notes", "draft")]
