"""
Windows backend placeholder.

This module exists so platform selection has a stable target.
It is intentionally minimal until the real Win32/ctypes backend lands.
"""

import sys


def init(state) -> int:
    raise NotImplementedError("Windows backend is not implemented yet")


def end(state) -> int:
    return 0


def get_size(state) -> tuple[int, int]:
    return 24, 80


def read_byte(state):
    return None


def unread_byte(state, ch: int) -> None:
    state.pushback_byte = ch & 0xFF


def input_pending(state, timeout_ms: int) -> bool:
    del timeout_ms
    return False


def poll_resize(state) -> bool:
    return False


def clear_resize(state) -> None:
    state.resize_pending = False


def apply_term(state) -> int:
    return -1
