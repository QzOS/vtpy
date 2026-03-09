import os

LC_OK = 0
LC_ERR = -1

LC_ATTR_NONE = 0
LC_ATTR_BOLD = 1 << 0
LC_ATTR_UNDERLINE = 1 << 1
LC_ATTR_REVERSE = 1 << 2

# Attribute layout:
# - bits 0..7   : style flags (bold, underline, reverse, etc.)
# - bits 8..15  : fg color index (0 = default, 1..n = palette index)
# - bits 16..23 : bg color index (0 = default, 1..n = palette index)
# - bits 24..31 : reserved for future expansion
LC_ATTR_STYLE_MASK = 0xFF

LC_ATTR_FG_SHIFT = 8
LC_ATTR_BG_SHIFT = 16
LC_ATTR_COLOR_MASK = 0xFF

# Logical color indices for the basic 16-color VT palette.
# 0 = terminal default, 1..8 = normal, 9..16 = bright.
LC_COLOR_DEFAULT = 0
LC_COLOR_BLACK = 1
LC_COLOR_RED = 2
LC_COLOR_GREEN = 3
LC_COLOR_YELLOW = 4
LC_COLOR_BLUE = 5
LC_COLOR_MAGENTA = 6
LC_COLOR_CYAN = 7
LC_COLOR_WHITE = 8
LC_COLOR_BRIGHT_BLACK = 9
LC_COLOR_BRIGHT_RED = 10
LC_COLOR_BRIGHT_GREEN = 11
LC_COLOR_BRIGHT_YELLOW = 12
LC_COLOR_BRIGHT_BLUE = 13
LC_COLOR_BRIGHT_MAGENTA = 14
LC_COLOR_BRIGHT_CYAN = 15
LC_COLOR_BRIGHT_WHITE = 16


def lc_attr_make(
    style: int = 0,
    fg: int = LC_COLOR_DEFAULT,
    bg: int = LC_COLOR_DEFAULT,
) -> int:
    fg_byte = fg & LC_ATTR_COLOR_MASK
    bg_byte = bg & LC_ATTR_COLOR_MASK
    return (
        (style & LC_ATTR_STYLE_MASK)
        | (fg_byte << LC_ATTR_FG_SHIFT)
        | (bg_byte << LC_ATTR_BG_SHIFT)
    )


def lc_attr_style(attr: int) -> int:
    return attr & LC_ATTR_STYLE_MASK


def lc_attr_fg(attr: int) -> int:
    return (attr >> LC_ATTR_FG_SHIFT) & LC_ATTR_COLOR_MASK


def lc_attr_bg(attr: int) -> int:
    return (attr >> LC_ATTR_BG_SHIFT) & LC_ATTR_COLOR_MASK


def lc_attr_is_default(attr: int) -> bool:
    return attr == LC_ATTR_NONE


def _sgr_16_color(is_fg: bool, idx: int) -> str:
    # Map 1..8 to normal 30-37/40-47, 9..16 to bright 90-97/100-107.
    if idx <= 0:
        return ""

    base_normal = 30 if is_fg else 40
    base_bright = 90 if is_fg else 100

    if 1 <= idx <= 8:
        return str(base_normal + (idx - 1))
    if 9 <= idx <= 16:
        return str(base_bright + (idx - 9))
    return ""


LC_DIRTY = 1
LC_FORCEPAINT = 2


class TermOps:
    clear_screen = "\x1b[2J\x1b[H"
    erase_eol = "\x1b[K"
    clear_line = "\x1b[2K"
    show_cursor_on = "\x1b[?25h"
    show_cursor_off = "\x1b[?25l"
    alt_screen_on = "\x1b[?1049h"
    alt_screen_off = "\x1b[?1049l"
    enable_wrap = "\x1b[?7h"
    disable_wrap = "\x1b[?7l"
    keypad_transmit_on = "\x1b[?1h\x1b="
    keypad_transmit_off = "\x1b[?1l\x1b>"
    sgr_reset = "\x1b[0m"
    move_fmt = "\x1b[%d;%dH"


class Terminal:
    def __init__(self) -> None:
        self.ops = TermOps()
        self.out_fd = 1
        self._last_attr = None

    def _write_all(self, data: bytes) -> None:
        off = 0
        while off < len(data):
            try:
                nwritten = os.write(self.out_fd, data[off:])
            except InterruptedError:
                continue
            if nwritten == 0:
                raise OSError("write returned zero bytes")
            if nwritten < 0:
                raise OSError("write failed")
            off += nwritten

    def write(self, s: str) -> None:
        self._write_all(s.encode('utf-8', 'replace'))

    def write_bytes(self, data: bytes | bytearray) -> None:
        if data:
            self._write_all(bytes(data))

    def move(self, y: int, x: int) -> None:
        # ANSI/VT cursor positions are 1-based.
        self.write(self.ops.move_fmt % (y + 1, x + 1))

    def move_bytes(self, y: int, x: int) -> bytes:
        return (self.ops.move_fmt % (y + 1, x + 1)).encode("ascii")

    def encode_text(self, s: str) -> bytes:
        return s.encode("utf-8", "replace")

    def clear_screen(self) -> None:
        self.write(self.ops.clear_screen)

    def show_cursor(self, on: bool) -> None:
        self.write(self.ops.show_cursor_on if on else self.ops.show_cursor_off)

    def use_alternate_screen(self, on: bool) -> None:
        self.write(self.ops.alt_screen_on if on else self.ops.alt_screen_off)

    def set_keypad_transmit(self, on: bool) -> int:
        self.write(self.ops.keypad_transmit_on if on else self.ops.keypad_transmit_off)
        return 0

    def set_wrap(self, on: bool) -> None:
        self.write(self.ops.enable_wrap if on else self.ops.disable_wrap)

    def attr_bytes(self, attr: int) -> bytes:
        # LC_ATTR_NONE means "reset to defaults".
        if lc_attr_is_default(attr):
            return self.ops.sgr_reset.encode("ascii")

        style = lc_attr_style(attr)
        fg_idx = lc_attr_fg(attr)
        bg_idx = lc_attr_bg(attr)

        parts: list[str] = ["0"]
        if style & LC_ATTR_BOLD:
            parts.append("1")
        if style & LC_ATTR_UNDERLINE:
            parts.append("4")
        if style & LC_ATTR_REVERSE:
            parts.append("7")

        fg_sgr = _sgr_16_color(True, fg_idx)
        if fg_sgr:
            parts.append(fg_sgr)

        bg_sgr = _sgr_16_color(False, bg_idx)
        if bg_sgr:
            parts.append(bg_sgr)

        return ("\x1b[" + ";".join(parts) + "m").encode("ascii")

    def set_attr(self, attr: int) -> None:
        if attr == self._last_attr:
            return

        self.write_bytes(self.attr_bytes(attr))
        self._last_attr = attr

    def note_attr(self, attr: int) -> None:
        self._last_attr = attr

    def reset_state(self) -> None:
        self._last_attr = None
