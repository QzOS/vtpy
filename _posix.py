import fcntl
import os
import select
import signal
import struct
import sys
import termios


def init(state) -> int:
    state.in_fd = sys.stdin.fileno()
    state.out_fd = sys.stdout.fileno()
    state.term.out_fd = state.out_fd

    state.orig_term = termios.tcgetattr(state.in_fd)
    state.cur_term = termios.tcgetattr(state.in_fd)

    state.cur_term[3] &= ~(termios.ICANON | termios.ECHO)
    state.cur_term[6][termios.VMIN] = 1
    state.cur_term[6][termios.VTIME] = 0
    termios.tcsetattr(state.in_fd, termios.TCSAFLUSH, state.cur_term)

    state.resize_pending = False
    state._prev_winch_handler = signal.signal(signal.SIGWINCH, _on_sigwinch)
    return 0


def end(state) -> int:
    if state._prev_winch_handler is not None:
        try:
            signal.signal(signal.SIGWINCH, state._prev_winch_handler)
        except (OSError, ValueError):
            pass

    if state.orig_term is not None:
        try:
            termios.tcsetattr(state.in_fd, termios.TCSAFLUSH, state.orig_term)
        except OSError:
            pass

    state.orig_term = None
    state.cur_term = None
    state.resize_pending = False
    state._prev_winch_handler = None
    state.in_fd = 0
    state.out_fd = 1
    return 0


def get_size(state) -> tuple[int, int]:
    try:
        buf = fcntl.ioctl(state.out_fd, termios.TIOCGWINSZ, b"\x00" * 8)
        rows, cols, _xp, _yp = struct.unpack("HHHH", buf)
        if rows > 0 and cols > 0:
            return rows, cols
    except OSError:
        pass
    return 24, 80


def read_byte(state):
    if state.pushback_byte is not None:
        ch = state.pushback_byte
        state.pushback_byte = None
        return ch

    while True:
        try:
            data = os.read(state.in_fd, 1)
            if len(data) == 1:
                return data[0]
            if len(data) == 0:
                return None
        except InterruptedError:
            continue
        except (OSError, ValueError):
            return None


def unread_byte(state, ch: int) -> None:
    state.pushback_byte = ch & 0xFF


def input_pending(state, timeout_ms: int) -> bool:
    timeout = None if timeout_ms < 0 else timeout_ms / 1000.0
    while True:
        try:
            r, _w, _e = select.select([state.in_fd], [], [], timeout)
            return bool(r)
        except InterruptedError:
            continue
        except (OSError, ValueError):
            return False


def poll_resize(state) -> bool:
    return bool(state.resize_pending)


def clear_resize(state) -> None:
    state.resize_pending = False


def apply_term(state) -> int:
    try:
        termios.tcsetattr(state.in_fd, termios.TCSAFLUSH, state.cur_term)
        return 0
    except OSError:
        return -1


def _on_sigwinch(signum, frame) -> None:
    del signum
    del frame
    # Imported lazily to avoid module import cycles at import time.
    from lc_screen import lc
    lc.resize_pending = True
