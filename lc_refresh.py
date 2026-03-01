import os
from typing import Optional

from lc_term import (
    LC_ATTR_NONE,
    LC_DIRTY,
    LC_FORCEPAINT,
    LC_ATTR_BOLD,
    LC_ATTR_UNDERLINE,
    LC_ATTR_REVERSE,
)
from lc_window import LCCell, LCWin
from lc_screen import lc


def line_hash(cells: list[LCCell]) -> int:
    # FNV-1a over rendered cell content and attr.
    h = 2166136261
    for cell in cells:
        data = cell.ch.encode('utf-8', 'replace')
        for b in data:
            h ^= b
            h = (h * 16777619) & 0xFFFFFFFF

        h ^= cell.attr & 0xFF
        h = (h * 16777619) & 0xFFFFFFFF
    return h


def lc_refresh() -> int:
    return lc_wrefresh(lc.stdscr)


def lc_wrefresh(win: Optional[LCWin]) -> int:
    if win is None:
        return -1
    out_fd = lc.out_fd

    if len(lc.screen) != lc.lines or (lc.lines > 0 and len(lc.screen[0]) != lc.cols):
        lc.screen = [[LCCell(' ', LC_ATTR_NONE) for _x in range(lc.cols)] for _y in range(lc.lines)]
        lc.hashes = [0 for _ in range(lc.lines)]
        lc.term.clear_screen()
        lc.cur_y = 0
        lc.cur_x = 0
        lc.cur_attr = LC_ATTR_NONE

    for y in range(win.maxy):
        abs_y = win.begy + y
        if abs_y >= lc.lines:
            continue

        ln = win.lines[y]
        if not (ln.flags & LC_DIRTY):
            continue

        h = line_hash(ln.line)
        if h == lc.hashes[abs_y] and not (ln.flags & LC_FORCEPAINT):
            ln.firstch = 0
            ln.lastch = 0
            ln.flags = 0
            continue

        lc.hashes[abs_y] = h
        start_x = max(0, ln.firstch)
        end_x = min(win.maxx, ln.lastch + 1)

        for x in range(start_x, end_x):
            abs_x = win.begx + x
            if abs_x >= lc.cols:
                continue

            cell = ln.line[x]
            scr = lc.screen[abs_y][abs_x]
            if scr.ch == cell.ch and scr.attr == cell.attr:
                continue

            if lc.cur_y != abs_y or lc.cur_x != abs_x:
                lc.term.move(abs_y, abs_x)
                lc.cur_y = abs_y
                lc.cur_x = abs_x

            if lc.cur_attr != cell.attr:
                lc.term.set_attr(cell.attr)
                lc.cur_attr = cell.attr

            os.write(out_fd, cell.ch.encode('utf-8', 'replace'))
            lc.screen[abs_y][abs_x] = LCCell(cell.ch, cell.attr)
            lc.cur_x += 1

        ln.firstch = 0
        ln.lastch = 0
        ln.flags = 0

    final_y = win.begy + win.cury
    final_x = win.begx + win.curx
    if final_y < lc.lines and final_x < lc.cols:
        lc.term.move(final_y, final_x)
        lc.cur_y = final_y
        lc.cur_x = final_x

    lc.term.set_attr(LC_ATTR_NONE)
    lc.cur_attr = LC_ATTR_NONE
    return 0
