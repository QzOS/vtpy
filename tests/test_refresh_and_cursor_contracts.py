import lc_refresh
import lc_screen
from lc_term import LC_DIRTY
from lc_window import (
    lc_new,
    lc_subwin,
    lc_free,
    lc_wmove,
    lc_wput,
    lc_waddstr,
)


class _DummyTerm:
    def __init__(self) -> None:
        self._last_attr = None

    def move_bytes(self, y: int, x: int) -> bytes:
        return b""

    def attr_bytes(self, attr: int) -> bytes:
        return b""

    def encode_text(self, s: str) -> bytes:
        return s.encode("utf-8", "replace")

    def write_bytes(self, data: bytes | bytearray) -> None:
        pass

    def clear_screen(self) -> None:
        pass

    def reset_state(self) -> None:
        self._last_attr = None

    def note_attr(self, attr: int) -> None:
        self._last_attr = attr


def _install_test_screen(win):
    lc_screen.lc.stdscr = win
    lc_screen.lc.lines = win.maxy
    lc_screen.lc.cols = win.maxx
    lc_screen.lc.screen = [
        [lc_screen.LCCell(" ", 0) for _x in range(win.maxx)]
        for _y in range(win.maxy)
    ]
    lc_screen.lc.hashes = [0 for _ in range(win.maxy)]
    lc_screen.lc.cur_y = 0
    lc_screen.lc.cur_x = 0
    lc_screen.lc.cur_attr = 0
    lc_screen.lc.resize_pending = False
    lc_screen.lc.term = _DummyTerm()


def test_parent_write_updates_child_shared_cells_without_marking_child_dirty():
    root = lc_new(3, 6, 0, 0)
    assert root is not None

    child = lc_subwin(root, 1, 3, 1, 1)
    assert child is not None

    for ln in root.lines:
        ln.flags = 0
        ln.firstch = 0
        ln.lastch = 0
    for ln in child.lines:
        ln.flags = 0
        ln.firstch = 0
        ln.lastch = 0

    assert lc_wmove(root, 1, 1) == 0
    assert lc_waddstr(root, "abc") == 0

    # Shared backing means child sees the updated cells.
    assert "".join(cell.ch for cell in child.lines[0].line) == "abc"

    # Dirty state is not shared symmetrically: root is dirty, child need not be.
    assert root.lines[1].flags & LC_DIRTY
    assert child.lines[0].flags == 0


def test_sibling_write_does_not_mark_overlapping_sibling_dirty():
    root = lc_new(3, 6, 0, 0)
    assert root is not None

    a = lc_subwin(root, 1, 3, 1, 1)
    b = lc_subwin(root, 1, 3, 1, 1)
    assert a is not None
    assert b is not None

    for ln in root.lines:
        ln.flags = 0
        ln.firstch = 0
        ln.lastch = 0
    for ln in a.lines:
        ln.flags = 0
        ln.firstch = 0
        ln.lastch = 0
    for ln in b.lines:
        ln.flags = 0
        ln.firstch = 0
        ln.lastch = 0

    assert lc_wmove(a, 0, 0) == 0
    assert lc_waddstr(a, "xyz") == 0

    # Shared backing means the overlapping sibling sees the new cells.
    assert "".join(cell.ch for cell in b.lines[0].line) == "xyz"

    # Dirty state propagates upward, not laterally.
    assert a.lines[0].flags & LC_DIRTY
    assert root.lines[1].flags & LC_DIRTY
    assert b.lines[0].flags == 0


def test_parent_write_does_not_make_child_refresh_a_coherent_commit_guarantee(monkeypatch):
    root = lc_new(2, 5, 0, 0)
    assert root is not None

    child = lc_subwin(root, 1, 3, 0, 1)
    assert child is not None

    _install_test_screen(root)
    monkeypatch.setattr(lc_refresh, "lc_check_resize", lambda: 0)

    # Establish an initially synchronized physical-screen cache.
    assert lc_refresh.lc_wrefresh(root) == 0

    for ln in root.lines:
        ln.flags = 0
        ln.firstch = 0
        ln.lastch = 0
    for ln in child.lines:
        ln.flags = 0
        ln.firstch = 0
        ln.lastch = 0

    assert lc_wmove(root, 0, 1) == 0
    assert lc_waddstr(root, "abc") == 0

    # Parent-originated writes update shared child cells, but do not have to
    # mark the child view dirty.
    assert "".join(cell.ch for cell in child.lines[0].line) == "abc"
    assert child.lines[0].flags == 0

    # A child refresh may succeed as an operation, but it is not the coherence
    # guarantee for parent-originated writes into shared backing.
    assert lc_refresh.lc_wrefresh(child) == 0

    # Root refresh remains the coherent commit path.
    assert lc_refresh.lc_wrefresh(root) == 0
    assert "".join(cell.ch for cell in lc_screen.lc.screen[0][1:4]) == "abc"


def test_wrefresh_rejects_dead_window(monkeypatch):
    win = lc_new(3, 4, 0, 0)
    assert win is not None
    _install_test_screen(win)

    assert lc_free(win) == 0
    assert win.alive is False

    monkeypatch.setattr(lc_refresh, "lc_check_resize", lambda: 0)

    assert lc_refresh.lc_wrefresh(win) == -1


def test_wput_saturates_cursor_at_last_cell():
    win = lc_new(2, 3, 0, 0)
    assert win is not None

    assert lc_wmove(win, 1, 2) == 0
    assert lc_wput(win, ord("X")) == 0

    assert win.cury == 1
    assert win.curx == 2
    assert win.lines[1].line[2].ch == "X"

    assert lc_wput(win, ord("Y")) == 0
    assert win.cury == 1
    assert win.curx == 2
    assert win.lines[1].line[2].ch == "Y"


def test_waddstr_saturates_cursor_at_last_cell_and_does_not_wrap_to_row_start():
    win = lc_new(2, 3, 0, 0)
    assert win is not None

    assert lc_wmove(win, 1, 2) == 0
    assert lc_waddstr(win, "XY") == 0

    assert win.cury == 1
    assert win.curx == 2
    assert win.lines[1].line[2].ch == "X"
    assert win.lines[1].line[0].ch == " "
    assert win.lines[1].line[1].ch == " "


def test_waddstr_from_penultimate_cell_writes_until_boundary_and_saturates():
    win = lc_new(2, 3, 0, 0)
    assert win is not None

    assert lc_wmove(win, 1, 1) == 0
    assert lc_waddstr(win, "XYZ") == 0

    assert win.lines[1].line[1].ch == "X"
    assert win.lines[1].line[2].ch == "Y"
    assert win.cury == 1
    assert win.curx == 2


def test_wput_and_waddstr_share_same_last_cell_policy():
    a = lc_new(1, 2, 0, 0)
    b = lc_new(1, 2, 0, 0)
    assert a is not None
    assert b is not None

    assert lc_wmove(a, 0, 1) == 0
    assert lc_wmove(b, 0, 1) == 0

    assert lc_wput(a, ord("Q")) == 0
    assert lc_waddstr(b, "Q") == 0

    assert a.cury == b.cury == 0
    assert a.curx == b.curx == 1
    assert a.lines[0].line[1].ch == "Q"
    assert b.lines[0].line[1].ch == "Q"


def test_wrefresh_rejects_stale_subwindow_after_resize(monkeypatch):
    root = lc_new(4, 5, 0, 0)
    assert root is not None

    sub = lc_subwin(root, 2, 2, 1, 1)
    assert sub is not None
    assert sub.alive is True

    _install_test_screen(root)

    replacement = lc_new(6, 7, 0, 0)
    assert replacement is not None

    def _fake_check_resize():
        old = lc_screen.lc.stdscr
        assert old is root
        assert sub.alive is True

        # Simulate the contract effect of a root resize rebuild:
        # all existing derived windows are invalidated, stdscr replaced.
        lc_screen.lc.stdscr = replacement
        lc_screen.lc.lines = replacement.maxy
        lc_screen.lc.cols = replacement.maxx
        lc_screen.lc.screen = [
            [lc_screen.LCCell(" ", 0) for _x in range(replacement.maxx)]
            for _y in range(replacement.maxy)
        ]
        lc_screen.lc.hashes = [0 for _ in range(replacement.maxy)]
        lc_screen.lc.cur_y = 0
        lc_screen.lc.cur_x = 0
        lc_screen.lc.cur_attr = 0
        lc_screen.lc.term = _DummyTerm()

        assert lc_free(sub) == 0
        return 1

    monkeypatch.setattr(lc_refresh, "lc_check_resize", _fake_check_resize)

    assert lc_refresh.lc_wrefresh(sub) == -1
    assert sub.alive is False


def test_wrefresh_root_after_resize_uses_rebuilt_stdscr(monkeypatch):
    root = lc_new(3, 3, 0, 0)
    assert root is not None
    _install_test_screen(root)

    replacement = lc_new(4, 4, 0, 0)
    assert replacement is not None
    replacement.lines[0].line[0].ch = "Z"

    def _fake_check_resize():
        lc_screen.lc.stdscr = replacement
        lc_screen.lc.lines = replacement.maxy
        lc_screen.lc.cols = replacement.maxx
        lc_screen.lc.screen = [
            [lc_screen.LCCell(" ", 0) for _x in range(replacement.maxx)]
            for _y in range(replacement.maxy)
        ]
        lc_screen.lc.hashes = [0 for _ in range(replacement.maxy)]
        lc_screen.lc.cur_y = 0
        lc_screen.lc.cur_x = 0
        lc_screen.lc.cur_attr = 0
        lc_screen.lc.term = _DummyTerm()
        return 1

    monkeypatch.setattr(lc_refresh, "lc_check_resize", _fake_check_resize)

    assert lc_refresh.lc_wrefresh(root) == 0
