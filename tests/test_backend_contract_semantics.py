from types import SimpleNamespace

import lc_platform
from lc_platform import backend


class DummyState:
    def __init__(self):
        self.pushback_byte = None
        self.resize_pending = False
        self.in_fd = 0
        self.out_fd = 1
        self.orig_term = None
        self.cur_term = None


def test_unread_byte_roundtrip_contract():
    state = DummyState()
    backend.unread_byte(state, 0x41)
    assert state.pushback_byte == 0x41


def test_clear_resize_contract():
    state = DummyState()
    state.resize_pending = True
    backend.clear_resize(state)
    assert state.resize_pending is False


def test_get_size_contract_shape():
    state = DummyState()
    size = backend.get_size(state)
    assert isinstance(size, tuple)
    assert len(size) == 2
    assert isinstance(size[0], int)
    assert isinstance(size[1], int)


def test_read_byte_returns_byte_or_none_when_pushback_is_set():
    state = DummyState()
    backend.unread_byte(state, 0x1FF)

    ch = backend.read_byte(state)

    assert isinstance(ch, int)
    assert 0 <= ch <= 255
    assert ch == 0xFF


def test_input_pending_resize_alone_not_true():
    state = DummyState()
    state.resize_pending = True

    pending = backend.input_pending(state, 0)

    assert isinstance(pending, bool)
    assert pending is False


def test_input_pending_true_when_pushback_exists_even_with_resize():
    state = DummyState()
    state.resize_pending = True
    backend.unread_byte(state, 0x42)

    pending = backend.input_pending(state, 0)

    assert pending is True


def test_windows_source_keeps_byte_oriented_contract_and_no_input_record_leak():
    """Validate Windows backend contract text + dispatch shape without importing _win."""
    # This check is intentionally source-based so it runs on non-Windows CI.
    with open("_win.py", "r", encoding="utf-8") as f:
        src = f.read()

    assert "read_byte() returns integers in range 0..255" in src
    assert "input_pending() reports keyboard byte availability only" in src
    assert "if rec.EventType != _KEY_EVENT:" in src
    assert "_translate_key_event(rec.KeyEvent)" in src


def test_windows_translate_key_event_returns_bytes_when_module_available():
    """On Windows, ensure translation never emits non-byte payloads."""
    if lc_platform.sys.platform != "win32":
        return

    import _win

    key = SimpleNamespace(
        bKeyDown=True,
        wRepeatCount=1,
        wVirtualKeyCode=0,
        dwControlKeyState=0,
        uChar=SimpleNamespace(UnicodeChar="A"),
    )

    data = _win._translate_key_event(key)

    assert isinstance(data, bytes)
