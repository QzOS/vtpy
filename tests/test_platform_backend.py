from lc_platform import backend


def test_backend_has_required_api():
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
    ]
    for name in required:
        assert hasattr(backend, name)
