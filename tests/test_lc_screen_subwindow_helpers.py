import pytest

from lc_screen import lc, lc_subwindow, lc_subwindow_from
from lc_window import lc_new


@pytest.fixture(autouse=True)
def _restore_lc_state():
    prev_stdscr = lc.stdscr
    prev_backend_started = lc.backend_started
    prev_session_active = lc.session_active
    try:
        yield
    finally:
        lc.stdscr = prev_stdscr
        lc.backend_started = prev_backend_started
        lc.session_active = prev_session_active


def _set_screen_state(stdscr, *, backend_started: bool, session_active: bool) -> None:
    lc.stdscr = stdscr
    lc.backend_started = backend_started
    lc.session_active = session_active


def test_lc_subwindow_uses_stdscr_when_session_is_available() -> None:
    root = lc_new(5, 7, 0, 0)
    assert root is not None
    _set_screen_state(root, backend_started=False, session_active=False)

    sub = lc_subwindow(2, 3, 1, 2)

    assert sub is not None
    assert sub.parent is root
    assert sub.root is root
    assert sub.pary == 1
    assert sub.parx == 2


def test_lc_subwindow_rejects_calls_during_backend_bootstrap_gap() -> None:
    root = lc_new(5, 7, 0, 0)
    assert root is not None
    _set_screen_state(root, backend_started=True, session_active=False)

    assert lc_subwindow(2, 3, 1, 2) is None


def test_lc_subwindow_from_delegates_to_lc_subwin() -> None:
    parent = lc_new(4, 6, 0, 0)
    assert parent is not None

    sub = lc_subwindow_from(parent, 2, 2, 1, 3)

    assert sub is not None
    assert sub.parent is parent
    assert sub.begy == 1
    assert sub.begx == 3


def test_lc_subwindow_from_applies_subwindow_bounds_validation() -> None:
    parent = lc_new(3, 3, 0, 0)
    assert parent is not None

    assert lc_subwindow_from(parent, 2, 2, 2, 0) is None
