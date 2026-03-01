"""Windows terminal backend.

Requires Windows 10 1607+ (or Windows Terminal) for VT/ANSI support.
"""

import ctypes
import ctypes.wintypes
import msvcrt
import os
import sys
import threading
import time
from typing import Optional

# ── Win32 constants ─────────────────────────────────────────────────
_STD_INPUT_HANDLE = -10
_STD_OUTPUT_HANDLE = -11

_ENABLE_PROCESSED_INPUT = 0x0001
_ENABLE_LINE_INPUT = 0x0002
_ENABLE_ECHO_INPUT = 0x0004
_ENABLE_VIRTUAL_TERMINAL_INPUT = 0x0200

_ENABLE_PROCESSED_OUTPUT = 0x0001
_ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004

_kernel32 = ctypes.windll.kernel32


def _handle(std: int):
    return _kernel32.GetStdHandle(std)


_resize_lock = threading.Lock()


def _start_resize_monitor(state) -> None:
    """Start background resize monitor for a state instance."""
    state._resize_stop = threading.Event()
    state._last_size = get_size(state)
    state._resize_thread = threading.Thread(
        target=_poll_resize,
        args=(state,),
        daemon=True,
        name="lc-win-resize",
    )
    state._resize_thread.start()


def init(state) -> int:
    """Initialize terminal for Windows console with VT processing."""

    state.in_fd = sys.stdin.fileno()
    state.out_fd = sys.stdout.fileno()
    state.term.out_fd = state.out_fd

    hin = _handle(_STD_INPUT_HANDLE)
    hout = _handle(_STD_OUTPUT_HANDLE)
    # Check for invalid handles: None, 0, or -1 (INVALID_HANDLE_VALUE)
    # 0 is rejected because GetStdHandle can return 0 for detached processes
    if hin in (None, 0, -1) or hout in (None, 0, -1):
        return -1

    state._resize_thread = None
    state._resize_stop = None
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
        | _ENABLE_VIRTUAL_TERMINAL_INPUT
    )
    if not _kernel32.SetConsoleMode(hin, new_in_mode):
        return -1

    # Start resize polling thread
    state.resize_pending = False
    _start_resize_monitor(state)
    return 0


def end(state) -> int:
    """Restore terminal to original state."""

    # Stop resize polling thread
    _stop_resize_monitor(state)

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
    state._resize_stop = None
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

    # Use msvcrt for console input on Windows.
    while True:
        try:
            if msvcrt.kbhit():
                ch = msvcrt.getch()
                if len(ch) >= 1:
                    return ch[0]
                # Empty getch response should not happen; retry.
            else:
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

    if timeout_ms < 0:
        try:
            while True:
                if msvcrt.kbhit():
                    return True
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


def _stop_resize_monitor(state) -> None:
    """Stop background resize monitor for a state instance."""
    stop = getattr(state, "_resize_stop", None)
    thread = getattr(state, "_resize_thread", None)

    if stop is not None:
        stop.set()
    if thread is not None:
        thread.join(timeout=1.0)
        state._resize_thread = None


def _poll_resize(state) -> None:
    """Poll terminal size changes and set resize_pending."""
    stop = getattr(state, "_resize_stop", None)
    if stop is None:
        return

    while not stop.is_set():
        try:
            sz = os.get_terminal_size(state.out_fd)
            current_size = (sz.lines, sz.columns)
            if current_size[0] > 0 and current_size[1] > 0:
                if current_size != state._last_size:
                    state._last_size = current_size
                    with _resize_lock:
                        state.resize_pending = True
        except (OSError, ValueError):
            pass

        stop.wait(0.25)
