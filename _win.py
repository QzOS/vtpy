"""Windows terminal backend.

Requires Windows 10 1607+ (or Windows Terminal) for VT/ANSI support.
"""

import ctypes
import ctypes.wintypes
import msvcrt
import os
import threading
import time
from typing import Optional

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

_kernel32 = ctypes.windll.kernel32

# INPUT_RECORD.EventType values
_KEY_EVENT = 0x0001
_WINDOW_BUFFER_SIZE_EVENT = 0x0004


def _handle(std: int):
    return _kernel32.GetStdHandle(std)


_resize_lock = threading.Lock()


class _COORD(ctypes.Structure):
    _fields_ = [
        ("X", ctypes.wintypes.SHORT),
        ("Y", ctypes.wintypes.SHORT),
    ]


class _WINDOW_BUFFER_SIZE_RECORD(ctypes.Structure):
    _fields_ = [
        ("dwSize", _COORD),
    ]


class _INPUT_RECORD_EVENT(ctypes.Union):
    _fields_ = [
        ("WindowBufferSizeEvent", _WINDOW_BUFFER_SIZE_RECORD),
        ("_padding", ctypes.c_byte * 16),
    ]


class _INPUT_RECORD(ctypes.Structure):
    _anonymous_ = ("Event",)
    _fields_ = [
        ("EventType", ctypes.wintypes.WORD),
        ("Event", _INPUT_RECORD_EVENT),
    ]


def init(state) -> int:
    """Initialize terminal for Windows console with VT processing."""

    state.in_fd = 0
    state.out_fd = 1
    state.term.out_fd = state.out_fd

    hin = _handle(_STD_INPUT_HANDLE)
    hout = _handle(_STD_OUTPUT_HANDLE)
    # Check for invalid handles: None, 0, or -1 (INVALID_HANDLE_VALUE)
    # 0 is rejected because GetStdHandle can return 0 for detached processes
    if hin in (None, 0, -1) or hout in (None, 0, -1):
        return -1

    state._last_size = (24, 80)
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
    state._last_size = (24, 80)
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

    _drain_resize_events(state)

    # Use msvcrt for console input on Windows.
    while True:
        try:
            if msvcrt.kbhit():
                ch = msvcrt.getch()
                if len(ch) >= 1:
                    return ch[0]
                # Empty getch response should not happen; retry.
            else:
                _drain_resize_events(state)
                # No input available; yield to other threads.
                time.sleep(0.001)
        except (OSError, ValueError):
            return None


def unread_byte(state, ch: int) -> None:
    """Push back a byte to input."""
    state.pushback_byte = ch & 0xFF


def input_pending(state, timeout_ms: int) -> bool:
    """Check if input is available within timeout."""
    if state.pushback_byte is not None:
        return True

    _drain_resize_events(state)

    if timeout_ms < 0:
        try:
            while True:
                if msvcrt.kbhit():
                    return True
                _drain_resize_events(state)
                time.sleep(0.01)
        except (OSError, ValueError):
            return False
    elif timeout_ms == 0:
        try:
            return msvcrt.kbhit()
        except (OSError, ValueError):
            return False
    else:
        deadline = time.monotonic() + (timeout_ms / 1000.0)
        try:
            while time.monotonic() < deadline:
                if msvcrt.kbhit():
                    return True
                _drain_resize_events(state)
                time.sleep(0.001)
        except (OSError, ValueError):
            return False
        return False


def poll_resize(state) -> bool:
    """Check if a resize event occurred."""
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


def _drain_resize_events(state) -> None:
    """Consume pending resize events from the console input buffer.

    This is opportunistic, not asynchronous: resize is noticed only when
    the caller enters an input path.
    """
    if state.orig_term is None:
        return

    hin = state.orig_term[2]
    records = (_INPUT_RECORD * 32)()
    count = ctypes.wintypes.DWORD()

    while True:
        try:
            if not _kernel32.PeekConsoleInputW(hin, records, len(records), ctypes.byref(count)):
                return
            if count.value == 0:
                return

            consumed = 0
            saw_resize = False

            for i in range(count.value):
                rec = records[i]
                if rec.EventType == _WINDOW_BUFFER_SIZE_EVENT:
                    saw_resize = True
                    consumed += 1
                    continue
                break

            if consumed == 0:
                return

            if not _kernel32.ReadConsoleInputW(hin, records, consumed, ctypes.byref(count)):
                return

            if saw_resize:
                current_size = get_size(state)
                if current_size[0] > 0 and current_size[1] > 0:
                    if current_size != state._last_size:
                        state._last_size = current_size
                        with _resize_lock:
                            state.resize_pending = True
        except (OSError, ValueError):
            return
