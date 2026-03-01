from lc_screen import (
    lc,
    lc_center_x,
    lc_draw_box,
    lc_draw_hline,
    lc_draw_vline,
)
from lc_term import LC_ATTR_NONE
from lc_window import lc_new


def test_center_x_basic():
    assert lc_center_x(10, "abc") == 3
    assert lc_center_x(9, "abc") == 3
    assert lc_center_x(3, "abc") == 0
    assert lc_center_x(2, "abc") == 0


def test_draw_hline():
    old_stdscr = lc.stdscr
    win = lc_new(3, 6, 0, 0)
    lc.stdscr = win
    assert lc_draw_hline(1, 1, 3, "-") == 0
    assert win.lines[1].line[1].ch == "-"
    assert win.lines[1].line[2].ch == "-"
    assert win.lines[1].line[3].ch == "-"
    lc.stdscr = old_stdscr


def test_draw_vline():
    old_stdscr = lc.stdscr
    win = lc_new(5, 5, 0, 0)
    lc.stdscr = win
    assert lc_draw_vline(1, 2, 3, "|") == 0
    assert win.lines[1].line[2].ch == "|"
    assert win.lines[2].line[2].ch == "|"
    assert win.lines[3].line[2].ch == "|"
    lc.stdscr = old_stdscr


def test_draw_box():
    old_stdscr = lc.stdscr
    win = lc_new(6, 8, 0, 0)
    lc.stdscr = win
    assert lc_draw_box(1, 1, 4, 5) == 0

    assert win.lines[1].line[1].ch == "+"
    assert win.lines[1].line[5].ch == "+"
    assert win.lines[4].line[1].ch == "+"
    assert win.lines[4].line[5].ch == "+"

    assert win.lines[1].line[2].ch == "-"
    assert win.lines[1].line[3].ch == "-"
    assert win.lines[1].line[4].ch == "-"

    assert win.lines[2].line[1].ch == "|"
    assert win.lines[3].line[1].ch == "|"
    assert win.lines[2].line[5].ch == "|"
    assert win.lines[3].line[5].ch == "|"
    lc.stdscr = old_stdscr


def test_draw_box_degenerate_height_one():
    old_stdscr = lc.stdscr
    win = lc_new(3, 6, 0, 0)
    lc.stdscr = win
    assert lc_draw_box(1, 1, 1, 4) == 0
    assert win.lines[1].line[1].ch == "-"
    assert win.lines[1].line[2].ch == "-"
    assert win.lines[1].line[3].ch == "-"
    assert win.lines[1].line[4].ch == "-"
    lc.stdscr = old_stdscr


def test_draw_box_degenerate_width_one():
    old_stdscr = lc.stdscr
    win = lc_new(5, 5, 0, 0)
    lc.stdscr = win
    assert lc_draw_box(1, 2, 3, 1) == 0
    assert win.lines[1].line[2].ch == "|"
    assert win.lines[2].line[2].ch == "|"
    assert win.lines[3].line[2].ch == "|"
    lc.stdscr = old_stdscr
