from lc_screen import lc, lc_check_resize, lc_get_size, lc_is_resize_pending
from lc_term import LC_ATTR_NONE, LC_DIRTY, LC_FORCEPAINT
from lc_keys import LCKey, LCKeyParser, LC_KT_KEYSYM, LC_KEY_RESIZE
from lc_window import lc_new


def test_check_resize_noop_when_size_unchanged(monkeypatch):
    win = lc_new(3, 4, 0, 0)
    lc.stdscr = win
    lc.lines = 3
    lc.cols = 4
    lc.screen = []
    lc.resize_pending = False

    monkeypatch.setattr("lc_screen.backend.get_size", lambda state: (3, 4))
    assert lc_check_resize() == 0
    assert lc.stdscr is win


def test_check_resize_rebuilds_screen_and_preserves_overlap(monkeypatch):
    win = lc_new(2, 3, 0, 0)
    win.lines[0].line[0].ch = "A"
    win.lines[0].line[1].ch = "B"
    win.lines[1].line[2].ch = "Z"
    win.cury = 1
    win.curx = 2

    lc.stdscr = win
    lc.lines = 2
    lc.cols = 3
    lc.screen = [[None for _ in range(3)] for _ in range(2)]
    lc.resize_pending = True
    lc.cur_y = 9
    lc.cur_x = 9
    lc.cur_attr = 99

    class FakeTerm:
        def __init__(self):
            self.reset_calls = 0

        def reset_state(self):
            self.reset_calls += 1

    fake_term = FakeTerm()
    lc.term = fake_term

    monkeypatch.setattr("lc_screen.backend.get_size", lambda state: (4, 5))
    assert lc_check_resize() == 1

    assert lc.lines == 4
    assert lc.cols == 5
    assert lc.stdscr is not win
    assert lc.stdscr.lines[0].line[0].ch == "A"
    assert lc.stdscr.lines[0].line[1].ch == "B"
    assert lc.stdscr.lines[1].line[2].ch == "Z"
    assert lc.stdscr.cury == 1
    assert lc.stdscr.curx == 2
    assert len(lc.screen) == 4
    assert len(lc.screen[0]) == 5
    assert lc.cur_y == 0
    assert lc.cur_x == 0
    assert lc.cur_attr == LC_ATTR_NONE
    assert fake_term.reset_calls == 1
    assert lc.resize_pending is False

    for row in lc.stdscr.lines:
        assert row.firstch == 0
        assert row.lastch == lc.stdscr.maxx - 1
        assert row.flags == (LC_DIRTY | LC_FORCEPAINT)


def test_check_resize_clamps_cursor_when_new_size_is_smaller(monkeypatch):
    win = lc_new(4, 5, 0, 0)
    win.cury = 3
    win.curx = 4

    lc.stdscr = win
    lc.lines = 4
    lc.cols = 5
    lc.screen = [[None for _ in range(5)] for _ in range(4)]
    lc.resize_pending = True

    class FakeTerm:
        def reset_state(self):
            pass

    lc.term = FakeTerm()

    monkeypatch.setattr("lc_screen.backend.get_size", lambda state: (2, 3))
    assert lc_check_resize() == 1
    assert lc.stdscr.cury == 1
    assert lc.stdscr.curx == 2


def test_check_resize_ignores_invalid_size(monkeypatch):
    win = lc_new(2, 2, 0, 0)
    lc.stdscr = win
    lc.lines = 2
    lc.cols = 2
    lc.resize_pending = True

    monkeypatch.setattr("lc_screen.backend.get_size", lambda state: (0, 0))
    assert lc_check_resize() == 0
    assert lc.stdscr is win
    assert lc.resize_pending is False


def test_resize_pending_api():
    lc.resize_pending = False
    assert lc_is_resize_pending() is False
    lc.resize_pending = True
    assert lc_is_resize_pending() is True


def test_get_size_api():
    lc.lines = 17
    lc.cols = 63
    assert lc_get_size() == (17, 63)


def test_readkey_returns_resize_event(monkeypatch):
    win = lc_new(2, 2, 0, 0)
    lc.stdscr = win
    lc.lines = 2
    lc.cols = 2
    lc.screen = [[None for _ in range(2)] for _ in range(2)]
    lc.resize_pending = True
    lc.nodelay_on = False

    class FakeTerm:
        def reset_state(self):
            pass

    class FakeInput:
        def unread_byte(self, ch: int) -> None:
            pass

        def read_byte(self):
            return None

        def input_pending(self, timeout_ms: int) -> bool:
            return False

    lc.term = FakeTerm()

    monkeypatch.setattr("lc_screen.backend.get_size", lambda state: (3, 4))

    parser = LCKeyParser(FakeInput())
    key = LCKey()
    assert parser.readkey(key) == 0
    assert key.type == LC_KT_KEYSYM
    assert key.keysym == LC_KEY_RESIZE
    assert key.rune == 0
    assert key.mods == 0
    assert lc.resize_pending is False
    assert lc.lines == 3
    assert lc.cols == 4
