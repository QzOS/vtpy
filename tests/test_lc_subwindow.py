from lc_window import (
    lc_invalidate_children,
    lc_new,
    lc_free,
    lc_panel_content_rect,
    lc_panel_subwin,
    lc_subwin,
    lc_waddstr,
    lc_wdraw_box,
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
    assert sub.alive is True
    assert sub in parent.children


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



def test_free_child_detaches_from_parent():
    parent = lc_new(4, 4, 0, 0)
    child = lc_subwin(parent, 2, 2, 1, 1)
    assert child is not None
    assert child in parent.children

    assert lc_free(child) == 0
    assert child.alive is False
    assert child.lines == []
    assert child not in parent.children


def test_free_parent_recursively_kills_children():
    parent = lc_new(6, 6, 0, 0)
    child = lc_subwin(parent, 4, 4, 1, 1)
    grand = lc_subwin(child, 2, 2, 1, 1)

    assert child is not None
    assert grand is not None

    assert lc_free(parent) == 0

    assert parent.alive is False
    assert child.alive is False
    assert grand.alive is False
    assert parent.lines == []
    assert child.lines == []
    assert grand.lines == []


def test_operations_on_dead_window_fail():
    win = lc_new(3, 3, 0, 0)
    assert lc_free(win) == 0

    assert lc_wmove(win, 0, 0) == -1
    assert lc_waddstr(win, "x") == -1
    assert lc_wfill(win, 0, 0, 1, 1, ".", 1) == -1
    assert lc_wdraw_box(win, 0, 0, 2, 2) == -1


def test_cannot_create_subwindow_from_dead_parent():
    parent = lc_new(4, 4, 0, 0)
    assert lc_free(parent) == 0
    assert lc_subwin(parent, 2, 2, 0, 0) is None


def test_panel_content_rect_matches_box_interior():
    assert lc_panel_content_rect(1, 2, 5, 8) == (2, 3, 3, 6)


def test_panel_content_subwin_uses_interior_rect():
    parent = lc_new(10, 12, 0, 0)
    sub = lc_panel_subwin(parent, 1, 2, 5, 8)

    assert sub is not None
    assert sub.parent is parent
    assert sub.begy == 2
    assert sub.begx == 3
    assert sub.maxy == 3
    assert sub.maxx == 6
    assert sub.pary == 2
    assert sub.parx == 3


def test_panel_content_subwin_rejects_degenerate_panel():
    parent = lc_new(6, 6, 0, 0)
    assert lc_panel_subwin(parent, 0, 0, 1, 4) is None
    assert lc_panel_subwin(parent, 0, 0, 4, 1) is None
    assert lc_panel_subwin(parent, 0, 0, 2, 2) is None


def test_panel_content_subwin_shares_backing_store():
    parent = lc_new(6, 10, 0, 0)
    sub = lc_panel_subwin(parent, 1, 1, 4, 6)
    assert sub is not None

    assert lc_wfill(sub, 0, 0, sub.maxy, sub.maxx, ".", 7) == 0

    assert _row_text(parent, 0) == "          "
    assert _row_text(parent, 1) == "          "
    assert _row_text(parent, 2) == "  ....    "
    assert _row_text(parent, 3) == "  ....    "
    assert _row_text(parent, 4) == "          "
    assert _row_text(parent, 5) == "          "
    assert parent.lines[2].line[2].attr == 7
    assert parent.lines[3].line[5].attr == 7


def test_panel_content_subwin_nested_under_child_window():
    parent = lc_new(8, 12, 5, 7)
    child = lc_subwin(parent, 6, 10, 1, 1)
    sub = lc_panel_subwin(child, 1, 2, 4, 5)
    assert child is not None
    assert sub is not None
    assert sub.root is parent
    assert sub.parent is child
    assert sub.begy == 8
    assert sub.begx == 11


def test_invalidate_children_kills_direct_children():
    parent = lc_new(6, 6, 0, 0)
    child1 = lc_subwin(parent, 2, 2, 0, 0)
    child2 = lc_subwin(parent, 2, 2, 2, 2)

    assert child1 is not None
    assert child2 is not None
    assert len(parent.children) == 2

    lc_invalidate_children(parent)

    assert parent.alive is True
    assert parent.children == []
    assert child1.alive is False
    assert child2.alive is False
    assert child1.lines == []
    assert child2.lines == []


def test_invalidate_children_kills_nested_subtree():
    parent = lc_new(8, 8, 0, 0)
    child = lc_subwin(parent, 6, 6, 1, 1)
    grand = lc_subwin(child, 2, 2, 2, 2)

    assert child is not None
    assert grand is not None

    lc_invalidate_children(parent)

    assert parent.alive is True
    assert parent.children == []
    assert child.alive is False
    assert grand.alive is False


def test_dead_children_fail_after_invalidation():
    parent = lc_new(6, 6, 0, 0)
    child = lc_subwin(parent, 2, 2, 1, 1)
    assert child is not None

    lc_invalidate_children(parent)

    assert lc_wmove(child, 0, 0) == -1
    assert lc_waddstr(child, "x") == -1
    assert lc_wfill(child, 0, 0, 1, 1, ".", 1) == -1
