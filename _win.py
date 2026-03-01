"""Windows terminal backend.

Requires Windows 10 1607+ (or Windows Terminal) for VT / ANSI support.
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


# Module-level state for resize polling thread
_resize_thread: Optional[threading.Thread] = None
_stop_resize = False
_last_size: tuple[int, int] = (24, 80)


def init(state) -> int:
    """Initialize terminal for Windows console with VT processing."""
    global _resize_thread, _stop_resize, _last_size

    state.in_fd = sys.stdin.fileno()
    state.out_fd = sys.stdout.fileno()
    state.term.out_fd = state.out_fd

    hin = _handle(_STD_INPUT_HANDLE)
    hout = _handle(_STD_OUTPUT_HANDLE)

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
    _stop_resize = False
    _last_size = get_size(state)

    def _poll_resize():
        global _last_size, _stop_resize
        while not _stop_resize:
            try:
                sz = os.get_terminal_size(state.out_fd)
                current_size = (sz.lines, sz.columns)
                if current_size != _last_size and current_size[0] > 0 and current_size[1] > 0:
                    _last_size = current_size
                    state.resize_pending = True
            except OSError:
                pass
            time.sleep(0.25)

    _resize_thread = threading.Thread(target=_poll_resize, daemon=True)
    _resize_thread.start()

    return 0


def end(state) -> int:
    """Restore terminal to original state."""
    global _resize_thread, _stop_resize

    # Stop resize polling thread
    _stop_resize = True
    _resize_thread = None

    if state.orig_term is not None:
        orig_in_mode, orig_out_mode, hin, hout = state.orig_term
        try:
            _kernel32.SetConsoleMode(hin, orig_in_mode)
            _kernel32.SetConsoleMode(hout, orig_out_mode)
        except (OSError, ValueError):
            pass

    state.orig_term = None
    state.cur_term = None
    state.resize_pending = False
    state.in_fd = 0
    state.out_fd = 1
    return 0


def get_size(state) -> tuple[int, int]:
    """Get terminal size (rows, cols)."""
    try:
        sz = os.get_terminal_size(state.out_fd)
        if sz.lines > 0 and sz.columns > 0:
            return sz.lines, sz.columns
    except OSError:
        pass
    return 24, 80


def read_byte(state):
    """Read a single byte from input."""
    if state.pushback_byte is not None:
        ch = state.pushback_byte
        state.pushback_byte = None
        return ch

    # Use msvcrt for console input on Windows
    while True:
        try:
            if msvcrt.kbhit():
                ch = msvcrt.getch()
                if len(ch) == 1:
                    return ch[0]
            else:
                # No input available, yield to allow other threads
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
        # Indefinite wait
        while True:
            if msvcrt.kbhit():
                return True
            time.sleep(0.001)
    elif timeout_ms == 0:
        # Immediate check
        return msvcrt.kbhit()
    else:
        # Wait with timeout
        deadline = time.monotonic() + (timeout_ms / 1000.0)
        while time.monotonic() < deadline:
            if msvcrt.kbhit():
                return True
            time.sleep(0.001)
        return False


def poll_resize(state) -> bool:
    """Check if a resize event occurred."""
    return bool(state.resize_pending)


def clear_resize(state) -> None:
    """Clear the resize pending flag."""
    state.resize_pending = False


def apply_term(state) -> int:
    """Apply terminal settings.
    
    On Windows, terminal mode changes are applied immediately
    via SetConsoleMode, so this is effectively a no-op.
    Returns 0 to indicate success.
    """
    return 0
