import sys

if sys.platform == "win32":
    import _win as backend
else:
    import _posix as backend


__all__ = ["backend"]
