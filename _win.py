"""Windows terminal backend.

Requires Windows 10 1607+ (or Windows Terminal) for VT/ANSI support.

Contract notes:
    - This backend is byte-oriented.
    - read_byte() returns integers in range 0..255, never Unicode code points.
    - Special keys are translated to VT-style byte sequences where practical.
    - input_pending() reports keyboard byte availability only; a resize alone
      is observed through poll_resize().
    - For now, direct Unicode input above Latin-1 is intentionally dropped
      rather than mixing UTF-16/UTF-8 semantics into the current parser model.
      This keeps backend behavior aligned with the library's byte-stream core,
      at the cost of incomplete non-Latin-1 text input on Windows.
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
_LEFT_CTRL_PRESSED = 0x0008
_SHIFT_PRESSED = 0x0010

_RIGHT_CTRL_PRESSED = 0x0004
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

_kernel32.GetNumberOfConsoleInputEvents.argtypes = [
    ctypes.wintypes.HANDLE,
    ctypes.POINTER(ctypes.wintypes.DWORD),
]
_kernel32.GetNumberOfConsoleInputEvents.restype = ctypes.wintypes.BOOL


_MAX_EVENT_BATCH = 128
_MAX_DRAIN_BATCHES = 8
_DRAIN_ON_INPUT_READY = 2
_DRAIN_ON_RESIZE_READY = 2


def _handle(std: int):
    return _kernel32.GetStdHandle(std)


def _valid_handle(handle) -> bool:
    return handle not in (None, _NULL_HANDLE_VALUE, _INVALID_HANDLE_VALUE)


def _get_terminal_size_fd(fd: int):
    try:
        sz = os.get_terminal_size(fd)
        if sz.lines > 0 and sz.columns > 0:
            return sz.lines, sz.columns
    except (OSError, ValueError, TypeError):
        pass
    return None


def _normalize_input_mode(mode: int) -> int:
    """Keep backend-required input flags enabled."""
    mode |= _ENABLE_WINDOW_INPUT
    mode |= _ENABLE_VIRTUAL_TERMINAL_INPUT
    return mode


def _set_console_mode(handle, mode: int) -> bool:
    if not _valid_handle(handle):
        return False
    try:
        return bool(_kernel32.SetConsoleMode(handle, int(mode)))
    except (OSError, ValueError, TypeError):
        return False


def _get_console_mode(handle):
    if not _valid_handle(handle):
        return None

    mode = ctypes.wintypes.DWORD()
    try:
        if not _kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return None
    except (OSError, ValueError, TypeError):
        return None
    return int(mode.value)


def _get_console_input_event_count(handle) -> int:
    count = ctypes.wintypes.DWORD()
    try:
        if not _kernel32.GetNumberOfConsoleInputEvents(handle, ctypes.byref(count)):
            return -1
    except (OSError, ValueError, TypeError):
        return -1
    return int(count.value)


def _update_input_mode(state, clear_mask: int = 0, set_mask: int = 0) -> int:
    if state.cur_term is None:
        return -1

    prev_cur_term = list(state.cur_term)
    new_in_mode = (int(prev_cur_term[0]) & ~clear_mask) | set_mask

    state.cur_term[0] = new_in_mode

    rc = apply_term(state)
    if rc < 0:
        state.cur_term = prev_cur_term
        return -1

    return 0


def _reset_state_fields(state) -> None:
    state.orig_term = None
    state.cur_term = None
    state._win_hin = None
    state._win_hout = None
    state._last_size = (24, 80)
    state._input_bytes = deque()
    state._resize_lock = threading.Lock()
    state._input_lock = threading.Lock()
    state.in_fd = 0
    state.out_fd = 1
    state.pushback_byte = None

    with state._resize_lock:
        state.resize_pending = False

    with state._input_lock:
        state._input_bytes.clear()


def init(state) -> int:
    """Initialize terminal for Windows console with VT processing."""
    _reset_state_fields(state)

    state.in_fd = 0
    state.out_fd = 1

    try:
        state.term.out_fd = state.out_fd
    except AttributeError:
        pass

    # These are internal-only fields owned by this backend.
    state._win_hin = None
    state._win_hout = None

    hin = _handle(_STD_INPUT_HANDLE)
    hout = _handle(_STD_OUTPUT_HANDLE)
    # Check for invalid handles: None, NULL, or INVALID_HANDLE_VALUE.
    if not _valid_handle(hin) or not _valid_handle(hout):
        return -1

    # Save original console modes
    orig_in_mode = ctypes.wintypes.DWORD()
    if not _kernel32.GetConsoleMode(hin, ctypes.byref(orig_in_mode)):
        _reset_state_fields(state)
        return -1

    orig_out_mode = ctypes.wintypes.DWORD()
    if not _kernel32.GetConsoleMode(hout, ctypes.byref(orig_out_mode)):
        _reset_state_fields(state)
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
        _reset_state_fields(state)
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
        _reset_state_fields(state)
        return -1

    # Keep current terminal state aligned with what was actually applied.
    #
    # orig_term remains the restore target captured at startup.
    # cur_term must reflect the live console modes so later raw/cbreak/echo
    # transitions are computed from the active baseline rather than the
    # original console state. Otherwise apply_term() can accidentally roll
    # VT processing or input mode changes back out.
    state.cur_term[0] = new_in_mode
    state.cur_term[1] = new_out_mode

    state.resize_pending = False
    state._last_size = get_size(state)
    return 0


def end(state) -> int:
    """Restore terminal to original state."""

    orig_term = getattr(state, "orig_term", None)
    if orig_term is not None:
        orig_in_mode, orig_out_mode, hin, hout = orig_term
        try:
            if _valid_handle(hin):
                _kernel32.SetConsoleMode(hin, orig_in_mode)
            if _valid_handle(hout):
                _kernel32.SetConsoleMode(hout, orig_out_mode)
        except (OSError, ValueError):
            pass

    _reset_state_fields(state)
    return 0


def get_size(state) -> tuple[int, int]:
    """Get terminal size (rows, cols)."""
    out_fd = getattr(state, "out_fd", None)
    in_fd = getattr(state, "in_fd", None)

    if out_fd is not None:
        size = _get_terminal_size_fd(out_fd)
        if size is not None:
            return size

    if in_fd is not None and in_fd != out_fd:
        size = _get_terminal_size_fd(in_fd)
        if size is not None:
            return size

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

    with state._resize_lock:
        if state.resize_pending:
            # Mirror POSIX behavior: once a resize is pending, do not block
            # here waiting for keyboard input. Let the caller observe it via
            # poll_resize().
            return False

    rc = _wait_console_input(state, 0)
    if rc == _WAIT_TIMEOUT:
        if timeout_ms == 0:
            return False
        rc = _wait_console_input(state, timeout_ms)

    if rc == _WAIT_TIMEOUT:
        return False
    if rc != _WAIT_OBJECT_0:
        return False

    if _read_console_events(state, block=False) < 0:
        return False

    with state._resize_lock:
        if state.resize_pending:
            return False

    return _peek_input_byte(state)


def poll_resize(state) -> bool:
    """Check if a resize event occurred."""
    with state._resize_lock:
        if state.resize_pending:
            return True

    rc = _wait_console_input(state, 0)
    if rc == _WAIT_TIMEOUT:
        return False
    if rc != _WAIT_OBJECT_0:
        return False

    if _read_console_events(state, block=False) < 0:
        return False

    with state._resize_lock:
        return bool(state.resize_pending)


def clear_resize(state) -> None:
    """Clear the resize pending flag."""
    with state._resize_lock:
        state.resize_pending = False


def apply_term(state) -> int:
    """Apply terminal settings.

    Apply current console modes stored in state.cur_term.
    """
    cur_term = getattr(state, "cur_term", None)
    hin = getattr(state, "_win_hin", None)
    hout = getattr(state, "_win_hout", None)

    if cur_term is None or len(cur_term) < 2:
        return -1
    if not _valid_handle(hin) or not _valid_handle(hout):
        return -1

    try:
        desired_in_mode = int(cur_term[0])
        desired_out_mode = int(cur_term[1])
    except (TypeError, ValueError):
        return -1

    prev_in_mode = _get_console_mode(hin)
    prev_out_mode = _get_console_mode(hout)
    if prev_in_mode is None or prev_out_mode is None:
        return -1

    new_in_mode = _normalize_input_mode(desired_in_mode)
    new_out_mode = desired_out_mode

    if not _set_console_mode(hout, new_out_mode):
        return -1

    if not _set_console_mode(hin, new_in_mode):
        try:
            _set_console_mode(hout, prev_out_mode)
            _set_console_mode(hin, prev_in_mode)
        except (OSError, ValueError, TypeError):
            pass
        return -1

    state.cur_term[0] = desired_in_mode
    state.cur_term[1] = desired_out_mode
    return 0


def raw(state) -> int:
    return _update_input_mode(
        state,
        clear_mask=(_ENABLE_LINE_INPUT | _ENABLE_ECHO_INPUT | _ENABLE_PROCESSED_INPUT),
        set_mask=0,
    )


def noraw(state) -> int:
    return _update_input_mode(
        state,
        clear_mask=0,
        set_mask=(_ENABLE_LINE_INPUT | _ENABLE_PROCESSED_INPUT),
    )


def cbreak(state) -> int:
    return _update_input_mode(
        state,
        clear_mask=_ENABLE_LINE_INPUT,
        set_mask=0,
    )


def nocbreak(state) -> int:
    return _update_input_mode(
        state,
        clear_mask=0,
        set_mask=_ENABLE_LINE_INPUT,
    )


def echo(state) -> int:
    return _update_input_mode(state, clear_mask=0, set_mask=_ENABLE_ECHO_INPUT)


def noecho(state) -> int:
    return _update_input_mode(state, clear_mask=_ENABLE_ECHO_INPUT, set_mask=0)


def _peek_input_byte(state) -> bool:
    with state._input_lock:
        return bool(getattr(state, "_input_bytes", None))


def _pop_input_byte(state):
    with state._input_lock:
        buf = getattr(state, "_input_bytes", None)
        if buf:
            return buf.popleft()
    return None


def _push_input_bytes(state, data: bytes) -> None:
    if not data:
        return
    with state._input_lock:
        buf = getattr(state, "_input_bytes", None)
        if buf is not None:
            buf.extend(data)


def _wait_console_input(state, timeout_ms: int) -> int:
    hin = getattr(state, "_win_hin", None)
    if not _valid_handle(hin):
        return -1

    timeout = _INFINITE if timeout_ms < 0 else max(0, int(timeout_ms))
    try:
        return _kernel32.WaitForSingleObject(hin, timeout)
    except (OSError, ValueError):
        return -1


def _read_console_events(state, block: bool) -> int:
    hin = getattr(state, "_win_hin", None)
    if not _valid_handle(hin):
        return -1

    batches = 0
    while True:
        try:
            if block:
                records = (_INPUT_RECORD * _MAX_EVENT_BATCH)()
                count = ctypes.wintypes.DWORD()
                ok = _kernel32.ReadConsoleInputW(
                    hin, records, len(records), ctypes.byref(count)
                )
                if not ok:
                    return -1
            else:
                queued = _get_console_input_event_count(hin)
                if queued < 0:
                    return -1
                if queued == 0:
                    return 0

                nread = min(queued, _MAX_EVENT_BATCH)
                records = (_INPUT_RECORD * nread)()
                count = ctypes.wintypes.DWORD()
                ok = _kernel32.ReadConsoleInputW(
                    hin, records, nread, ctypes.byref(count)
                )
                if not ok:
                    return -1

            for i in range(count.value):
                _handle_console_record(state, records[i])

            have_input = _peek_input_byte(state)
            with state._resize_lock:
                resize_pending = bool(state.resize_pending)

            if block:
                if have_input or resize_pending:
                    return 1
                continue

            if have_input:
                batches += 1
                if batches >= _DRAIN_ON_INPUT_READY:
                    return 1
            elif resize_pending:
                batches += 1
                if batches >= _DRAIN_ON_RESIZE_READY:
                    return 1
            else:
                batches += 1

            if batches >= _MAX_DRAIN_BATCHES:
                return 1

            queued = _get_console_input_event_count(hin)
            if queued <= 0:
                return 1
        except (OSError, ValueError):
            return -1


def _handle_console_record(state, rec) -> None:
    if rec.EventType == _WINDOW_BUFFER_SIZE_EVENT:
        current_size = get_size(state)
        if current_size[0] > 0 and current_size[1] > 0:
            if current_size != getattr(state, "_last_size", None):
                state._last_size = current_size
                with state._resize_lock:
                    state.resize_pending = True
        return

    if rec.EventType != _KEY_EVENT:
        return

    data = _translate_key_event(rec.KeyEvent)
    if data:
        _push_input_bytes(state, data)


def _with_alt_prefix(data: bytes, alt: bool) -> bytes:
    if alt and data:
        return b"\x1b" + data
    return data


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
        return _with_alt_prefix(_SPECIAL_KEY_BYTES[vk], alt) * repeat

    if vk == _VK_RETURN:
        return _with_alt_prefix(b"\r", alt) * repeat
    if vk == _VK_TAB:
        return _with_alt_prefix(b"\t", alt) * repeat
    if vk == _VK_BACK:
        return _with_alt_prefix(b"\x08", alt) * repeat
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
            # Current backend contract is byte-oriented.
            # We only forward single-byte code points directly and drop higher
            # Unicode code points rather than inventing a UTF-16/UTF-8 mix.
            # This keeps Windows input semantics aligned with the library's
            # current byte-stream parser model, at the cost of incomplete
            # Unicode input.
            data = b""

    return _with_alt_prefix(data, alt) * repeat
