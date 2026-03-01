"""Windows terminal backend.

Requires Windows 10 1607+ (or Windows Terminal) for VT/ANSI support.
"""

import ctypes
import ctypes.wintypes
import os
import threading
from collections import deque

# ── Win32 constants ─────────────────────────────────────────────────
_STD_INPUT_HANDLE = -10
_STD_OUTPUT_HANDLE = -11

_ENABLE_WINDOW_INPUT = 0x0008
_ENABLE_PROCESSED_INPUT = 0x0001
_ENABLE_LINE_INPUT = 0x0002
_ENABLE_ECHO_INPUT = 0x0004
_ENABLE_VIRTUAL_TERMINAL_INPUT = 0x0200

_ENABLE_PROCESSED_OUTPUT = 0x0001
_ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004

_WAIT_OBJECT_0 = 0x00000000
_WAIT_TIMEOUT = 0x00000102
_INFINITE = 0xFFFFFFFF

_kernel32 = ctypes.windll.kernel32
_INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
_NULL_HANDLE_VALUE = ctypes.c_void_p(0).value

# INPUT_RECORD.EventType values
_KEY_EVENT = 0x0001
_WINDOW_BUFFER_SIZE_EVENT = 0x0004
_MOUSE_EVENT = 0x0002
_MENU_EVENT = 0x0008
_FOCUS_EVENT = 0x0010

# Control key state flags
_RIGHT_ALT_PRESSED = 0x0001
_LEFT_ALT_PRESSED = 0x0002
_RIGHT_CTRL_PRESSED = 0x0004
_LEFT_CTRL_PRESSED = 0x0008
_SHIFT_PRESSED = 0x0010

_resize_lock = threading.Lock()
_input_lock = threading.Lock()


_VK_BACK = 0x08
_VK_TAB = 0x09
_VK_RETURN = 0x0D
_VK_ESCAPE = 0x1B
_VK_PRIOR = 0x21
_VK_NEXT = 0x22
_VK_END = 0x23
_VK_HOME = 0x24
_VK_LEFT = 0x25
_VK_UP = 0x26
_VK_RIGHT = 0x27
_VK_DOWN = 0x28
_VK_INSERT = 0x2D
_VK_DELETE = 0x2E

_SPECIAL_KEY_BYTES = {
    _VK_UP: b"\x1b[A",
    _VK_DOWN: b"\x1b[B",
    _VK_RIGHT: b"\x1b[C",
    _VK_LEFT: b"\x1b[D",
    _VK_HOME: b"\x1b[H",
    _VK_END: b"\x1b[F",
    _VK_DELETE: b"\x1b[3~",
    _VK_INSERT: b"\x1b[2~",
    _VK_PRIOR: b"\x1b[5~",
    _VK_NEXT: b"\x1b[6~",
}


class _COORD(ctypes.Structure):
    _fields_ = [
        ("X", ctypes.wintypes.SHORT),
        ("Y", ctypes.wintypes.SHORT),
    ]


class _WINDOW_BUFFER_SIZE_RECORD(ctypes.Structure):
    _fields_ = [
        ("dwSize", _COORD),
    ]


class _KEY_EVENT_RECORD_UNION(ctypes.Union):
    _fields_ = [
        ("UnicodeChar", ctypes.wintypes.WCHAR),
        ("AsciiChar", ctypes.c_char),
    ]


class _KEY_EVENT_RECORD(ctypes.Structure):
    _fields_ = [
        ("bKeyDown", ctypes.wintypes.BOOL),
        ("wRepeatCount", ctypes.wintypes.WORD),
        ("wVirtualKeyCode", ctypes.wintypes.WORD),
        ("wVirtualScanCode", ctypes.wintypes.WORD),
        ("uChar", _KEY_EVENT_RECORD_UNION),
        ("dwControlKeyState", ctypes.wintypes.DWORD),
    ]


class _INPUT_RECORD_EVENT(ctypes.Union):
    _fields_ = [
        ("KeyEvent", _KEY_EVENT_RECORD),
        ("WindowBufferSizeEvent", _WINDOW_BUFFER_SIZE_RECORD),
        ("_padding", ctypes.c_byte * 16),
    ]


class _INPUT_RECORD(ctypes.Structure):
    _anonymous_ = ("Event",)
    _fields_ = [
        ("EventType", ctypes.wintypes.WORD),
        ("Event", _INPUT_RECORD_EVENT),
    ]


_kernel32.GetStdHandle.argtypes = [ctypes.wintypes.DWORD]
_kernel32.GetStdHandle.restype = ctypes.wintypes.HANDLE

_kernel32.GetConsoleMode.argtypes = [
    ctypes.wintypes.HANDLE,
    ctypes.POINTER(ctypes.wintypes.DWORD),
]
_kernel32.GetConsoleMode.restype = ctypes.wintypes.BOOL

_kernel32.SetConsoleMode.argtypes = [
    ctypes.wintypes.HANDLE,
    ctypes.wintypes.DWORD,
]
_kernel32.SetConsoleMode.restype = ctypes.wintypes.BOOL

_kernel32.PeekConsoleInputW.argtypes = [
    ctypes.wintypes.HANDLE,
    ctypes.POINTER(_INPUT_RECORD),
    ctypes.wintypes.DWORD,
    ctypes.POINTER(ctypes.wintypes.DWORD),
]
_kernel32.PeekConsoleInputW.restype = ctypes.wintypes.BOOL

_kernel32.ReadConsoleInputW.argtypes = [
    ctypes.wintypes.HANDLE,
    ctypes.POINTER(_INPUT_RECORD),
    ctypes.wintypes.DWORD,
    ctypes.POINTER(ctypes.wintypes.DWORD),
]
_kernel32.ReadConsoleInputW.restype = ctypes.wintypes.BOOL

_kernel32.WaitForSingleObject.argtypes = [
    ctypes.wintypes.HANDLE,
    ctypes.wintypes.DWORD,
]
_kernel32.WaitForSingleObject.restype = ctypes.wintypes.DWORD


def _handle(std: int):
    return _kernel32.GetStdHandle(std)


def init(state) -> int:
    """Initialize terminal for Windows console with VT processing."""

    state.in_fd = 0
    state.out_fd = 1
    state.term.out_fd = state.out_fd
    state._input_bytes = deque()
    state._last_size = (24, 80)

    # These are internal-only fields owned by this backend.
    state._win_hin = None
    state._win_hout = None

    hin = _handle(_STD_INPUT_HANDLE)
    hout = _handle(_STD_OUTPUT_HANDLE)
    # Check for invalid handles: None, NULL, or INVALID_HANDLE_VALUE.
    # 0 is rejected because GetStdHandle can return 0 for detached processes
    if hin in (None, _NULL_HANDLE_VALUE, _INVALID_HANDLE_VALUE) or hout in (None, _NULL_HANDLE_VALUE, _INVALID_HANDLE_VALUE):
        return -1

    # Save original console modes
    orig_in_mode = ctypes.wintypes.DWORD()
    if not _kernel32.GetConsoleMode(hin, ctypes.byref(orig_in_mode)):
        return -1

    orig_out_mode = ctypes.wintypes.DWORD()
    if not _kernel32.GetConsoleMode(hout, ctypes.byref(orig_out_mode)):
        return -1

    # Store original modes in state for restoration
    state.orig_term = (orig_in_mode.value, orig_out_mode.value, hin, hout)
    state.cur_term = list(state.orig_term)
    state._win_hin = hin
    state._win_hout = hout

    # Enable VT processing on output so ANSI escapes work
    new_out_mode = (
        orig_out_mode.value
        | _ENABLE_PROCESSED_OUTPUT
        | _ENABLE_VIRTUAL_TERMINAL_PROCESSING
    )

    if not _kernel32.SetConsoleMode(hout, new_out_mode):
        return -1

    # cbreak-like: disable line input and echo, enable VT input
    new_in_mode = (
        (orig_in_mode.value & ~_ENABLE_LINE_INPUT & ~_ENABLE_ECHO_INPUT)
        | _ENABLE_WINDOW_INPUT
        | _ENABLE_VIRTUAL_TERMINAL_INPUT
    )

    if not _kernel32.SetConsoleMode(hin, new_in_mode):
        try:
            _kernel32.SetConsoleMode(hout, orig_out_mode.value)
        except (OSError, ValueError):
            pass
        state.orig_term = None
        state.cur_term = None
        state._win_hin = None
        state._win_hout = None
        return -1


    state.resize_pending = False
    state._last_size = get_size(state)
    return 0


def end(state) -> int:
    """Restore terminal to original state."""

    if state.orig_term is not None:
        orig_in_mode, orig_out_mode, hin, hout = state.orig_term
        try:
            _kernel32.SetConsoleMode(hin, orig_in_mode)
            _kernel32.SetConsoleMode(hout, orig_out_mode)
        except (OSError, ValueError):
            pass

    state.orig_term = None
    state.cur_term = None

    with _resize_lock:
        state.resize_pending = False

    with _input_lock:
        if hasattr(state, "_input_bytes"):
            state._input_bytes.clear()

    state._last_size = (24, 80)
    state._win_hin = None
    state._win_hout = None
    state.in_fd = 0
    state.out_fd = 1
    return 0


def get_size(state) -> tuple[int, int]:
    """Get terminal size (rows, cols)."""
    try:
        sz = os.get_terminal_size(state.out_fd)
        if sz.lines > 0 and sz.columns > 0:
            return sz.lines, sz.columns
    except (OSError, ValueError):
        pass
    return 24, 80


def read_byte(state):
    """Read a single byte from input."""
    if state.pushback_byte is not None:
        ch = state.pushback_byte
        state.pushback_byte = None
        return ch

    while True:
        ch = _pop_input_byte(state)
        if ch is not None:
            return ch

        rc = _wait_console_input(state, -1)
        if rc != _WAIT_OBJECT_0:
            return None

        if _read_console_events(state, block=True) < 0:
            return None


def unread_byte(state, ch: int) -> None:
    """Push back a byte to input."""
    state.pushback_byte = ch & 0xFF


def input_pending(state, timeout_ms: int) -> bool:
    """Check if input is available within timeout."""
    if state.pushback_byte is not None:
        return True

    if _peek_input_byte(state):
        return True

    if _read_console_events(state, block=False) < 0:
        return False
    if _peek_input_byte(state):
        return True

    rc = _wait_console_input(state, timeout_ms)
    if rc == _WAIT_TIMEOUT:
        return False
    if rc != _WAIT_OBJECT_0:
        return False

    if _read_console_events(state, block=False) < 0:
        return False
    return _peek_input_byte(state)


def poll_resize(state) -> bool:
    """Check if a resize event occurred."""
    if _read_console_events(state, block=False) < 0:
        return False
    with _resize_lock:
        return bool(state.resize_pending)


def clear_resize(state) -> None:
    """Clear the resize pending flag."""
    with _resize_lock:
        state.resize_pending = False


def apply_term(state) -> int:
    """Apply terminal settings.

    On Windows, terminal mode changes are applied immediately
    via SetConsoleMode, so this is effectively a no-op.
    Returns 0 to indicate success.
    """
    return 0


def _peek_input_byte(state) -> bool:
    with _input_lock:
        return bool(state._input_bytes)


def _pop_input_byte(state):
    with _input_lock:
        if state._input_bytes:
            return state._input_bytes.popleft()
    return None


def _push_input_bytes(state, data: bytes) -> None:
    if not data:
        return
    with _input_lock:
        state._input_bytes.extend(data)


def _wait_console_input(state, timeout_ms: int) -> int:
    hin = getattr(state, "_win_hin", None)
    if hin in (None, _NULL_HANDLE_VALUE, _INVALID_HANDLE_VALUE):
        return -1

    timeout = _INFINITE if timeout_ms < 0 else max(0, int(timeout_ms))
    try:
        return _kernel32.WaitForSingleObject(hin, timeout)
    except (OSError, ValueError):
        return -1


def _read_console_events(state, block: bool) -> int:
    hin = getattr(state, "_win_hin", None)
    if hin in (None, _NULL_HANDLE_VALUE, _INVALID_HANDLE_VALUE):
        return -1

    records = (_INPUT_RECORD * 32)()
    count = ctypes.wintypes.DWORD()

    while True:
        try:
            if block:
                ok = _kernel32.ReadConsoleInputW(
                    hin, records, len(records), ctypes.byref(count)
                )
                if not ok:
                    return -1
            else:
                ok = _kernel32.PeekConsoleInputW(
                    hin, records, len(records), ctypes.byref(count)
                )
                if not ok:
                    return -1
                if count.value == 0:
                    return 0
                ok = _kernel32.ReadConsoleInputW(
                    hin, records, count.value, ctypes.byref(count)
                )
                if not ok:
                    return -1

            for i in range(count.value):
                _handle_console_record(state, records[i])

            if block:
                with _resize_lock:
                    resize_pending = bool(state.resize_pending)
                if _peek_input_byte(state) or resize_pending:
                    return 1

            if not block:
                return 1
        except (OSError, ValueError):
            return -1


def _handle_console_record(state, rec) -> None:
    if rec.EventType == _WINDOW_BUFFER_SIZE_EVENT:
        current_size = get_size(state)
        if current_size[0] > 0 and current_size[1] > 0:
            if current_size != state._last_size:
                state._last_size = current_size
                with _resize_lock:
                    state.resize_pending = True
        return

    if rec.EventType != _KEY_EVENT:
        return

    data = _translate_key_event(rec.KeyEvent)
    if data:
        _push_input_bytes(state, data)


def _translate_key_event(key) -> bytes:
    if not key.bKeyDown:
        return b""

    if int(key.wRepeatCount) == 0:
        return b""

    repeat = int(key.wRepeatCount)
    if repeat <= 0:
        repeat = 1

    vk = int(key.wVirtualKeyCode)
    ctrl = bool(key.dwControlKeyState & (_LEFT_CTRL_PRESSED | _RIGHT_CTRL_PRESSED))
    alt = bool(key.dwControlKeyState & (_LEFT_ALT_PRESSED | _RIGHT_ALT_PRESSED))

    if vk in _SPECIAL_KEY_BYTES:
        data = _SPECIAL_KEY_BYTES[vk]
        if alt:
            data = b"\x1b" + data
        return data * repeat

    if vk == _VK_RETURN:
        data = b"\r"
        if alt:
            data = b"\x1b" + data
        return data * repeat
    if vk == _VK_TAB:
        data = b"\t"
        if alt:
            data = b"\x1b" + data
        return data * repeat
    if vk == _VK_BACK:
        data = b"\x08"
        if alt:
            data = b"\x1b" + data
        return data * repeat
    if vk == _VK_ESCAPE:
        return b"\x1b" * repeat

    ch = key.uChar.UnicodeChar
    if not ch:
        return b""

    code = ord(ch)

    if ctrl:
        # Ctrl+A..Ctrl+Z => 0x01..0x1A
        if 0x40 < code < 0x5B:
            data = bytes([code - 0x40])
        elif 0x60 < code < 0x7B:
            data = bytes([code - 0x60])
        elif code == 0x20:
            data = b"\x00"
        elif code == 0x5B:
            data = b"\x1b"
        elif code == 0x5C:
            data = b"\x1c"
        elif code == 0x5D:
            data = b"\x1d"
        elif code == 0x5E:
            data = b"\x1e"
        elif code == 0x5F:
            data = b"\x1f"
        else:
            data = b""
    else:
        if 0 <= code <= 0xFF:
            data = bytes([code])
        else:
            # Byte-oriented backend: drop non-Latin-1 code points.
            data = b""

    if alt and data:
        data = b"\x1b" + data

    return data * repeat
