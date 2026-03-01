from lc_term import LC_ATTR_NONE
from lc_window import (
    fill_rect,
    lc_new,
    lc_waddstr,
    lc_wdraw_box,
    lc_wdraw_hline,
    lc_wdraw_vline,
    lc_wmove,
)


def _row_text(win, y: int) -> str:
    return "".join(cell.ch for cell in win.lines[y].line)


def test_fill_rect_clips_negative_and_right_edge():
    win = lc_new(3, 5, 0, 0)
    fill_rect(win, 0, -2, 2, 10, "x")

    assert _row_text(win, 0) == "xxxxx"
    assert _row_text(win, 1) == "xxxxx"
    assert _row_text(win, 2) == "     "


def test_fill_rect_clips_top_and_bottom():
    win = lc_new(4, 4, 0, 0)
    fill_rect(win, -3, 1, 10, 3, "z")

    assert _row_text(win, 0) == " zz "
    assert _row_text(win, 1) == " zz "
    assert _row_text(win, 2) == " zz "
    assert _row_text(win, 3) == " zz "


def test_waddstr_clips_when_reaching_window_end():
    win = lc_new(2, 3, 0, 0)
    assert lc_wmove(win, 1, 1) == 0
    assert lc_waddstr(win, "abcd") == 0

    assert _row_text(win, 0) == "   "
    assert _row_text(win, 1) == " ab"
    assert win.cury == 1
    assert win.curx == 0


def test_waddstr_returns_error_for_invalid_cursor():
    win = lc_new(2, 2, 0, 0)
    win.cury = 3
    win.curx = 0
    assert lc_waddstr(win, "x") == -1


def test_waddstr_fills_exactly_to_end():
    """Test writing exactly enough chars to fill to the last cell."""
    win = lc_new(2, 3, 0, 0)
    assert lc_wmove(win, 1, 0) == 0
    assert lc_waddstr(win, "abc") == 0

    assert _row_text(win, 0) == "   "
    assert _row_text(win, 1) == "abc"
    # After writing 'c' at (1, 2), cursor wraps to (1, 0) but cury is restored to last valid row
    assert win.cury == 1
    assert win.curx == 0


def test_hline_clips_left_edge():
    win = lc_new(3, 5, 0, 0)
    assert lc_wdraw_hline(win, 1, -2, 5, "-", LC_ATTR_NONE) == 0
    assert _row_text(win, 1) == "---  "


def test_hline_fully_outside_is_noop_success():
    win = lc_new(3, 5, 0, 0)
    assert lc_wdraw_hline(win, 1, 10, 4, "-", LC_ATTR_NONE) == 0
    assert _row_text(win, 1) == "     "


def test_vline_clips_top_edge():
    win = lc_new(5, 4, 0, 0)
    assert lc_wdraw_vline(win, -2, 1, 5, "|", LC_ATTR_NONE) == 0
    assert _row_text(win, 0) == " |  "
    assert _row_text(win, 1) == " |  "
    assert _row_text(win, 2) == " |  "
    assert _row_text(win, 3) == "    "
    assert _row_text(win, 4) == "    "


def test_vline_fully_outside_is_noop_success():
    win = lc_new(4, 4, 0, 0)
    assert lc_wdraw_vline(win, 0, -1, 4, "|", LC_ATTR_NONE) == 0
    for y in range(4):
        assert _row_text(win, y) == "    "


def test_box_clips_right_edge():
    win = lc_new(4, 5, 0, 0)
    assert lc_wdraw_box(win, 1, 2, 3, 4) == 0

    assert _row_text(win, 0) == "     "
    assert _row_text(win, 1) == "  +--"
    assert _row_text(win, 2) == "  |  "
    assert _row_text(win, 3) == "  +--"


def test_box_clips_negative_left_edge():
    win = lc_new(4, 4, 0, 0)
    assert lc_wdraw_box(win, 0, -1, 3, 4) == 0

    assert _row_text(win, 0) == "--+ "
    assert _row_text(win, 1) == "  | "
    assert _row_text(win, 2) == "--+ "
    assert _row_text(win, 3) == "    "


def test_box_fully_outside_is_noop_success():
    win = lc_new(3, 3, 0, 0)
    assert lc_wdraw_box(win, 10, 10, 2, 2) == 0
    for y in range(3):
        assert _row_text(win, y) == "   "


def test_box_degenerate_height_one_clips():
    win = lc_new(3, 4, 0, 0)
    assert lc_wdraw_box(win, 1, -1, 1, 4) == 0
    assert _row_text(win, 1) == "--- "


def test_box_degenerate_width_one_clips():
    win = lc_new(4, 4, 0, 0)
    assert lc_wdraw_box(win, -1, 2, 4, 1) == 0
    assert _row_text(win, 0) == "  | "
    assert _row_text(win, 1) == "  | "
    assert _row_text(win, 2) == "  | "
    assert _row_text(win, 3) == "    "
