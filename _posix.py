import fcntl
import os
import select
import signal
import struct
import sys
import time
import termios


_resize_states = set()


def _mark_resize_pending(state) -> None:
    state.resize_pending = True


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
    state._prev_winch_handler = None
    state._resize_poll_fallback = False

    try:
        state._prev_winch_handler = signal.signal(signal.SIGWINCH, _on_sigwinch)
        _resize_states.add(state)
    except ValueError:
        # signal.signal() only works in the main thread.
        state._resize_poll_fallback = True

    return 0


def end(state) -> int:
    _resize_states.discard(state)

    if state._prev_winch_handler is not None:
        try:
            signal.signal(signal.SIGWINCH, state._prev_winch_handler)
        except (OSError, ValueError):
            pass

    if state.orig_term is not None:
        try:
            termios.tcsetattr(state.in_fd, termios.TCSAFLUSH, state.orig_term)
        except (OSError, ValueError):
            pass

    state.orig_term = None
    state.cur_term = None
    state.resize_pending = False
    state._prev_winch_handler = None
    state.in_fd = 0
    state.out_fd = 1
    state._resize_poll_fallback = False
    return 0


def get_size(state) -> tuple[int, int]:
    try:
        buf = fcntl.ioctl(state.out_fd, termios.TIOCGWINSZ, b"\x00" * 8)
        rows, cols, _xp, _yp = struct.unpack("HHHH", buf)
        if rows > 0 and cols > 0:
            return rows, cols
    except (OSError, ValueError):
        pass
    try:
        sz = os.get_terminal_size(state.out_fd)
        if sz.lines > 0 and sz.columns > 0:
            return sz.lines, sz.columns
    except (OSError, ValueError):
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
    deadline = None if timeout_ms < 0 else (time.monotonic() + (timeout_ms / 1000.0))
    while True:
        try:
            if deadline is None:
                timeout = None
            else:
                timeout = deadline - time.monotonic()
                if timeout <= 0:
                    return False
            r, _w, _e = select.select([state.in_fd], [], [], timeout)
            return bool(r)
        except InterruptedError:
            continue
        except (OSError, ValueError):
            return False


def poll_resize(state) -> bool:
    if getattr(state, "_resize_poll_fallback", False):
        try:
            current_size = get_size(state)
            last_size = getattr(state, "_last_size", None)
            if last_size is None:
                state._last_size = current_size
            elif current_size != last_size:
                state._last_size = current_size
                state.resize_pending = True
        except (OSError, ValueError):
            pass
    return bool(state.resize_pending)


def clear_resize(state) -> None:
    state.resize_pending = False


def apply_term(state) -> int:
    try:
        termios.tcsetattr(state.in_fd, termios.TCSAFLUSH, state.cur_term)
        return 0
    except (OSError, ValueError):
        return -1


def _on_sigwinch(signum, frame) -> None:
    del signum
    del frame
    for state in tuple(_resize_states):
        try:
            _mark_resize_pending(state)
        except (OSError, ValueError):
            pass
