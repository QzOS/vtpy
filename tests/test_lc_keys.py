from lc_keys import (
    LCKey,
    LCKeyParser,
    LC_MOD_ALT,
    LC_KEY_UP,
    LC_KEY_F5,
    LC_KEY_DELETE,
    LC_KT_CHAR,
    LC_KT_KEYSYM,
)
from lc_screen import lc


class FakeInput:
    def __init__(self, data: bytes, pending=None) -> None:
        self.buf = bytearray(data)
        self.pushback = None
        self.pending = list(pending) if pending is not None else None
        self.pending_calls = []

    def unread_byte(self, ch: int) -> None:
        self.pushback = ch & 0xFF

    def read_byte(self):
        if self.pushback is not None:
            ch = self.pushback
            self.pushback = None
            return ch
        if not self.buf:
            return None
        ch = self.buf[0]
        del self.buf[0]
        return ch

    def input_pending(self, timeout_ms: int) -> bool:
        self.pending_calls.append(timeout_ms)
        if self.pending is not None and self.pending:
            return self.pending.pop(0)
        return self.pushback is not None or bool(self.buf)


def _set_parser_state(*, meta_on: bool = True, nodelay_on: bool = False, escdelay_ms: int = 35):
    old_state = (lc.meta_on, lc.nodelay_on, lc.escdelay_ms)
    lc.meta_on = meta_on
    lc.nodelay_on = nodelay_on
    lc.escdelay_ms = escdelay_ms
    return old_state


def _restore_parser_state(old_state) -> None:
    lc.meta_on, lc.nodelay_on, lc.escdelay_ms = old_state


def test_plain_ascii():
    src = FakeInput(b"a")
    parser = LCKeyParser(src)
    key = LCKey()
    assert parser.readkey(key) == 0
    assert key.type == LC_KT_CHAR
    assert key.rune == ord("a")


def test_utf8_char():
    src = FakeInput("å".encode("utf-8"))
    parser = LCKeyParser(src)
    key = LCKey()
    assert parser.readkey(key) == 0
    assert key.type == LC_KT_CHAR
    assert key.rune == ord("å")


def test_csi_up():
    src = FakeInput(b"\x1b[A")
    parser = LCKeyParser(src)
    key = LCKey()
    assert parser.readkey(key) == 0
    assert key.type == LC_KT_KEYSYM
    assert key.keysym == LC_KEY_UP


def test_csi_delete():
    src = FakeInput(b"\x1b[3~")
    parser = LCKeyParser(src)
    key = LCKey()
    assert parser.readkey(key) == 0
    assert key.type == LC_KT_KEYSYM
    assert key.keysym == LC_KEY_DELETE


def test_csi_f5():
    src = FakeInput(b"\x1b[15~")
    parser = LCKeyParser(src)
    key = LCKey()
    assert parser.readkey(key) == 0
    assert key.type == LC_KT_KEYSYM
    assert key.keysym == LC_KEY_F5


def test_alt_modified_ascii_from_esc_prefix():
    old_state = _set_parser_state(meta_on=True, nodelay_on=False, escdelay_ms=40)
    try:
        src = FakeInput(b"\x1bx", pending=[True])
        parser = LCKeyParser(src)
        key = LCKey()

        assert parser.readkey(key) == 0
        assert key.type == LC_KT_CHAR
        assert key.mods == LC_MOD_ALT
        assert key.rune == ord("x")
    finally:
        _restore_parser_state(old_state)


def test_alt_modified_utf8_from_esc_prefix():
    old_state = _set_parser_state(meta_on=True, nodelay_on=False, escdelay_ms=40)
    try:
        src = FakeInput(b"\x1b" + "å".encode("utf-8"), pending=[True])
        parser = LCKeyParser(src)
        key = LCKey()

        assert parser.readkey(key) == 0
        assert key.type == LC_KT_CHAR
        assert key.mods == LC_MOD_ALT
        assert key.rune == ord("å")
    finally:
        _restore_parser_state(old_state)


def test_esc_timeout_returns_bare_escape():
    old_state = _set_parser_state(meta_on=True, nodelay_on=False, escdelay_ms=33)
    try:
        src = FakeInput(b"\x1b", pending=[False])
        parser = LCKeyParser(src)
        key = LCKey()

        assert parser.readkey(key) == 0
        assert key.type == LC_KT_CHAR
        assert key.mods == 0
        assert key.rune == 0x1B
        assert src.pending_calls == [33]
    finally:
        _restore_parser_state(old_state)


def test_escdelay_negative_uses_immediate_followup_read():
    old_state = _set_parser_state(meta_on=True, nodelay_on=False, escdelay_ms=-1)
    try:
        src = FakeInput(b"\x1bx")
        parser = LCKeyParser(src)
        key = LCKey()

        assert parser.readkey(key) == 0
        assert key.type == LC_KT_CHAR
        assert key.mods == LC_MOD_ALT
        assert key.rune == ord("x")
        assert src.pending_calls == []
    finally:
        _restore_parser_state(old_state)


def test_nodelay_with_negative_escdelay_polls_with_zero_timeout():
    old_state = _set_parser_state(meta_on=True, nodelay_on=True, escdelay_ms=-1)
    try:
        src = FakeInput(b"\x1b", pending=[True, False])
        parser = LCKeyParser(src)
        key = LCKey()

        assert parser.readkey(key) == 0
        assert key.type == LC_KT_CHAR
        assert key.mods == 0
        assert key.rune == 0x1B
        assert src.pending_calls == [0, 0]
    finally:
        _restore_parser_state(old_state)
