from lc_keys import (
    LCKey,
    LCKeyParser,
    LC_KEY_UP,
    LC_KEY_F5,
    LC_KEY_DELETE,
    LC_KT_CHAR,
    LC_KT_KEYSYM,
)


class FakeInput:
    def __init__(self, data: bytes) -> None:
        self.buf = bytearray(data)
        self.pushback = None

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
        return self.pushback is not None or bool(self.buf)


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
