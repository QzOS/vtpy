from lc_window import (
    LCWin,
    lc_new,
    lc_free,
    lc_wclear,
    lc_wmove,
    lc_wput,
    lc_waddstr,
    lc_waddstr_attr,
    lc_mvwaddstr,
    lc_subwin,
    fill_rect,
    lc_wdraw_hline,
    lc_wdraw_vline,
    lc_wdraw_box,
    lc_wtouchline,
    lc_wtouchwin,
    lc_winsdelln,
    lc_wscrl,
    lc_invalidate_children,
)
from lc_term import LC_ATTR_NONE, LC_ATTR_BOLD, LC_DIRTY


def test_lc_new():
    win = lc_new(10, 20, 0, 0)
    assert win is not None
    assert win.maxy == 10
    assert win.maxx == 20
    assert win.begy == 0
    assert win.begx == 0
    assert win.root is win


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


def test_live_top_level_window_has_self_root():
    win = lc_new(4, 5, 0, 0)
    assert win is not None
    assert win.parent is None
    assert win.alive is True
    assert win.root is win


def test_live_subwindow_inherits_top_root():
    root = lc_new(6, 8, 0, 0)
    child = lc_subwin(root, 4, 5, 1, 1)
    grand = lc_subwin(child, 2, 2, 1, 1)

    assert root is not None
    assert child is not None
    assert grand is not None

    assert root.root is root
    assert child.root is root
    assert grand.root is root


def test_dead_window_clears_root():
    win = lc_new(3, 3, 0, 0)
    assert win is not None
    assert win.root is win
    assert lc_free(win) == 0
    assert win.alive is False
    assert win.root is None


# ---------------------------------------------------------------------------
# Write operation family: clipped drawing/fill (fill_rect, lc_wdraw_hline,
# lc_wdraw_vline, lc_wdraw_box) — verify cell content, dirty ranges, clipping
# ---------------------------------------------------------------------------

def _row_text(win, y: int) -> str:
    return "".join(cell.ch for cell in win.lines[y].line)


def _clear_dirty(win) -> None:
    for ln in win.lines:
        ln.flags = 0
        ln.firstch = 0
        ln.lastch = 0


def test_fill_rect_writes_expected_cells_and_dirty_range():
    win = lc_new(4, 6, 0, 0)
    assert win is not None
    _clear_dirty(win)

    fill_rect(win, 1, 1, 3, 4, "x", LC_ATTR_NONE)

    assert _row_text(win, 0) == "      "
    assert _row_text(win, 1) == " xxx  "
    assert _row_text(win, 2) == " xxx  "
    assert _row_text(win, 3) == "      "

    assert win.lines[1].flags & LC_DIRTY
    assert win.lines[1].firstch == 1
    assert win.lines[1].lastch == 3
    assert win.lines[2].flags & LC_DIRTY
    assert win.lines[0].flags == 0
    assert win.lines[3].flags == 0


def test_fill_rect_clips_to_window_bounds():
    win = lc_new(3, 4, 0, 0)
    assert win is not None

    # Request extends beyond window in all directions.
    fill_rect(win, -1, -1, 10, 10, "Z", LC_ATTR_NONE)

    for y in range(3):
        assert _row_text(win, y) == "ZZZZ"


def test_lc_wdraw_hline_writes_expected_cells_and_dirty_range():
    win = lc_new(3, 8, 0, 0)
    assert win is not None
    _clear_dirty(win)

    assert lc_wdraw_hline(win, 1, 2, 4, "-", LC_ATTR_NONE) == 0

    assert _row_text(win, 0) == "        "
    assert _row_text(win, 1) == "  ----  "
    assert _row_text(win, 2) == "        "

    assert win.lines[1].flags & LC_DIRTY
    assert win.lines[1].firstch == 2
    assert win.lines[1].lastch == 5
    assert win.lines[0].flags == 0
    assert win.lines[2].flags == 0


def test_lc_wdraw_hline_clips_to_window_bounds():
    win = lc_new(2, 4, 0, 0)
    assert win is not None

    # Start within bounds, extends beyond right edge.
    assert lc_wdraw_hline(win, 0, 2, 10, "=", LC_ATTR_NONE) == 0
    assert _row_text(win, 0) == "  =="

    # y out of bounds returns 0 (noop).
    assert lc_wdraw_hline(win, 5, 0, 4, "-", LC_ATTR_NONE) == 0


def test_lc_wdraw_vline_writes_expected_cells_and_dirty_range():
    win = lc_new(5, 4, 0, 0)
    assert win is not None
    _clear_dirty(win)

    assert lc_wdraw_vline(win, 1, 2, 3, "|", LC_ATTR_NONE) == 0

    assert win.lines[0].line[2].ch == " "
    assert win.lines[1].line[2].ch == "|"
    assert win.lines[2].line[2].ch == "|"
    assert win.lines[3].line[2].ch == "|"
    assert win.lines[4].line[2].ch == " "

    for y in (1, 2, 3):
        assert win.lines[y].flags & LC_DIRTY
        assert win.lines[y].firstch == 2
        assert win.lines[y].lastch == 2
    assert win.lines[0].flags == 0
    assert win.lines[4].flags == 0


def test_lc_wdraw_vline_clips_to_window_bounds():
    win = lc_new(3, 4, 0, 0)
    assert win is not None

    # Start within bounds, extends beyond bottom.
    assert lc_wdraw_vline(win, 2, 1, 10, "|", LC_ATTR_NONE) == 0
    assert win.lines[2].line[1].ch == "|"

    # x out of bounds returns 0 (noop).
    assert lc_wdraw_vline(win, 0, 10, 3, "|", LC_ATTR_NONE) == 0


def test_lc_wdraw_box_writes_expected_corners_and_edges():
    win = lc_new(4, 6, 0, 0)
    assert win is not None
    _clear_dirty(win)

    assert lc_wdraw_box(win, 0, 0, 4, 6, LC_ATTR_NONE, "-", "|", "+", "+", "+", "+") == 0

    # Corners
    assert win.lines[0].line[0].ch == "+"
    assert win.lines[0].line[5].ch == "+"
    assert win.lines[3].line[0].ch == "+"
    assert win.lines[3].line[5].ch == "+"

    # Top and bottom edges
    for x in range(1, 5):
        assert win.lines[0].line[x].ch == "-"
        assert win.lines[3].line[x].ch == "-"

    # Left and right edges
    for y in range(1, 3):
        assert win.lines[y].line[0].ch == "|"
        assert win.lines[y].line[5].ch == "|"

    # Interior is untouched
    for y in range(1, 3):
        for x in range(1, 5):
            assert win.lines[y].line[x].ch == " "

    # All border rows are dirty
    for y in (0, 3):
        assert win.lines[y].flags & LC_DIRTY
    for y in (1, 2):
        assert win.lines[y].flags & LC_DIRTY


def test_lc_wdraw_box_clips_to_window_bounds():
    win = lc_new(3, 4, 0, 0)
    assert win is not None

    # Box extends beyond all edges — should still succeed without error.
    assert lc_wdraw_box(win, -1, -1, 10, 10, LC_ATTR_NONE) == 0


def test_lc_waddstr_dirty_range_matches_chars_written():
    win = lc_new(2, 6, 0, 0)
    assert win is not None
    _clear_dirty(win)

    assert lc_wmove(win, 0, 1) == 0
    assert lc_waddstr(win, "abc") == 0

    assert win.lines[0].flags & LC_DIRTY
    assert win.lines[0].firstch == 1
    assert win.lines[0].lastch == 3
    assert win.lines[1].flags == 0


# ---------------------------------------------------------------------------
# Root/self-root invariants across create/subwin/free/resize replacement
# ---------------------------------------------------------------------------

def test_root_invariant_after_resize_replacement():
    """After resize replacement, old subwindows have alive=False and root=None;
    new stdscr has root is self."""
    root = lc_new(4, 5, 0, 0)
    assert root is not None
    assert root.root is root

    child = lc_subwin(root, 2, 2, 1, 1)
    assert child is not None
    assert child.root is root

    # Simulate resize: invalidate children, free old root, create new root.
    lc_invalidate_children(root)
    lc_free(root)

    new_root = lc_new(6, 7, 0, 0)
    assert new_root is not None

    assert root.alive is False
    assert root.root is None
    assert child.alive is False
    assert child.root is None

    assert new_root.alive is True
    assert new_root.root is new_root


def test_lc_waddstr_attr_sets_attribute_on_written_cells():
    win = lc_new(2, 4, 0, 0)
    assert win is not None

    assert lc_waddstr_attr(win, "ab", LC_ATTR_BOLD) == 0
    assert win.lines[0].line[0].ch == 'a'
    assert win.lines[0].line[1].ch == 'b'
    assert win.lines[0].line[0].attr == LC_ATTR_BOLD
    assert win.lines[0].line[1].attr == LC_ATTR_BOLD


def test_lc_waddstr_attr_saturates_at_last_cell():
    win = lc_new(1, 3, 0, 0)
    assert win is not None

    assert lc_wmove(win, 0, 1) == 0
    assert lc_waddstr_attr(win, "XYZ", LC_ATTR_BOLD) == 0

    assert win.lines[0].line[1].ch == 'X'
    assert win.lines[0].line[2].ch == 'Y'
    assert win.lines[0].line[1].attr == LC_ATTR_BOLD
    assert win.lines[0].line[2].attr == LC_ATTR_BOLD
    assert win.curx == 2
    assert win.cury == 0


def test_lc_waddstr_attr_at_last_cell_writes_single_char():
    """When the cursor is already at the last writable cell, only the first
    character of the string should be written with the attribute."""
    win = lc_new(1, 3, 0, 0)
    assert win is not None

    # Move cursor to the last cell (0, 2)
    assert lc_wmove(win, 0, 2) == 0
    assert lc_waddstr_attr(win, "ABC", LC_ATTR_BOLD) == 0

    # Only 'A' should be written at (0, 2)
    assert win.lines[0].line[2].ch == 'A'
    assert win.lines[0].line[2].attr == LC_ATTR_BOLD
    # Cursor should remain at the last cell
    assert win.curx == 2
    assert win.cury == 0


def test_lc_waddstr_attr_spans_multiple_rows():
    """Writing a string that is longer than a single row should correctly
    apply the attribute across row boundaries."""
    win = lc_new(3, 4, 0, 0)
    assert win is not None

    # Write a string longer than one row (4 chars per row, 3 rows)
    # This should span row 0 and row 1
    assert lc_waddstr_attr(win, "ABCDEFGH", LC_ATTR_BOLD) == 0

    # Row 0: A B C D
    assert win.lines[0].line[0].ch == 'A'
    assert win.lines[0].line[1].ch == 'B'
    assert win.lines[0].line[2].ch == 'C'
    assert win.lines[0].line[3].ch == 'D'
    assert win.lines[0].line[0].attr == LC_ATTR_BOLD
    assert win.lines[0].line[3].attr == LC_ATTR_BOLD

    # Row 1: E F G H
    assert win.lines[1].line[0].ch == 'E'
    assert win.lines[1].line[1].ch == 'F'
    assert win.lines[1].line[2].ch == 'G'
    assert win.lines[1].line[3].ch == 'H'
    assert win.lines[1].line[0].attr == LC_ATTR_BOLD
    assert win.lines[1].line[3].attr == LC_ATTR_BOLD

    # Cursor should advance to row 2, column 0
    assert win.cury == 2
    assert win.curx == 0


def _clear_dirty(win):
    for ln in win.lines:
        ln.flags = 0
        ln.firstch = 0
        ln.lastch = 0


def _row_text(win, y):
    return ''.join(c.ch for c in win.lines[y].line)


def test_lc_wtouchline_marks_clipped_rows_dirty_without_mutation():
    win = lc_new(4, 6, 0, 0)
    assert win is not None
    _clear_dirty(win)

    before = [_row_text(win, y) for y in range(win.maxy)]
    assert lc_wtouchline(win, 1, 2) == 0

    assert win.lines[0].flags == 0
    for y in (1, 2):
        assert win.lines[y].flags & LC_DIRTY
        assert win.lines[y].firstch == 0
        assert win.lines[y].lastch == win.maxx - 1

    after = [_row_text(win, y) for y in range(win.maxy)]
    assert after == before


def test_lc_wtouchline_clips_and_accepts_noop_lengths():
    win = lc_new(3, 5, 0, 0)
    assert win is not None
    _clear_dirty(win)

    assert lc_wtouchline(win, -1, 2) == 0
    assert win.lines[0].flags & LC_DIRTY
    assert win.lines[1].flags == 0

    _clear_dirty(win)
    assert lc_wtouchline(win, 1, 0) == 0
    assert all(ln.flags == 0 for ln in win.lines)


def test_lc_wtouchwin_marks_all_rows_dirty():
    win = lc_new(3, 4, 0, 0)
    assert win is not None
    _clear_dirty(win)

    assert lc_wtouchwin(win) == 0
    for ln in win.lines:
        assert ln.flags & LC_DIRTY
        assert ln.firstch == 0
        assert ln.lastch == win.maxx - 1


def test_lc_wtouchline_propagates_to_parent_chain():
    root = lc_new(5, 7, 0, 0)
    assert root is not None
    child = lc_subwin(root, 3, 4, 1, 2)
    assert child is not None
    _clear_dirty(root)
    _clear_dirty(child)

    assert lc_wtouchline(child, 1, 1) == 0

    assert child.lines[1].flags & LC_DIRTY
    assert child.lines[1].firstch == 0
    assert child.lines[1].lastch == child.maxx - 1

    root_row = child.pary + 1
    assert root.lines[root_row].flags & LC_DIRTY
    assert root.lines[root_row].firstch == child.parx
    assert root.lines[root_row].lastch == child.parx + child.maxx - 1


def test_lc_wtouch_apis_reject_invalid_windows():
    assert lc_wtouchline(None, 0, 1) == -1
    assert lc_wtouchwin(None) == -1



def test_lc_winsdelln_inserts_blank_lines_from_cursor_row():
    win = lc_new(4, 3, 0, 0)
    assert win is not None

    for y in range(win.maxy):
        for x in range(win.maxx):
            win.lines[y].line[x].ch = str(y)

    assert lc_wmove(win, 1, 0) == 0
    assert lc_winsdelln(win, 1) == 0

    assert _row_text(win, 0) == "000"
    assert _row_text(win, 1) == "   "
    assert _row_text(win, 2) == "111"
    assert _row_text(win, 3) == "222"


def test_lc_winsdelln_deletes_lines_from_cursor_row():
    win = lc_new(4, 3, 0, 0)
    assert win is not None

    for y in range(win.maxy):
        for x in range(win.maxx):
            win.lines[y].line[x].ch = str(y)

    assert lc_wmove(win, 1, 0) == 0
    assert lc_winsdelln(win, -2) == 0

    assert _row_text(win, 0) == "000"
    assert _row_text(win, 1) == "333"
    assert _row_text(win, 2) == "   "
    assert _row_text(win, 3) == "   "


def test_lc_wscrl_positive_moves_content_up_negative_moves_content_down():
    win = lc_new(4, 3, 0, 0)
    assert win is not None

    for y in range(win.maxy):
        for x in range(win.maxx):
            win.lines[y].line[x].ch = str(y)

    assert lc_wscrl(win, 1) == 0
    assert _row_text(win, 0) == "111"
    assert _row_text(win, 1) == "222"
    assert _row_text(win, 2) == "333"
    assert _row_text(win, 3) == "   "

    assert lc_wscrl(win, -1) == 0
    assert _row_text(win, 0) == "   "
    assert _row_text(win, 1) == "111"
    assert _row_text(win, 2) == "222"
    assert _row_text(win, 3) == "333"


def test_lc_winsdelln_large_magnitude_blanks_affected_region():
    win = lc_new(4, 3, 0, 0)
    assert win is not None

    for y in range(win.maxy):
        for x in range(win.maxx):
            win.lines[y].line[x].ch = str(y)

    assert lc_wmove(win, 2, 0) == 0
    assert lc_winsdelln(win, 9) == 0

    assert _row_text(win, 0) == "000"
    assert _row_text(win, 1) == "111"
    assert _row_text(win, 2) == "   "
    assert _row_text(win, 3) == "   "


def test_lc_winsdelln_preserves_subwindow_backing_aliasing():
    root = lc_new(5, 4, 0, 0)
    assert root is not None
    sub = lc_subwin(root, 3, 4, 1, 0)
    assert sub is not None

    root_row_ids = [id(ln) for ln in root.lines]
    sub_row_ids = [id(ln) for ln in sub.lines]

    assert lc_wmove(sub, 1, 0) == 0
    assert lc_winsdelln(sub, -1) == 0

    assert [id(ln) for ln in root.lines] == root_row_ids
    assert [id(ln) for ln in sub.lines] == sub_row_ids


def test_lc_winsdelln_subwindow_only_affects_subwindow_region_in_root():
    root = lc_new(5, 6, 0, 0)
    assert root is not None
    sub = lc_subwin(root, 3, 2, 1, 2)
    assert sub is not None

    for y in range(root.maxy):
        for x in range(root.maxx):
            root.lines[y].line[x].ch = chr(ord('A') + y)

    assert lc_wmove(sub, 1, 0) == 0
    assert lc_winsdelln(sub, -1) == 0

    assert _row_text(root, 0) == "AAAAAA"
    assert _row_text(root, 1) == "BBBBBB"
    assert _row_text(root, 2) == "CCDDCC"
    assert _row_text(root, 3) == "DD  DD"
    assert _row_text(root, 4) == "EEEEEE"


def test_lc_winsdelln_and_wscrl_reject_invalid_windows():
    assert lc_winsdelln(None, 1) == -1
    assert lc_wscrl(None, 1) == -1
