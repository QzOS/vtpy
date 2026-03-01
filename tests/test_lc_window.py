from lc_window import (
    LCWin,
    lc_new,
    lc_free,
    lc_wclear,
    lc_wmove,
    lc_wput,
    lc_waddstr,
    lc_mvwaddstr,
)
from lc_term import LC_ATTR_NONE, LC_ATTR_BOLD


def test_lc_new():
    win = lc_new(10, 20, 0, 0)
    assert win is not None
    assert win.maxy == 10
    assert win.maxx == 20
    assert win.begy == 0
    assert win.begx == 0


def test_lc_new_invalid():
    assert lc_new(-1, 20, 0, 0) is None
    assert lc_new(10, -1, 0, 0) is None
    assert lc_new(0, 20, 0, 0) is None
    assert lc_new(10, 0, 0, 0) is None


def test_lc_free():
    win = lc_new(10, 20, 0, 0)
    assert lc_free(win) == 0
    assert lc_free(None) == -1


def test_lc_wmove():
    win = lc_new(10, 20, 0, 0)
    assert lc_wmove(win, 5, 10) == 0
    assert win.cury == 5
    assert win.curx == 10


def test_lc_wmove_invalid():
    win = lc_new(10, 20, 0, 0)
    assert lc_wmove(win, -1, 0) == -1
    assert lc_wmove(win, 0, -1) == -1
    assert lc_wmove(win, 10, 0) == -1
    assert lc_wmove(win, 0, 20) == -1
    assert lc_wmove(None, 0, 0) == -1


def test_lc_wput():
    win = lc_new(10, 20, 0, 0)
    assert lc_wput(win, ord('A')) == 0
    assert win.lines[0].line[0].ch == 'A'
    assert win.lines[0].line[0].attr == LC_ATTR_NONE
    assert win.curx == 1


def test_lc_wput_with_attr():
    win = lc_new(10, 20, 0, 0)
    assert lc_wput(win, ord('B'), LC_ATTR_BOLD) == 0
    assert win.lines[0].line[0].ch == 'B'
    assert win.lines[0].line[0].attr == LC_ATTR_BOLD


def test_lc_wput_wrap():
    win = lc_new(2, 3, 0, 0)
    lc_wmove(win, 0, 2)  # Move to last column
    assert lc_wput(win, ord('X')) == 0
    assert win.curx == 0
    assert win.cury == 1


def test_lc_waddstr():
    win = lc_new(10, 20, 0, 0)
    assert lc_waddstr(win, "Hello") == 0
    assert win.lines[0].line[0].ch == 'H'
    assert win.lines[0].line[1].ch == 'e'
    assert win.lines[0].line[2].ch == 'l'
    assert win.lines[0].line[3].ch == 'l'
    assert win.lines[0].line[4].ch == 'o'
    assert win.curx == 5


def test_lc_mvwaddstr():
    win = lc_new(10, 20, 0, 0)
    assert lc_mvwaddstr(win, 2, 3, "Test") == 0
    assert win.lines[2].line[3].ch == 'T'
    assert win.lines[2].line[4].ch == 'e'
    assert win.lines[2].line[5].ch == 's'
    assert win.lines[2].line[6].ch == 't'


def test_lc_wclear():
    win = lc_new(5, 5, 0, 0)
    lc_waddstr(win, "XXXXX")
    lc_wclear(win)
    assert win.cury == 0
    assert win.curx == 0
    assert win.lines[0].line[0].ch == ' '
