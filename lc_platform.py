import sys

if sys.platform == "win32":
    import _win as backend
else:
    import _posix as backend

__all__ = ["backend"]

_REQUIRED_API = (
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
    "cbreak",
    "nocbreak",
    "echo",
    "noecho",
)

# Keep this list in sync with the backend contract text below.
_REQUIRED_API = _REQUIRED_API + ("noraw",)


class BackendContractError(RuntimeError):
    pass


def backend_has_api() -> bool:
    return all(hasattr(backend, name) for name in _REQUIRED_API)


def verify_backend() -> None:
    missing = [name for name in _REQUIRED_API if not hasattr(backend, name)]
    if missing:
        raise BackendContractError(
            "backend is missing required API: " + ", ".join(missing)
        )


BACKEND_CONTRACT = """
Backend contract:

init(state) -> int
    Initialize backend-owned terminal/input state.
    Return 0 on success, -1 on failure.

end(state) -> int
    Restore backend-owned state. Must be safe to call during teardown.

get_size(state) -> (rows, cols)
    Return current terminal size. Must never raise; use a safe fallback.

read_byte(state) -> int | None
    Return one input byte in range 0..255, or None on EOF/error/unavailable
    terminal failure. This interface is byte-oriented by design.

unread_byte(state, ch) -> None
    Push back exactly one byte-equivalent value for the next read_byte().

input_pending(state, timeout_ms) -> bool
    Return True only if a keyboard/input byte can be consumed now (or within
    timeout). A pending resize alone must not make this return True.

poll_resize(state) -> bool
    Return True iff a real terminal size change is pending observation by the
    core. Spurious/stale notifications should be filtered out here when
    practical.

clear_resize(state) -> None
    Clear the backend's pending resize state after the core has observed it.

apply_term/raw/noraw/cbreak/nocbreak/echo/noecho
    Backend-specific terminal mode controls. Return 0 on success, -1 on
    failure.
"""


verify_backend()
