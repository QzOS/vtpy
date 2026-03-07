from lc_screen import (
    lc,
    lc_center_x,
    lc_draw_box,
    lc_draw_hline,
    lc_draw_vline,
    lc_move,
    lc_touchline,
    lc_touchwin,
    lc_insdelln,
    lc_scrl,
    lc_addstr_attr,
)
from lc_term import LC_ATTR_NONE, LC_ATTR_BOLD
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


def test_addstr_attr_writes_with_attribute():
    old_stdscr = lc.stdscr
    win = lc_new(2, 5, 0, 0)
    lc.stdscr = win
    assert lc_addstr_attr("ok", LC_ATTR_BOLD) == 0
    assert win.lines[0].line[0].ch == "o"
    assert win.lines[0].line[1].ch == "k"
    assert win.lines[0].line[0].attr == LC_ATTR_BOLD
    assert win.lines[0].line[1].attr == LC_ATTR_BOLD
    lc.stdscr = old_stdscr


def test_touchline_marks_requested_stdscr_rows_dirty():
    old_stdscr = lc.stdscr
    win = lc_new(4, 6, 0, 0)
    lc.stdscr = win
    for ln in win.lines:
        ln.flags = 0

    assert lc_touchline(1, 2) == 0

    assert win.lines[0].flags == 0
    assert win.lines[1].flags != 0
    assert win.lines[2].flags != 0
    lc.stdscr = old_stdscr


def test_touchwin_marks_all_stdscr_rows_dirty():
    old_stdscr = lc.stdscr
    win = lc_new(2, 3, 0, 0)
    lc.stdscr = win
    for ln in win.lines:
        ln.flags = 0

    assert lc_touchwin() == 0
    assert all(ln.flags != 0 for ln in win.lines)
    lc.stdscr = old_stdscr


def test_touch_wrappers_require_stdscr():
    old_stdscr = lc.stdscr
    lc.stdscr = None
    try:
        assert lc_touchline(0, 1) == -1
        assert lc_touchwin() == -1
        assert lc_insdelln(1) == -1
        assert lc_scrl(1) == -1
    finally:
        lc.stdscr = old_stdscr


def test_insdelln_and_scrl_forward_to_stdscr_window_ops():
    old_stdscr = lc.stdscr
    win = lc_new(4, 3, 0, 0)
    lc.stdscr = win
    try:
        for y in range(win.maxy):
            for x in range(win.maxx):
                win.lines[y].line[x].ch = str(y)

        assert lc_move(1, 0) == 0
        assert lc_insdelln(1) == 0
        assert ''.join(c.ch for c in win.lines[1].line) == '   '
        assert ''.join(c.ch for c in win.lines[2].line) == '111'

        assert lc_scrl(1) == 0
        assert ''.join(c.ch for c in win.lines[0].line) == '   '
        assert ''.join(c.ch for c in win.lines[1].line) == '111'
    finally:
        lc.stdscr = old_stdscr
