from lc_term import (
    Terminal,
    LC_ATTR_NONE,
    LC_ATTR_BOLD,
    LC_ATTR_UNDERLINE,
    LC_ATTR_REVERSE,
)


class FakeTerminal(Terminal):
    """Terminal that captures output instead of writing to a file descriptor."""
    def __init__(self):
        super().__init__()
        self.output = []

    def write(self, s: str) -> None:
        self.output.append(s)

    def write_bytes(self, data: bytes | bytearray) -> None:
        if data:
            self.output.append(bytes(data).decode("utf-8", "replace"))


def test_set_attr_none():
    term = FakeTerminal()
    term.set_attr(LC_ATTR_NONE)
    assert term.output == ["\x1b[0m"]


def test_set_attr_bold():
    term = FakeTerminal()
    term.set_attr(LC_ATTR_BOLD)
    assert term.output == ["\x1b[0;1m"]


def test_set_attr_underline():
    term = FakeTerminal()
    term.set_attr(LC_ATTR_UNDERLINE)
    assert term.output == ["\x1b[0;4m"]


def test_set_attr_reverse():
    term = FakeTerminal()
    term.set_attr(LC_ATTR_REVERSE)
    assert term.output == ["\x1b[0;7m"]


def test_set_attr_combined():
    term = FakeTerminal()
    term.set_attr(LC_ATTR_BOLD | LC_ATTR_UNDERLINE | LC_ATTR_REVERSE)
    assert term.output == ["\x1b[0;1;4;7m"]


def test_set_attr_cached():
    term = FakeTerminal()
    term.set_attr(LC_ATTR_BOLD)
    term.set_attr(LC_ATTR_BOLD)  # Same attr, should not emit
    assert len(term.output) == 1  # Only one output


def test_reset_state():
    term = FakeTerminal()
    term.set_attr(LC_ATTR_BOLD)
    term.reset_state()
    term.set_attr(LC_ATTR_BOLD)  # After reset, should emit again
    assert len(term.output) == 2


def test_set_wrap():
    term = FakeTerminal()
    term.set_wrap(True)
    assert term.output == ["\x1b[?7h"]
    term.output.clear()
    term.set_wrap(False)
    assert term.output == ["\x1b[?7l"]


def test_note_attr():
    term = FakeTerminal()
    term.note_attr(LC_ATTR_BOLD)
    assert term._last_attr == LC_ATTR_BOLD
    # note_attr should not produce any output
    assert term.output == []
    # subsequent set_attr with same value should not emit
    term.set_attr(LC_ATTR_BOLD)
    assert term.output == []
