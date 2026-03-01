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


def lc_waddstr(win: Optional[LCWin], s: str) -> int:
    if win is None or s is None:
        return -1

    for ch in s:
        if win.curx >= win.maxx or win.cury >= win.maxy:
            return -1
        ln = win.lines[win.cury]
        ln.line[win.curx].ch = ch
        ln.line[win.curx].attr = LC_ATTR_NONE
        mark_dirty(ln, win.curx, win.curx + 1, win.maxx)
        win.curx += 1
        if win.curx >= win.maxx:
            win.curx = 0
            if win.cury < win.maxy - 1:
                win.cury += 1
    return 0


def lc_wmove(win: Optional[LCWin], y: int, x: int) -> int:
    if win is None:
        return -1
    if y < 0 or y >= win.maxy or x < 0 or x >= win.maxx:
        return -1
    win.cury = y
    win.curx = x
    return 0


def lc_wput(win: Optional[LCWin], ch: int, attr: int = LC_ATTR_NONE) -> int:
    if win is None:
        return -1
    if win.curx >= win.maxx or win.cury >= win.maxy:
        return -1

    try:
        outch = chr(ch)
    except (TypeError, ValueError):
        return -1

    ln = win.lines[win.cury]
    ln.line[win.curx].ch = outch
    ln.line[win.curx].attr = attr
    mark_dirty(ln, win.curx, win.curx + 1, win.maxx)

    win.curx += 1
    if win.curx >= win.maxx:
        win.curx = 0
        if win.cury < win.maxy - 1:
            win.cury += 1
    return 0


def lc_mvwaddstr(win: Optional[LCWin], y: int, x: int, s: str) -> int:
    if lc_wmove(win, y, x) != 0:
        return -1
    return lc_waddstr(win, s)


def lc_wdraw_hline(
    win: Optional[LCWin],
    y: int,
    x: int,
    width: int,
    ch: str = "-",
    attr: int = LC_ATTR_NONE,
) -> int:
    if win is None:
        return -1
    if width <= 0:
        return 0
    if y < 0 or y >= win.maxy:
        return -1
    if x < 0 or x >= win.maxx:
        return -1
    if not ch:
        return -1

    end = min(win.maxx, x + width)
    ln = win.lines[y]
    for cx in range(x, end):
        ln.line[cx].ch = ch[0]
        ln.line[cx].attr = attr
    mark_dirty(ln, x, end, win.maxx)
    return 0


def lc_wdraw_vline(
    win: Optional[LCWin],
    y: int,
    x: int,
    height: int,
    ch: str = "|",
    attr: int = LC_ATTR_NONE,
) -> int:
    if win is None:
        return -1
    if height <= 0:
        return 0
    if x < 0 or x >= win.maxx:
        return -1
    if y < 0 or y >= win.maxy:
        return -1
    if not ch:
        return -1

    end = min(win.maxy, y + height)
    for cy in range(y, end):
        ln = win.lines[cy]
        ln.line[x].ch = ch[0]
        ln.line[x].attr = attr
        mark_dirty(ln, x, x + 1, win.maxx)
    return 0


def lc_wdraw_box(
    win: Optional[LCWin],
    y: int,
    x: int,
    height: int,
    width: int,
    attr: int = LC_ATTR_NONE,
    hch: str = "-",
    vch: str = "|",
    tl: str = "+",
    tr: str = "+",
    bl: str = "+",
    br: str = "+",
) -> int:
    if win is None:
        return -1
    if height <= 0 or width <= 0:
        return 0
    if y < 0 or x < 0:
        return -1
    if y >= win.maxy or x >= win.maxx:
        return -1

    if height == 1:
        return lc_wdraw_hline(win, y, x, width, hch, attr)

    if width == 1:
        return lc_wdraw_vline(win, y, x, height, vch, attr)

    lc_wdraw_hline(win, y, x + 1, max(0, width - 2), hch, attr)
    lc_wdraw_hline(win, y + height - 1, x + 1, max(0, width - 2), hch, attr)
    lc_wdraw_vline(win, y + 1, x, max(0, height - 2), vch, attr)
    lc_wdraw_vline(win, y + 1, x + width - 1, max(0, height - 2), vch, attr)

    if 0 <= y < win.maxy and 0 <= x < win.maxx:
        ln = win.lines[y]
        ln.line[x].ch = tl[0]
        ln.line[x].attr = attr
        mark_dirty(ln, x, x + 1, win.maxx)

    if 0 <= y < win.maxy and 0 <= x + width - 1 < win.maxx:
        ln = win.lines[y]
        ln.line[x + width - 1].ch = tr[0]
        ln.line[x + width - 1].attr = attr
        mark_dirty(ln, x + width - 1, x + width, win.maxx)

    if 0 <= y + height - 1 < win.maxy and 0 <= x < win.maxx:
        ln = win.lines[y + height - 1]
        ln.line[x].ch = bl[0]
        ln.line[x].attr = attr
        mark_dirty(ln, x, x + 1, win.maxx)

    if 0 <= y + height - 1 < win.maxy and 0 <= x + width - 1 < win.maxx:
        ln = win.lines[y + height - 1]
        ln.line[x + width - 1].ch = br[0]
        ln.line[x + width - 1].attr = attr
        mark_dirty(ln, x + width - 1, x + width, win.maxx)

    return 0
