from lc_window import (
    lc_new,
    lc_subwin,
    lc_waddstr,
    lc_wfill,
    lc_wmove,
    LC_DIRTY,
)


def _row_text(win, y: int) -> str:
    return "".join(cell.ch for cell in win.lines[y].line)


def test_subwin_creation_is_relative_to_parent():
    parent = lc_new(6, 8, 2, 3)
    sub = lc_subwin(parent, 2, 3, 1, 2)

    assert sub is not None
    assert sub.parent is parent
    assert sub.root is parent
    assert sub.begy == 3
    assert sub.begx == 5
    assert sub.pary == 1
    assert sub.parx == 2


def test_subwin_rejects_out_of_bounds_creation():
    parent = lc_new(4, 4, 0, 0)
    assert lc_subwin(parent, 2, 2, 3, 0) is None
    assert lc_subwin(parent, 2, 2, 0, 3) is None
    assert lc_subwin(parent, 5, 1, 0, 0) is None
    assert lc_subwin(parent, 1, 5, 0, 0) is None


def test_subwin_shares_backing_store_for_fill():
    parent = lc_new(4, 6, 0, 0)
    sub = lc_subwin(parent, 2, 3, 1, 2)
    assert sub is not None

    assert lc_wfill(sub, 0, 0, 2, 3, "x", 5) == 0

    assert _row_text(parent, 0) == "      "
    assert _row_text(parent, 1) == "  xxx "
    assert _row_text(parent, 2) == "  xxx "
    assert _row_text(parent, 3) == "      "
    assert parent.lines[1].line[2].attr == 5
    assert parent.lines[2].line[4].attr == 5


def test_subwin_shares_backing_store_for_text():
    parent = lc_new(3, 6, 0, 0)
    sub = lc_subwin(parent, 1, 4, 1, 1)
    assert sub is not None

    assert lc_wmove(sub, 0, 0) == 0
    assert lc_waddstr(sub, "abcd") == 0

    assert _row_text(parent, 0) == "      "
    assert _row_text(parent, 1) == " abcd "
    assert _row_text(parent, 2) == "      "


def test_subwin_dirty_propagates_to_parent():
    parent = lc_new(4, 6, 0, 0)
    sub = lc_subwin(parent, 2, 2, 1, 3)
    assert sub is not None

    for ln in parent.lines:
        ln.flags = 0
        ln.firstch = 0
        ln.lastch = 0
    for ln in sub.lines:
        ln.flags = 0
        ln.firstch = 0
        ln.lastch = 0

    assert lc_wfill(sub, 0, 0, 1, 2, ".", 1) == 0

    assert sub.lines[0].flags & LC_DIRTY
    assert parent.lines[1].flags & LC_DIRTY
    assert parent.lines[1].firstch == 3
    assert parent.lines[1].lastch == 4


def test_nested_subwin_root_tracks_top_window():
    parent = lc_new(6, 8, 0, 0)
    child = lc_subwin(parent, 4, 5, 1, 2)
    grand = lc_subwin(child, 2, 2, 1, 1)

    assert child is not None
    assert grand is not None
    assert child.root is parent
    assert grand.root is parent
    assert grand.parent is child
    assert grand.begy == 2
    assert grand.begx == 3
