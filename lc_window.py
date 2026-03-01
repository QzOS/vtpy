from dataclasses import dataclass, field
from typing import Optional

from lc_term import LC_DIRTY, LC_FORCEPAINT, LC_ATTR_NONE


@dataclass
class LCCell:
    ch: str = ' '
    attr: int = 0


@dataclass
class LCRow:
    line: list[LCCell]
    firstch: int = 0
    lastch: int = 0
    flags: int = LC_DIRTY | LC_FORCEPAINT


@dataclass
class LCWin:
    maxy: int
    maxx: int
    begy: int = 0
    begx: int = 0
    cury: int = 0
    curx: int = 0
    lines: list[LCRow] = field(default_factory=list)


def mark_dirty(ln: Optional[LCRow], start: int, end: int, maxx: int) -> None:
    if ln is None or start >= maxx:
        return
    if end > maxx:
        end = maxx
    if end == 0 or start >= end:
        return

    first = start
    last = end - 1

    if ln.flags & LC_DIRTY:
        if first < ln.firstch:
            ln.firstch = first
        if last > ln.lastch:
            ln.lastch = last
    else:
        ln.firstch = first
        ln.lastch = last
        ln.flags |= LC_DIRTY

    ln.flags |= LC_FORCEPAINT


def lc_new(nlines: int, ncols: int, begin_y: int, begin_x: int) -> Optional[LCWin]:
    if nlines <= 0 or ncols <= 0:
        return None
    if begin_y < 0 or begin_x < 0:
        return None

    lines: list[LCRow] = []
    for _y in range(nlines):
        row_cells = [LCCell(' ', LC_ATTR_NONE) for _x in range(ncols)]
        row = LCRow(line=row_cells, firstch=0, lastch=ncols - 1,
                    flags=LC_DIRTY | LC_FORCEPAINT)
        lines.append(row)

    return LCWin(
        maxy=nlines,
        maxx=ncols,
        begy=begin_y,
        begx=begin_x,
        cury=0,
        curx=0,
        lines=lines
    )


def lc_free(win: Optional[LCWin]) -> int:
    if win is None:
        return -1
    win.lines.clear()
    return 0


def fill_rect(win: Optional[LCWin], y0: int, x0: int, y1: int, x1: int, ch: str) -> None:
    if win is None:
        return
    if y0 >= y1 or y0 >= win.maxy:
        return

    if y1 > win.maxy:
        y1 = win.maxy

    for y in range(y0, y1):
        ln = win.lines[y]
        start = min(max(x0, 0), win.maxx)
        end = min(max(x1, 0), win.maxx)
        if start >= end:
            continue

        for x in range(start, end):
            ln.line[x].ch = ch
            ln.line[x].attr = LC_ATTR_NONE

        mark_dirty(ln, start, end, win.maxx)


def lc_wclear(win: Optional[LCWin]) -> int:
    if win is None:
        return -1
    fill_rect(win, 0, 0, win.maxy, win.maxx, ' ')
    win.cury = 0
    win.curx = 0
    return 0


def lc_wclrtobot(win: Optional[LCWin]) -> int:
    if win is None:
        return -1

    y = win.cury
    x = win.curx
    fill_rect(win, y, x, y + 1, win.maxx, ' ')
    if y + 1 < win.maxy:
        fill_rect(win, y + 1, 0, win.maxy, win.maxx, ' ')
    return 0


def lc_wclrtoeol(win: Optional[LCWin]) -> int:
    if win is None:
        return -1
    fill_rect(win, win.cury, win.curx, win.cury + 1, win.maxx, ' ')
    return 0
