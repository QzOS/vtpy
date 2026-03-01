import os


LC_OK = 0
LC_ERR = -1

LC_ATTR_NONE = 0

LC_DIRTY = 1
LC_FORCEPAINT = 2


class TermOps:
    move_fmt = "\x1b[%d;%dH"
    clear_screen = "\x1b[2J\x1b[H"
    erase_eol = "\x1b[K"
    clear_line = "\x1b[2K"
    show_cursor_on = "\x1b[?25h"
    show_cursor_off = "\x1b[?25l"
    alt_screen_on = "\x1b[?1049h"
    alt_screen_off = "\x1b[?1049l"
    keypad_transmit_on = "\x1b[?1h\x1b="
    keypad_transmit_off = "\x1b[?1l\x1b>"


class Terminal:
    def __init__(self) -> None:
        self.ops = TermOps()
        self.out_fd = 1

    def write(self, s: str) -> None:
        os.write(self.out_fd, s.encode('utf-8', 'replace'))

    def move(self, y: int, x: int) -> None:
        # ANSI/VT cursor positions are 1-based.
        self.write(self.ops.move_fmt % (y + 1, x + 1))

    def clear_screen(self) -> None:
        self.write(self.ops.clear_screen)

    def show_cursor(self, on: bool) -> None:
        self.write(self.ops.show_cursor_on if on else self.ops.show_cursor_off)

    def use_alternate_screen(self, on: bool) -> None:
        self.write(self.ops.alt_screen_on if on else self.ops.alt_screen_off)

    def set_keypad_transmit(self, on: bool) -> int:
        self.write(self.ops.keypad_transmit_on if on else self.ops.keypad_transmit_off)
        return 0

    def set_attr(self, attr: int) -> None:
        # Minimal port. Extend if you want bold/reverse/underline.
        if attr == LC_ATTR_NONE:
            self.write("\x1b[0m")
        else:
            self.write("\x1b[0m")
