"""POSIX terminal backend."""
import fcntl
import os
import select
import signal
import struct
import sys
import time
import termios
import weakref


_resize_states = weakref.WeakSet()
_prev_sigwinch_handler = None
_sigwinch_installed = False


def _mark_resize_pending(state) -> None:
    state.resize_pending = True


def _call_prev_sigwinch_handler(signum, frame) -> None:
    handler = _prev_sigwinch_handler

    if handler in (None, signal.SIG_DFL, signal.SIG_IGN):
        return

    try:
        handler(signum, frame)
    except TypeError:
        # Be defensive if a foreign handler has an unexpected signature.
        pass


def _install_sigwinch_handler() -> None:
    global _prev_sigwinch_handler
    global _sigwinch_installed

    if _sigwinch_installed:
        return

    _prev_sigwinch_handler = signal.signal(signal.SIGWINCH, _on_sigwinch)
    _sigwinch_installed = True


def _uninstall_sigwinch_handler() -> None:
    global _prev_sigwinch_handler
    global _sigwinch_installed

    if not _sigwinch_installed:
        return

    try:
        current_handler = signal.getsignal(signal.SIGWINCH)
    except (OSError, ValueError):
        current_handler = None

    if _prev_sigwinch_handler is not None and current_handler is _on_sigwinch:
        try:
            signal.signal(signal.SIGWINCH, _prev_sigwinch_handler)
        except (OSError, ValueError):
            pass

    _prev_sigwinch_handler = None
    _sigwinch_installed = False


def _reset_state_fields(state) -> None:
    state.orig_term = None
    state.cur_term = None
    state.resize_pending = False
    state.pushback_byte = None
    state.in_fd = 0
    state.out_fd = 1
    state._last_size = None
    state._resize_poll_fallback = False
    state._using_sigwinch = False


def _cleanup_sigwinch_state(state) -> None:
    if getattr(state, "_using_sigwinch", False):
        _resize_states.discard(state)
        if not _resize_states:
            _uninstall_sigwinch_handler()
    state._using_sigwinch = False


def _restore_term(state, when: int) -> int:
    orig_term = getattr(state, "orig_term", None)
    in_fd = getattr(state, "in_fd", None)

    if orig_term is None or in_fd is None:
        return -1

    try:
        termios.tcsetattr(in_fd, when, orig_term)
        return 0
    except (termios.error, OSError, ValueError):
        return -1


def _copy_term_attrs(attrs):
    if attrs is None:
        return None
    copied = list(attrs)
    copied[6] = list(attrs[6])
    return copied


def _sync_resize_state(state) -> bool:
    """Refresh resize_pending against the current terminal size.

    Returns True if a real size change is currently pending, else False.
    """
    try:
        current_size = get_size(state)
        last_size = getattr(state, "_last_size", None)

        if last_size is None:
            state._last_size = current_size
            state.resize_pending = False
            return False

        if current_size != last_size:
            state._last_size = current_size
            state.resize_pending = True
            return True

        state.resize_pending = False
        return False
    except (OSError, ValueError):
        return bool(getattr(state, "resize_pending", False))


def _is_tty_fd(fd: int) -> bool:
    try:
        return os.isatty(fd)
    except (OSError, ValueError, TypeError):
        return False


def _get_winsize_fd(fd: int):
    try:
        buf = fcntl.ioctl(fd, termios.TIOCGWINSZ, b"\x00" * 8)
        rows, cols, _xp, _yp = struct.unpack("HHHH", buf)
        if rows > 0 and cols > 0:
            return rows, cols
    except (OSError, ValueError, TypeError):
        pass

    try:
        sz = os.get_terminal_size(fd)
        if sz.lines > 0 and sz.columns > 0:
            return sz.lines, sz.columns
    except (OSError, ValueError, TypeError):
        pass

    return None


def init(state) -> int:
    _cleanup_sigwinch_state(state)
    _reset_state_fields(state)
    try:
        state.in_fd = sys.stdin.fileno()
        state.out_fd = sys.stdout.fileno()
    except (OSError, ValueError):
        return -1

    try:
        state.term.out_fd = state.out_fd
    except AttributeError:
        pass

    if not _is_tty_fd(state.in_fd):
        return -1

    orig_term = None
    try:
        orig_term = termios.tcgetattr(state.in_fd)
        state.orig_term = _copy_term_attrs(orig_term)
        state.cur_term = _copy_term_attrs(orig_term)
        state.cur_term[3] &= ~(termios.ICANON | termios.ECHO)
        state.cur_term[6][termios.VMIN] = 1
        state.cur_term[6][termios.VTIME] = 0
        termios.tcsetattr(state.in_fd, termios.TCSANOW, state.cur_term)
    except (termios.error, OSError, ValueError):
        if orig_term is not None:
            state.orig_term = _copy_term_attrs(orig_term)
            _restore_term(state, termios.TCSANOW)
        _reset_state_fields(state)
        return -1

    state.resize_pending = False
    state.pushback_byte = None
    state._last_size = get_size(state)
    state._resize_poll_fallback = False
    state._using_sigwinch = False

    try:
        _install_sigwinch_handler()
        _resize_states.add(state)
        state._using_sigwinch = True
    except ValueError:
        # signal.signal() only works in the main thread.
        state._resize_poll_fallback = True

    return 0


def end(state) -> int:
    _cleanup_sigwinch_state(state)
    # Restore without flushing unread input on teardown.
    _restore_term(state, termios.TCSADRAIN)
    _reset_state_fields(state)
    return 0


def get_size(state) -> tuple[int, int]:
    out_fd = getattr(state, "out_fd", None)
    in_fd = getattr(state, "in_fd", None)

    if out_fd is not None:
        size = _get_winsize_fd(out_fd)
        if size is not None:
            return size

    if in_fd is not None and in_fd != out_fd:
        size = _get_winsize_fd(in_fd)
        if size is not None:
            return size

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
    if state.pushback_byte is not None:
        return True

    if getattr(state, "resize_pending", False) and _sync_resize_state(state):
        return False

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
            # A signal (typically SIGWINCH) interrupted select(). If that
            # signal corresponds to a real size change, let the caller observe
            # it via poll_resize() instead of immediately re-entering select().
            if getattr(state, "resize_pending", False) and _sync_resize_state(state):
                return False
            continue

        except (OSError, ValueError):
            return False


def poll_resize(state) -> bool:
    if getattr(state, "_resize_poll_fallback", False):
        return _sync_resize_state(state)

    if getattr(state, "resize_pending", False):
        # Confirm that SIGWINCH corresponds to an actual size change and clear
        # stale/spurious notifications.
        return _sync_resize_state(state)

    return bool(state.resize_pending)


def clear_resize(state) -> None:
    state.resize_pending = False


def apply_term(state) -> int:
    if state.cur_term is None:
        return -1

    new_term = _copy_term_attrs(state.cur_term)
    if new_term is None:
        return -1

    try:
        termios.tcsetattr(state.in_fd, termios.TCSANOW, new_term)
        state.cur_term = new_term
        return 0
    except (termios.error, OSError, ValueError):
        return -1


def raw(state) -> int:
    if state.cur_term is None:
        return -1
    state.cur_term[3] &= ~(termios.ICANON | termios.ISIG | termios.ECHO)
    state.cur_term[6][termios.VMIN] = 1
    state.cur_term[6][termios.VTIME] = 0
    return apply_term(state)


def noraw(state) -> int:
    if state.cur_term is None:
        return -1
    state.cur_term[3] |= (termios.ICANON | termios.ISIG)
    return apply_term(state)


def cbreak(state) -> int:
    if state.cur_term is None:
        return -1
    state.cur_term[3] &= ~termios.ICANON
    state.cur_term[6][termios.VMIN] = 1
    state.cur_term[6][termios.VTIME] = 0
    return apply_term(state)


def nocbreak(state) -> int:
    if state.cur_term is None:
        return -1
    state.cur_term[3] |= termios.ICANON
    return apply_term(state)


def echo(state) -> int:
    if state.cur_term is None:
        return -1
    state.cur_term[3] |= termios.ECHO
    return apply_term(state)


def noecho(state) -> int:
    if state.cur_term is None:
        return -1
    state.cur_term[3] &= ~termios.ECHO
    return apply_term(state)


def _on_sigwinch(signum, frame) -> None:
    for state in tuple(_resize_states):
        try:
            _mark_resize_pending(state)
        except Exception:
            pass

    _call_prev_sigwinch_handler(signum, frame)
