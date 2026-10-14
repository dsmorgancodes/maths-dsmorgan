"""First-pass converter from Obsidian notes to house-style LaTeX.

    uv run tools/import_obsidian.py NOTE.md [NOTE.md ...] [--figures DIR] [--vault DIR]

Prints a LaTeX fragment (one \\section per note) for a hand rewrite. It never
edits the vault. Places that need a human carry a `TODO(review)` comment.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

CALLOUT = re.compile(r"^>\s*\[!([^\]]+)\][+-]?\s*(.*)$")
EMBED = re.compile(r"!\[\[([^\]|]+)(?:\|[^\]]*)?\]\]")
WIKILINK = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|([^\]]+))?\]\]")
HEADING = re.compile(r"^(#{1,6})\s")

# Callout type -> (environment for the statement, environment for what follows).
CALLOUTS = {"prove": ("exercise", "proof"), "problem": ("exercise", "solution")}

MACROS = {r"\mathbb{N}": r"\N", r"\mathbb{Z}": r"\Z", r"\mathbb{Q}": r"\Q",
          r"\mathbb{R}": r"\R", r"\mathbb{C}": r"\C"}  # fmt: skip
UNICODE = {"≠": r"\ensuremath{\neq}", "≤": r"\ensuremath{\leq}",
           "≥": r"\ensuremath{\geq}", "°": r"\ensuremath{^\circ}",
           "−": "-", "×": r"\ensuremath{\times}", "◾️": r"\ensuremath{\square}",
           "◾": r"\ensuremath{\square}", "▲": r"\ensuremath{\triangle}",
           "𝜃": r"\ensuremath{\theta}", "𝑡": "t", "π": r"\ensuremath{\pi}",
           "γ": r"\ensuremath{\gamma}", "\ufe0f": ""}  # fmt: skip

# Pandoc Lua filter: divs -> environments; chained display maths -> align*.
FILTER = r"""
local ENVS = {exercise = true, proof = true, solution = true}

function Div(div)
  local env = div.classes[1]
  if not ENVS[env] then return nil end
  local blocks = {pandoc.RawBlock('latex', '\\begin{' .. env .. '}')}
  for _, b in ipairs(div.content) do table.insert(blocks, b) end
  table.insert(blocks, pandoc.RawBlock('latex', '\\end{' .. env .. '}'))
  return blocks
end

local function align(rows)
  -- Align on the first top-level '=' when every row has one.
  local out, all = {}, true
  for i, r in ipairs(rows) do
    local depth, at = 0, nil
    for j = 1, #r do
      local c = r:sub(j, j)
      if c == '{' then depth = depth + 1 elseif c == '}' then depth = depth - 1
      elseif c == '=' and depth == 0 and not at then at = j end
    end
    if not at then all = false end
    out[i] = {r, at}
  end
  local lines = {}
  for i, p in ipairs(out) do
    local r, at = p[1], p[2]
    if all then r = r:sub(1, at - 1) .. '&' .. r:sub(at) end
    lines[i] = '  ' .. r
  end
  local env = all and 'align*' or 'gather*'
  return '\\begin{' .. env .. '}\n' .. table.concat(lines, ' \\\\\n')
    .. '\n\\end{' .. env .. '}'
end

local function trim(s) return (s:gsub('^%s+', ''):gsub('%s+$', '')) end

function Inlines(inlines)
  local result, i = pandoc.List(), 1
  while i <= #inlines do
    local el = inlines[i]
    if el.t == 'Math' and el.mathtype == 'DisplayMath' then
      local rows, j = {trim(el.text)}, i + 1
      while j <= #inlines do
        local k = j
        while k <= #inlines and (inlines[k].t == 'Space'
            or inlines[k].t == 'SoftBreak' or inlines[k].t == 'LineBreak') do
          k = k + 1
        end
        local nxt = inlines[k]
        if nxt and nxt.t == 'Math' and nxt.mathtype == 'DisplayMath' then
          table.insert(rows, trim(nxt.text)); j = k + 1
        else break end
      end
      if #rows > 1 then
        result:insert(pandoc.RawInline('latex', align(rows)))
      else
        result:insert(pandoc.RawInline('latex', '\\[\n  ' .. rows[1] .. '\n\\]'))
      end
      i = j
    else
      result:insert(el); i = i + 1
    end
  end
  return result
end
"""


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "note"


def find_file(vault: Path, name: str) -> Path | None:
    direct = vault / name
    if direct.is_file():
        return direct
    return next((p for p in vault.rglob(Path(name).name) if p.is_file()), None)


def preprocess(
    text: str, vault: Path, figures: Path | None, prefix: str
) -> tuple[str, list[str]]:
    """Rewrite Obsidian syntax into plain pandoc markdown."""
    notes: list[str] = []
    counter = 0

    def embed(match: re.Match[str]) -> str:
        nonlocal counter
        name = match.group(1).strip()
        source = find_file(vault, name)
        if source is None or source.suffix.lower() not in {".png", ".jpg", ".pdf"}:
            notes.append(f"missing embed {name}")
            return f"`TODO-EMBED {name}`"
        counter += 1
        target = f"{prefix}-{counter}{source.suffix.lower()}"
        if figures is not None:
            figures.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, figures / target)
        notes.append(f"{name} -> figures/{target}")
        return (
            "\n```{=latex}\n% TODO(review): caption or redraw\n"
            "\\begin{center}\n"
            f"  \\includegraphics[width=0.6\\linewidth]{{{Path(target).stem}}}\n"
            "\\end{center}\n```\n"
        )

    text = EMBED.sub(embed, text)
    text = WIKILINK.sub(lambda m: (m.group(2) or m.group(1)).strip(), text)

    out: list[str] = []
    lines = text.splitlines()
    i = 0
    follow: str | None = None
    while i < len(lines):
        match = CALLOUT.match(lines[i])
        if not match:
            out.append(lines[i])
            i += 1
            continue
        kind = match.group(1).strip().lower()
        statement_env, follow_env = CALLOUTS.get(kind, ("exercise", "solution"))
        body = [match.group(2)] if match.group(2) else []
        i += 1
        while i < len(lines) and lines[i].lstrip().startswith(">"):
            body.append(re.sub(r"^\s*>\s?", "", lines[i]))
            i += 1
        if follow:
            out.append(":::")
        out += ["", f"::: {statement_env}", *body, ":::", "", f"::: {follow_env}"]
        follow = follow_env
    if follow:
        out.append(":::")
    if not follow:
        notes.append("no callout: split statement from solution by hand")

    # The note becomes a \section, so its shallowest heading becomes a subsection.
    levels = [len(m.group(1)) for line in out if (m := HEADING.match(line))]
    if levels:
        shift = 2 - min(levels)
        out = [
            ("#" * min(3, max(2, len(m.group(1)) + shift)) + line[len(m.group(1)) :])
            if (m := HEADING.match(line))
            else line
            for line in out
        ]
    return "\n".join(out) + "\n", notes


def postprocess(latex: str) -> str:
    for old, new in {**MACROS, **UNICODE}.items():
        latex = latex.replace(old, new)
    # Pandoc labels every heading; we label by hand.
    latex = re.sub(r"\\label\{[^}]*\}", "", latex)
    latex = re.sub(
        r"^\\(tightlist|def\\labelenum\w+\{.*\})\n", "", latex, flags=re.MULTILINE
    )
    return latex


def pandoc(markdown: str) -> str:
    executable = shutil.which("pandoc")
    if executable is None:
        raise SystemExit("pandoc is not on PATH (brew install pandoc)")
    with tempfile.NamedTemporaryFile("w", suffix=".lua", delete=False) as handle:
        handle.write(FILTER)
        filter_path = handle.name
    try:
        result = subprocess.run(
            [executable, "--from", "markdown+tex_math_dollars-smart",
             "--to", "latex", "--wrap=preserve", "--lua-filter", filter_path],
            input=markdown, capture_output=True, text=True, check=True,
        )  # fmt: skip
    finally:
        Path(filter_path).unlink(missing_ok=True)
    return result.stdout


def convert(
    note: Path, vault: Path, figures: Path | None = None, title: str | None = None
) -> str:
    prefix = slugify(title) if title else slugify(f"{note.parent.name} {note.stem}")
    title = title or note.stem
    markdown, notes = preprocess(
        note.read_text(encoding="utf-8"), vault, figures, prefix
    )
    body = postprocess(pandoc(markdown)).strip()
    header = [f"\\section{{{title}}}", f"% TODO(review): source {note.name}"]
    header += [f"% TODO(review): {n}" for n in notes]
    return "\n".join(header) + "\n\n" + body + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("notes", nargs="+", type=Path)
    parser.add_argument(
        "--vault", type=Path, default=Path.home() / "Obsidian" / "Math Notes"
    )
    parser.add_argument("--figures", type=Path, help="copy embedded images here")
    parser.add_argument("--title", help="section title (one note only)")
    args = parser.parse_args(argv)
    if args.title and len(args.notes) > 1:
        parser.error("--title needs exactly one note")
    for note in args.notes:
        sys.stdout.write(convert(note, args.vault, args.figures, args.title) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
