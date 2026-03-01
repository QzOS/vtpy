from lc_platform import backend, backend_has_api


def test_backend_has_required_api():
    assert backend_has_api() is True
    required = [
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
    ]
    for name in required:
        assert hasattr(backend, name)
