from lc_refresh import lc_wrefresh
from lc_screen import lc
from lc_term import LC_ATTR_BOLD, LC_ATTR_NONE
from lc_window import LCCell, LCRow, LCWin


class FakeTerm:
    def __init__(self) -> None:
        self.out_fd = 1
        self._last_attr = None
        self.writes: list[bytes] = []

    def write_bytes(self, data: bytes | bytearray) -> None:
        if data:
            self.writes.append(bytes(data))

    def move_bytes(self, y: int, x: int) -> bytes:
        return f"\x1b[{y + 1};{x + 1}H".encode("ascii")

    def attr_bytes(self, attr: int) -> bytes:
        if attr == LC_ATTR_NONE:
            return b"\x1b[0m"
        parts = ["0"]
        if attr & LC_ATTR_BOLD:
            parts.append("1")
        return ("\x1b[" + ";".join(parts) + "m").encode("ascii")

    def encode_text(self, s: str) -> bytes:
        return s.encode("utf-8", "replace")

    def clear_screen(self) -> None:
        pass

    def reset_state(self) -> None:
        self._last_attr = None


def _make_win(rows: int, cols: int) -> LCWin:
    lines = []
    for _ in range(rows):
        row_cells = [LCCell(' ', LC_ATTR_NONE) for _ in range(cols)]
        row = LCRow(line=row_cells, firstch=0, lastch=cols - 1, flags=3)
        lines.append(row)
    return LCWin(maxy=rows, maxx=cols, begy=0, begx=0, cury=0, curx=0, lines=lines)


def _setup_lc(rows: int, cols: int) -> FakeTerm:
    lc.lines = rows
    lc.cols = cols
    lc.screen = [[LCCell(' ', LC_ATTR_NONE) for _ in range(cols)] for _ in range(rows)]
    lc.hashes = [0 for _ in range(rows)]
    lc.cur_y = 0
    lc.cur_x = 0
    lc.cur_attr = LC_ATTR_NONE
    fake = FakeTerm()
    lc.term = fake  # type: ignore
    return fake


def test_lc_wrefresh_none_returns_error() -> None:
    assert lc_wrefresh(None) == -1


def test_lc_wrefresh_single_cell() -> None:
    fake = _setup_lc(10, 10)
    win = _make_win(10, 10)
    win.lines[0].line[0] = LCCell('A', LC_ATTR_NONE)
    result = lc_wrefresh(win)
    assert result == 0
    combined = b"".join(fake.writes)
    # Should contain the character 'A'
    assert b"A" in combined


def test_lc_wrefresh_coalesces_adjacent_cells() -> None:
    fake = _setup_lc(10, 10)
    win = _make_win(10, 10)
    # Set "ABC" starting at position 0
    win.lines[0].line[0] = LCCell('A', LC_ATTR_NONE)
    win.lines[0].line[1] = LCCell('B', LC_ATTR_NONE)
    win.lines[0].line[2] = LCCell('C', LC_ATTR_NONE)
    result = lc_wrefresh(win)
    assert result == 0
    combined = b"".join(fake.writes)
    # Adjacent cells with same attr should be coalesced
    assert b"ABC" in combined


def test_lc_wrefresh_attr_change_splits_run() -> None:
    fake = _setup_lc(10, 10)
    win = _make_win(10, 10)
    win.lines[0].line[0] = LCCell('A', LC_ATTR_NONE)
    win.lines[0].line[1] = LCCell('B', LC_ATTR_BOLD)
    win.lines[0].line[2] = LCCell('C', LC_ATTR_BOLD)
    result = lc_wrefresh(win)
    assert result == 0
    combined = b"".join(fake.writes)
    # 'A' should be separate from 'BC' due to attr change
    assert b"A" in combined
    assert b"BC" in combined


def test_lc_wrefresh_resets_attr_at_end() -> None:
    fake = _setup_lc(10, 10)
    win = _make_win(10, 10)
    win.lines[0].line[0] = LCCell('X', LC_ATTR_BOLD)
    result = lc_wrefresh(win)
    assert result == 0
    combined = b"".join(fake.writes)
    # Should end with attr reset
    assert combined.endswith(b"\x1b[0m")


def test_lc_wrefresh_skips_unchanged_cells() -> None:
    fake = _setup_lc(10, 10)
    # Pre-fill screen with 'A'
    lc.screen[0][0] = LCCell('A', LC_ATTR_NONE)
    win = _make_win(10, 10)
    win.lines[0].line[0] = LCCell('A', LC_ATTR_NONE)
    # Force the line to be non-dirty initially
    win.lines[0].flags = 0
    result = lc_wrefresh(win)
    assert result == 0
    # Combine all output and verify 'A' was not written
    combined = b"".join(fake.writes)
    # Since the line is not dirty, no cell content should be written
    # Only the final cursor move and attr reset should appear
    assert b"A" not in combined
