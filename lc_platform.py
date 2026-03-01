import sys

if sys.platform == "win32":
    import _win as backend
else:
    import _posix as backend

__all__ = ["backend", "backend_has_api"]


def backend_has_api() -> bool:
    required = (
        "init",
        "end",
        "get_size",
        "read_byte",
        "unread_byte",
        "input_pending",
        "poll_resize",
        "clear_resize",
        "apply_term",
        "raw",
        "noraw",
        "cbreak",
        "nocbreak",
        "echo",
        "noecho",
    )
    return all(hasattr(backend, name) for name in required)
