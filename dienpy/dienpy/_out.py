"""Tables and section headers for every CLI in the ecosystem.

Terminal output goes through rich: cells are plain text (a release name's
`[PublicHD]` is not markup), styling drops away when piped, and piped output
is never wrapped or squeezed to a guessed width. `plain` renders the same
layout as text for something other than the terminal (fzf input, a commit
message). Markdown output is the compact form: `| a | b |`, `| --- |`, no
padding.
"""

from __future__ import annotations

from collections.abc import Collection, Iterable, Sequence
from functools import cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rich.console import Console, RenderableType

_PIPED_WIDTH = 1 << 16
_MD_ALIGN = {"<": ":--", ">": "--:", "^": ":-:"}


@cache
def _console(plain: bool) -> Console:
    from rich.console import Console

    tty = not plain and Console().is_terminal
    return Console(
        markup=False,
        highlight=False,
        emoji=False,
        width=None if tty else _PIPED_WIDTH,
        color_system="auto" if tty else None,
    )


def _render(renderable: RenderableType, indent: int = 0, plain: bool = False) -> str:
    console, pad = _console(plain), " " * indent
    with console.capture() as cap:
        console.print(renderable, width=console.width - indent)
    return "\n".join(pad + line.rstrip() for line in cap.get().splitlines())


def table(
    rows: Iterable[Sequence[object]],
    head: Sequence[str] = (),
    *,
    align: str = "",
    dim: Collection[int] = (),
    clip: bool = False,
    indent: int = 0,
    plain: bool = False,
) -> str:
    """Rows as aligned columns two spaces apart, empty when there are none.

    `align` holds one `<`/`>` per column (left by default), `dim` the indices
    of secondary columns; a column empty in every row takes no space. On a
    terminal too narrow for the row, the last column wraps inside itself, or
    with `clip` is cut with an ellipsis; the others keep their full width."""
    from rich.cells import cell_len
    from rich.table import Table

    lines = [[*map(str, r)] for r in rows]
    if not lines:
        return ""
    n = max(len(head), *map(len, lines))
    grid = [[*r, *[""] * (n - len(r))] for r in ([head] if head else []) + lines]
    widths = [max(map(cell_len, col)) for col in zip(*grid, strict=True)]
    keep = [i for i in range(n) if widths[i]]
    room = _console(plain).width - indent - sum(widths[i] + 2 for i in keep[:-1])
    t = Table(
        box=None,
        show_header=bool(head),
        header_style="bold",
        pad_edge=False,
        padding=(0, 1),
    )
    for i in keep:
        last = i == keep[-1]
        t.add_column(
            grid[0][i] if head else "",
            justify="right" if align[i : i + 1] == ">" else "left",
            style="dim" if i in dim else "",
            no_wrap=not last or clip,
            overflow="fold" if last and not clip else "ellipsis",
            max_width=room if last and room > 0 else None,
        )
    for r in grid[1:] if head else grid:
        t.add_row(*(r[i] for i in keep))
    return _render(t, indent, plain)


def section(title: str, note: str = "") -> str:
    """`── title  note`: the header over one machine's, entry's or group's lines."""
    from rich.text import Text

    return _render(
        Text.assemble("── ", (title, "bold"), (f"  {note}" if note else "", "dim"))
    )


def md_row(cells: Iterable[object]) -> str:
    """`| a | b |`, an empty cell `| |`; a `|` inside a cell is escaped."""
    escaped = (str(c).replace("|", "\\|") for c in cells)
    return "|" + "|".join(f" {c} " if c else " " for c in escaped) + "|"


def md_table(
    head: Sequence[str], rows: Iterable[Sequence[object]], *, align: str = ""
) -> list[str]:
    """Header, delimiter and one line per row; `align` as in `table`, `^` centres."""
    delim = [_MD_ALIGN.get(align[i : i + 1], "---") for i in range(len(head))]
    return [md_row(head), md_row(delim), *map(md_row, rows)]
