import pytest

from lc_keys import (
    LC_KT_CHAR,
    LC_KT_KEYSYM,
    LC_KEY_BTAB,
    LC_KEY_DELETE,
    LC_KEY_END,
    LC_KEY_F1,
    LC_KEY_F2,
    LC_KEY_F3,
    LC_KEY_F4,
    LC_KEY_F5,
    LC_KEY_F6,
    LC_KEY_F7,
    LC_KEY_F8,
    LC_KEY_F9,
    LC_KEY_F10,
    LC_KEY_F11,
    LC_KEY_F12,
    LC_KEY_HOME,
    LC_MOD_ALT,
    LC_KEY_SHIFT_END,
    LCKey,
    LCKeyParser,
)
from lc_screen import lc


class FakeInput:
    def __init__(self, data: bytes, pending=None):
        self.buf = list(data)
        self.pending = list(pending) if pending is not None else None
        self.pending_calls = []

    def read_byte(self):
        if not self.buf:
            return None
        return self.buf.pop(0)

    def unread_byte(self, ch: int) -> None:
        self.buf.insert(0, ch & 0xFF)

    def input_pending(self, timeout_ms: int) -> bool:
        self.pending_calls.append(timeout_ms)
        if self.pending is not None and self.pending:
            return self.pending.pop(0)
        return bool(self.buf)


@pytest.fixture(autouse=True)
def parser_env(monkeypatch):
    old_meta = lc.meta_on
    old_nodelay = lc.nodelay_on
    old_escdelay = lc.escdelay_ms

    monkeypatch.setattr("lc_keys.lc_check_resize", lambda: 0)
    lc.meta_on = True
    lc.nodelay_on = False
    lc.escdelay_ms = 37
    yield
    lc.meta_on = old_meta
    lc.nodelay_on = old_nodelay
    lc.escdelay_ms = old_escdelay


def test_bare_escape_when_no_followup_arrives_before_timeout():
    src = FakeInput(b"\x1b", pending=[False])
    parser = LCKeyParser(src)
    out = LCKey()

    assert parser.readkey(out) == 0
    assert out.type == LC_KT_CHAR
    assert out.mods == 0
    assert out.rune == 0x1B
    assert src.pending_calls == [37]


def test_alt_modified_ascii_character_from_esc_prefix():
    src = FakeInput(b"\x1bx", pending=[True])
    parser = LCKeyParser(src)
    out = LCKey()

    assert parser.readkey(out) == 0
    assert out.type == LC_KT_CHAR
    assert out.mods == LC_MOD_ALT
    assert out.rune == ord("x")


def test_meta_disabled_keeps_bare_escape_and_unreads_followup():
    lc.meta_on = False
    src = FakeInput(b"\x1bx", pending=[True])
    parser = LCKeyParser(src)
    first = LCKey()
    second = LCKey()

    assert parser.readkey(first) == 0
    assert first.type == LC_KT_CHAR
    assert first.mods == 0
    assert first.rune == 0x1B

    assert parser.readkey(second) == 0
    assert second.type == LC_KT_CHAR
    assert second.mods == 0
    assert second.rune == ord("x")


@pytest.mark.parametrize(
    "seq, expected",
    [
        (b"\x1bOP", LC_KEY_F1),
        (b"\x1bOQ", LC_KEY_F2),
        (b"\x1bOR", LC_KEY_F3),
        (b"\x1bOS", LC_KEY_F4),
        (b"\x1b[15~", LC_KEY_F5),
        (b"\x1b[17~", LC_KEY_F6),
        (b"\x1b[18~", LC_KEY_F7),
        (b"\x1b[19~", LC_KEY_F8),
        (b"\x1b[20~", LC_KEY_F9),
        (b"\x1b[21~", LC_KEY_F10),
        (b"\x1b[23~", LC_KEY_F11),
        (b"\x1b[24~", LC_KEY_F12),
        (b"\x1b[1~", LC_KEY_HOME),
        (b"\x1b[4~", LC_KEY_SHIFT_END),
        (b"\x1b[3~", LC_KEY_DELETE),
        (b"\x1b[Z", LC_KEY_BTAB),
    ],
)
def test_common_terminal_vectors(seq, expected):
    src = FakeInput(seq, pending=[True])
    parser = LCKeyParser(src)
    out = LCKey()

    assert parser.readkey(out) == 0
    assert out.type == LC_KT_KEYSYM
    assert out.keysym == expected
