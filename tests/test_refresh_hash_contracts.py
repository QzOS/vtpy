import lc_refresh
import lc_screen
from lc_window import lc_new, lc_subwin


class _RecordingTerm:
    def __init__(self) -> None:
        self._last_attr = None
        self.writes = []

    def move_bytes(self, y: int, x: int) -> bytes:
        return b""

    def attr_bytes(self, attr: int) -> bytes:
        return b""

    def encode_text(self, s: str) -> bytes:
        return s.encode("utf-8", "replace")

    def write_bytes(self, data: bytes | bytearray) -> None:
        self.writes.append(bytes(data))

    def clear_screen(self) -> None:
        pass

    def reset_state(self) -> None:
        self._last_attr = None

    def note_attr(self, attr: int) -> None:
        self._last_attr = attr


def _install_test_screen(win):
    term = _RecordingTerm()
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
    lc_screen.lc.term = term
    return term


def _concat_writes(term: _RecordingTerm) -> bytes:
    return b"".join(term.writes)


def test_line_hash_distinguishes_high_attr_bits():
    row_a = [
        lc_screen.LCCell("A", 0x0001),
        lc_screen.LCCell("B", 0x0002),
    ]
    row_b = [
        lc_screen.LCCell("A", 0x0101),
        lc_screen.LCCell("B", 0x0102),
    ]

    assert lc_refresh.line_hash(row_a) != lc_refresh.line_hash(row_b)


def test_root_row_hash_shortcut_can_skip_clean_repeat_refresh(monkeypatch):
    root = lc_new(1, 4, 0, 0)
    assert root is not None
    term = _install_test_screen(root)

    monkeypatch.setattr(lc_refresh, "lc_check_resize", lambda: 0)

    root.lines[0].line[0].ch = "A"
    root.lines[0].line[1].ch = "B"
    root.lines[0].line[2].ch = "C"
    root.lines[0].line[3].ch = "D"
    root.lines[0].firstch = 0
    root.lines[0].lastch = 3
    root.lines[0].flags = lc_screen.LC_DIRTY

    assert lc_refresh.lc_wrefresh(root) == 0
    first_payload = _concat_writes(term)
    assert b"ABCD" in first_payload

    term.writes.clear()
    root.lines[0].firstch = 0
    root.lines[0].lastch = 3
    root.lines[0].flags = lc_screen.LC_DIRTY

    assert lc_refresh.lc_wrefresh(root) == 0
    second_payload = _concat_writes(term)

    # No changed cells should be emitted on the second pass.
    assert b"ABCD" not in second_payload


def test_subwindow_refresh_does_not_poison_root_row_hash_shortcut(monkeypatch):
    root = lc_new(1, 6, 0, 0)
    assert root is not None
    sub = lc_subwin(root, 1, 3, 0, 1)
    assert sub is not None
    term = _install_test_screen(root)

    monkeypatch.setattr(lc_refresh, "lc_check_resize", lambda: 0)

    # Initial full-root render establishes the physical-row cache state.
    text = "ABCDEF"
    for i, ch in enumerate(text):
        root.lines[0].line[i].ch = ch
    root.lines[0].firstch = 0
    root.lines[0].lastch = 5
    root.lines[0].flags = lc_screen.LC_DIRTY

    assert lc_refresh.lc_wrefresh(root) == 0
    assert lc_screen.lc.hashes[0] == lc_refresh.line_hash(root.lines[0].line)

    # Now change only the subwindow slice and refresh via the subwindow.
    term.writes.clear()
    sub.lines[0].line[0].ch = "x"
    sub.lines[0].line[1].ch = "y"
    sub.lines[0].line[2].ch = "z"
    sub.lines[0].firstch = 0
    sub.lines[0].lastch = 2
    sub.lines[0].flags = lc_screen.LC_DIRTY

    old_root_hash = lc_screen.lc.hashes[0]
    assert lc_refresh.lc_wrefresh(sub) == 0
    sub_payload = _concat_writes(term)
    assert b"xyz" in sub_payload

    # Subwindow refresh must not overwrite the physical full-row hash cache.
    assert lc_screen.lc.hashes[0] == old_root_hash

    # A subsequent root refresh should compute and store the new full-row hash.
    term.writes.clear()
    root.lines[0].firstch = 0
    root.lines[0].lastch = 5
    root.lines[0].flags = lc_screen.LC_DIRTY

    assert lc_refresh.lc_wrefresh(root) == 0
    assert lc_screen.lc.hashes[0] == lc_refresh.line_hash(root.lines[0].line)


def test_subwindow_refresh_followed_by_root_refresh_emits_no_spurious_full_row_rewrite(monkeypatch):
    root = lc_new(1, 6, 0, 0)
    assert root is not None
    sub = lc_subwin(root, 1, 2, 0, 2)
    assert sub is not None
    term = _install_test_screen(root)

    monkeypatch.setattr(lc_refresh, "lc_check_resize", lambda: 0)

    # Render initial root row.
    for i, ch in enumerate("ABCDEF"):
        root.lines[0].line[i].ch = ch
    root.lines[0].firstch = 0
    root.lines[0].lastch = 5
    root.lines[0].flags = lc_screen.LC_DIRTY
    root.lines[0].flags |= lc_screen.LC_FORCEPAINT
    assert lc_refresh.lc_wrefresh(root) == 0

    # Refresh changed subwindow content.
    term.writes.clear()
    sub.lines[0].line[0].ch = "X"
    sub.lines[0].line[1].ch = "Y"
    sub.lines[0].firstch = 0
    sub.lines[0].lastch = 1
    sub.lines[0].flags = lc_screen.LC_DIRTY
    assert lc_refresh.lc_wrefresh(sub) == 0
    sub_payload = _concat_writes(term)
    assert b"XY" in sub_payload

    # Root refresh over the now-updated full row should not need to emit
    # another full text rewrite if nothing changed since the subwindow render.
    term.writes.clear()
    root.lines[0].firstch = 0
    root.lines[0].lastch = 5
    root.lines[0].flags = lc_screen.LC_DIRTY
    assert lc_refresh.lc_wrefresh(root) == 0
    root_payload = _concat_writes(term)

    # Cursor motion/reset bytes may still exist, but the row text itself
    # should not be emitted again.
    assert b"ABXYEF" not in root_payload


def test_row_hash_shortcut_is_not_used_for_non_full_width_root_window(monkeypatch):
    root = lc_new(1, 4, 0, 1)
    assert root is not None
    term = _install_test_screen(root)

    monkeypatch.setattr(lc_refresh, "lc_check_resize", lambda: 0)

    for i, ch in enumerate("WXYZ"):
        root.lines[0].line[i].ch = ch
    root.lines[0].firstch = 0
    root.lines[0].lastch = 3
    root.lines[0].flags = lc_screen.LC_DIRTY

    assert lc_refresh.lc_wrefresh(root) == 0

    # Because this root window does not map to the full physical row domain,
    # the full-row hash shortcut should not claim ownership of that row cache.
    assert lc_screen.lc.hashes[0] == 0
