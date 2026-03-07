"""Tests for session/backend lifecycle guards introduced in the refresh refactor.

These tests verify the behaviour of:
- lc_check_resize and lc_is_resize_pending when backend is live but session
  is not yet fully active
- lc_refresh_session_ready with every combination of backend_started / session_active
- lc_refresh_resize_gate and lc_refresh_target_after_resize edge cases
- lc_wstage and lc_wstageflush as explicit public entry points
"""
import lc_refresh
from lc_refresh import lc_doupdate, lc_wstage, lc_wstageflush
from lc_screen import (
    lc,
    lc_check_resize,
    lc_is_resize_pending,
    lc_refresh_resize_gate,
    lc_refresh_session_ready,
    lc_refresh_target_after_resize,
)
from lc_term import LC_ATTR_NONE
from lc_window import LCCell, LCRow, LCWin, lc_new


# ---------------------------------------------------------------------------
# Helpers shared across this module
# ---------------------------------------------------------------------------

class _FakeTerm:
    def __init__(self) -> None:
        self._last_attr = None
        self.writes: list[bytes] = []
        self.clear_calls: int = 0
        self.reset_calls: int = 0

    def write_bytes(self, data: bytes | bytearray) -> None:
        if data:
            self.writes.append(bytes(data))

    def move_bytes(self, y: int, x: int) -> bytes:
        return f"\x1b[{y + 1};{x + 1}H".encode("ascii")

    def attr_bytes(self, attr: int) -> bytes:
        return b"\x1b[0m" if attr == LC_ATTR_NONE else b"\x1b[1m"

    def encode_text(self, s: str) -> bytes:
        return s.encode("utf-8", "replace")

    def clear_screen(self) -> None:
        self.clear_calls += 1

    def note_attr(self, attr: int) -> None:
        self._last_attr = attr

    def reset_state(self) -> None:
        self.reset_calls += 1


def _make_win(rows: int, cols: int, begy: int = 0, begx: int = 0) -> LCWin:
    lines = []
    for _ in range(rows):
        cells = [LCCell(" ", LC_ATTR_NONE) for _ in range(cols)]
        row = LCRow(line=cells, firstch=0, lastch=cols - 1, flags=3)
        lines.append(row)
    return LCWin(
        maxy=rows, maxx=cols, begy=begy, begx=begx,
        cury=0, curx=0, lines=lines,
    )


def _setup_lc(rows: int, cols: int) -> _FakeTerm:
    """Minimal lc setup that mirrors the in-test pattern used across the suite."""
    lc.lines = rows
    lc.cols = cols
    lc.stdscr = None
    lc.screen = [[LCCell(" ", LC_ATTR_NONE) for _ in range(cols)] for _ in range(rows)]
    lc.vscreen = [[LCCell(" ", LC_ATTR_NONE) for _ in range(cols)] for _ in range(rows)]
    lc.vdirty_first = [-1 for _ in range(rows)]
    lc.vdirty_last = [-1 for _ in range(rows)]
    lc.cur_y = 0
    lc.cur_x = 0
    lc.cur_attr = LC_ATTR_NONE
    lc.virtual_cur_y = 0
    lc.virtual_cur_x = 0
    lc.virtual_cursor_valid = False
    lc.backend_started = False
    lc.session_active = False
    lc.resize_pending = False
    fake = _FakeTerm()
    lc.term = fake  # type: ignore
    return fake


# ---------------------------------------------------------------------------
# lc_refresh_session_ready
# ---------------------------------------------------------------------------

def test_session_ready_when_backend_not_started() -> None:
    # When the backend has never been started the function always returns True
    # so that tests and offline usage work without a live backend.
    lc.backend_started = False
    lc.session_active = False
    lc.stdscr = None
    assert lc_refresh_session_ready() is True


def test_session_ready_when_backend_live_and_session_active_with_stdscr() -> None:
    win = lc_new(2, 4, 0, 0)
    lc.backend_started = True
    lc.session_active = True
    lc.stdscr = win
    assert lc_refresh_session_ready() is True


def test_session_not_ready_when_backend_live_but_session_inactive() -> None:
    lc.backend_started = True
    lc.session_active = False
    lc.stdscr = None
    assert lc_refresh_session_ready() is False


def test_session_not_ready_when_backend_live_and_session_active_but_no_stdscr() -> None:
    lc.backend_started = True
    lc.session_active = True
    lc.stdscr = None
    assert lc_refresh_session_ready() is False


# ---------------------------------------------------------------------------
# lc_check_resize session guard
# ---------------------------------------------------------------------------

def test_check_resize_suppressed_when_backend_live_but_session_inactive(monkeypatch) -> None:
    # When the backend has been started but the session is not yet fully
    # active, lc_check_resize should return 0 (no-op) rather than
    # attempting a resize rebuild against an uninitialised stdscr.
    lc.backend_started = True
    lc.session_active = False
    lc.stdscr = None
    lc.resize_pending = True

    monkeypatch.setattr("lc_screen.backend.get_size", lambda state: (10, 20))
    assert lc_check_resize() == 0
    # stdscr remains None – no rebuild attempted
    assert lc.stdscr is None


def test_check_resize_proceeds_when_session_active(monkeypatch) -> None:
    win = lc_new(2, 3, 0, 0)
    lc.stdscr = win
    lc.lines = 2
    lc.cols = 3
    lc.screen = [[None for _ in range(3)] for _ in range(2)]
    lc.resize_pending = True
    lc.backend_started = True
    lc.session_active = True
    lc.term = _FakeTerm()  # type: ignore

    monkeypatch.setattr("lc_screen.backend.get_size", lambda state: (4, 5))
    rc = lc_check_resize()
    assert rc == 1
    assert lc.lines == 4
    assert lc.cols == 5


# ---------------------------------------------------------------------------
# lc_is_resize_pending session guard
# ---------------------------------------------------------------------------

def test_is_resize_pending_suppressed_when_backend_live_but_session_inactive(
    monkeypatch,
) -> None:
    lc.backend_started = True
    lc.session_active = False
    lc.resize_pending = True

    # Even with a pending resize, the function returns False when the session
    # is not yet active and the backend is live.
    monkeypatch.setattr("lc_screen.backend.poll_resize", lambda state: True)
    assert lc_is_resize_pending() is False


def test_is_resize_pending_returns_true_when_session_active(monkeypatch) -> None:
    lc.backend_started = True
    lc.session_active = True
    lc.resize_pending = True

    monkeypatch.setattr("lc_screen.backend.poll_resize", lambda state: False)
    assert lc_is_resize_pending() is True


# ---------------------------------------------------------------------------
# lc_refresh_resize_gate
# ---------------------------------------------------------------------------

def test_refresh_resize_gate_returns_minus_one_when_session_not_ready() -> None:
    lc.backend_started = True
    lc.session_active = False
    lc.stdscr = None
    assert lc_refresh_resize_gate() == -1


def test_refresh_resize_gate_delegates_to_check_resize_when_ready(monkeypatch) -> None:
    win = lc_new(2, 4, 0, 0)
    lc.stdscr = win
    lc.lines = 2
    lc.cols = 4
    lc.backend_started = False
    lc.session_active = False
    lc.resize_pending = False

    monkeypatch.setattr("lc_screen.backend.get_size", lambda state: (2, 4))
    assert lc_refresh_resize_gate() == 0


# ---------------------------------------------------------------------------
# lc_refresh_target_after_resize
# ---------------------------------------------------------------------------

def test_target_after_resize_returns_none_for_dead_window() -> None:
    win = lc_new(2, 4, 0, 0)
    win.alive = False
    assert lc_refresh_target_after_resize(win, 0) is None


def test_target_after_resize_returns_none_when_rc_negative() -> None:
    win = lc_new(2, 4, 0, 0)
    assert lc_refresh_target_after_resize(win, -1) is None


def test_target_after_resize_returns_same_window_when_no_resize() -> None:
    win = lc_new(2, 4, 0, 0)
    result = lc_refresh_target_after_resize(win, 0)
    assert result is win


def test_target_after_resize_returns_none_for_derived_window_after_resize() -> None:
    # Derived windows (parent is not None) are not remapped after a resize.
    parent = lc_new(4, 8, 0, 0)
    child = lc_new(2, 4, 1, 1)
    child.parent = parent
    assert lc_refresh_target_after_resize(child, 1) is None


# ---------------------------------------------------------------------------
# lc_wstage
# ---------------------------------------------------------------------------

def test_lc_wstage_returns_error_for_none() -> None:
    assert lc_wstage(None) == -1


def test_lc_wstage_stages_dirty_cells_without_terminal_output() -> None:
    fake = _setup_lc(2, 4)
    win = _make_win(2, 4)
    win.lines[0].line[1] = LCCell("X", LC_ATTR_NONE)

    assert lc_wstage(win) == 0

    # No terminal output at this point
    assert fake.writes == []
    # The staged cell is visible in the virtual screen
    assert lc.vscreen[0][1].ch == "X"


def test_lc_wstage_followed_by_doupdate_emits_output() -> None:
    fake = _setup_lc(1, 4)
    win = _make_win(1, 4)
    win.lines[0].line[0] = LCCell("H", LC_ATTR_NONE)
    win.lines[0].line[1] = LCCell("i", LC_ATTR_NONE)

    assert lc_wstage(win) == 0
    assert lc_doupdate() == 0

    payload = b"".join(fake.writes)
    assert b"Hi" in payload


def test_lc_wstage_second_stage_overwrites_first() -> None:
    fake = _setup_lc(1, 4)
    win_a = _make_win(1, 4)
    win_b = _make_win(1, 4)

    win_a.lines[0].line[0] = LCCell("A", LC_ATTR_NONE)
    win_b.lines[0].line[0] = LCCell("B", LC_ATTR_NONE)
    win_b.lines[0].firstch = 0
    win_b.lines[0].lastch = 0

    assert lc_wstage(win_a) == 0
    assert lc_wstage(win_b) == 0
    assert lc_doupdate() == 0

    payload = b"".join(fake.writes)
    assert b"B" in payload
    # 'A' in position 0 was overwritten by 'B'; should not appear
    assert b"A" not in payload


# ---------------------------------------------------------------------------
# lc_wstageflush
# ---------------------------------------------------------------------------

def test_lc_wstageflush_returns_error_for_none() -> None:
    assert lc_wstageflush(None) == -1


def test_lc_wstageflush_stages_and_emits_in_one_call() -> None:
    fake = _setup_lc(1, 3)
    win = _make_win(1, 3)
    win.lines[0].line[0] = LCCell("Z", LC_ATTR_NONE)

    assert lc_wstageflush(win) == 0

    payload = b"".join(fake.writes)
    assert b"Z" in payload
