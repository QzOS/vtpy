from lc_keys import (
    LCKey,
    LC_KT_CHAR,
    LC_KT_KEYSYM,
    LC_KEY_RESIZE,
    lc_readkey,
)

from lc_refresh import lc_refresh
from lc_screen import (
    lc,
    lc_session,
    lc_get_size,
    lc_move,
    lc_addstr,
    lc_addstr_at,
    lc_addstr_centered,
)
from lc_window import lc_wclear
from lc_screen import lc_draw_box


def key_name(key: LCKey) -> str:
    if key.type == LC_KT_CHAR:
        if key.rune == 0x1B:
            return "CHAR ESC"
        if 32 <= key.rune < 127:
            return f"CHAR '{chr(key.rune)}' ({key.rune})"
        return f"CHAR U+{key.rune:04X}"

    if key.type == LC_KT_KEYSYM:
        if key.keysym == LC_KEY_RESIZE:
            return "KEY RESIZE"
        return f"KEYSYM 0x{key.keysym:X} mods={key.mods}"

    return "UNKNOWN"


def draw_frame(last_key: str, info: str) -> None:
    rows, cols = lc_get_size()

    lc_wclear(lc.stdscr)

    # Outer border.
    lc_draw_box(0, 0, rows, cols)

    # Title and footer.
    lc_addstr_centered(0, " lc demo ")
    lc_addstr_at(rows - 1, 2, "q: quit")

    # Main content box if there is room.
    if rows >= 8 and cols >= 20:
        inner_y = 2
        inner_x = 2
        inner_h = rows - 5
        inner_w = cols - 4
        lc_draw_box(inner_y, inner_x, inner_h, inner_w)

        lc_addstr_at(3, 4, f"size: {rows}x{cols}")
        lc_addstr_at(4, 4, f"last: {last_key}")
        lc_addstr_at(5, 4, info)

        msg = "Resize the terminal or press keys"
        msg_x = max(1, (cols - len(msg)) // 2)
        lc_addstr_at(rows // 2, msg_x, msg)
    else:
        # Tiny terminal fallback.
        lc_addstr_at(1, 1, f"{rows}x{cols}")
        lc_addstr_at(2, 1, last_key[:max(0, cols - 2)])

    lc_refresh()


def main() -> None:
    last_key = "none"
    info = "ready"

    with lc_session():
        draw_frame(last_key, info)

        while True:
            key = LCKey()
            rc = lc_readkey(key)
            if rc != 0:
                continue

            last_key = key_name(key)

            if key.type == LC_KT_KEYSYM and key.keysym == LC_KEY_RESIZE:
                rows, cols = lc_get_size()
                info = f"resize handled: now {rows}x{cols}"
                draw_frame(last_key, info)
                continue

            if key.type == LC_KT_CHAR and key.rune == ord('q'):
                break

            info = "input received"
            draw_frame(last_key, info)


if __name__ == "__main__":
    main()
