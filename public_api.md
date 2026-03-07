# vtpy Public API Reference

This document describes every public function in the vtpy library with short usage examples.

---

## Table of Contents

1. [Session Management](#session-management)
2. [Screen and Size](#screen-and-size)
3. [Cursor and Movement](#cursor-and-movement)
4. [Text Output](#text-output)
5. [Drawing Primitives](#drawing-primitives)
6. [Fill and Clear](#fill-and-clear)
7. [Window Operations](#window-operations)
8. [Panel and Subwindow Helpers](#panel-and-subwindow-helpers)
9. [Input Handling](#input-handling)
10. [Terminal Mode Control](#terminal-mode-control)
11. [Refresh](#refresh)
12. [Input Settings](#input-settings)
13. [Constants](#constants)

---

## Session Management

### `lc_init() -> Optional[LCWin]`

Initialize the terminal library and return the standard screen window.

```python
from lc_screen import lc_init, lc_end

stdscr = lc_init()
if stdscr is None:
    print("Failed to initialize")
else:
    # Use the terminal...
    lc_end()
```

### `lc_end() -> int`

Restore the terminal to its original state and clean up resources. Returns `0` on success.

```python
from lc_screen import lc_init, lc_end

lc_init()
# ... do work ...
lc_end()
```

### `lc_session()`

Context manager for automatic initialization and cleanup.

```python
from lc_screen import lc_session

with lc_session() as stdscr:
    # Terminal is initialized here
    pass
# Terminal is automatically restored
```

---

## Screen and Size

### `lc_get_size() -> tuple[int, int]`

Return the current terminal size as `(rows, cols)`.

```python
from lc_screen import lc_session, lc_get_size

with lc_session():
    rows, cols = lc_get_size()
    print(f"Terminal is {rows} rows by {cols} columns")
```

### `lc_check_resize() -> int`

Check for and handle terminal resize. Returns `1` if a resize occurred, `0` if not, `-1` on error.

```python
from lc_screen import lc_check_resize

rc = lc_check_resize()
if rc == 1:
    # Terminal was resized, rebuild any subwindows
    pass
```

### `lc_is_resize_pending() -> bool`

Check if a resize event is pending.

```python
from lc_screen import lc_is_resize_pending

if lc_is_resize_pending():
    # Handle resize
    pass
```

---

## Cursor and Movement

### `lc_move(y: int, x: int) -> int`

Move the cursor to position `(y, x)` on the standard screen. Returns `0` on success, `-1` if out of bounds.

```python
from lc_screen import lc_session, lc_move

with lc_session():
    if lc_move(5, 10) == 0:
        # Cursor is now at row 5, column 10
        pass
```

### `lc_wmove(win: LCWin, y: int, x: int) -> int`

Move the cursor to position `(y, x)` within a specific window. Returns `0` on success, `-1` if invalid.

```python
from lc_window import lc_wmove

lc_wmove(my_window, 2, 3)  # Move cursor to row 2, col 3 in window
```

---

## Text Output

### `lc_put(ch: int) -> int`

Write a single character at the current cursor position on the standard screen with default attributes (`LC_ATTR_NONE`). Under the current saturating cursor policy, a write at the final writable cell succeeds and leaves the cursor at that same cell. Use `lc_put_attr()` to specify custom attributes.

```python
from lc_screen import lc_session, lc_move, lc_put

with lc_session():
    lc_move(0, 0)
    lc_put(ord('H'))
    lc_put(ord('i'))
```

### `lc_put_attr(ch: int, attr: int) -> int`

Write a single character with attributes at the current cursor position. This is the attributed variant of `lc_put()`.

```python
from lc_screen import lc_session, lc_move, lc_put_attr
from lc_term import LC_ATTR_BOLD

with lc_session():
    lc_move(0, 0)
    lc_put_attr(ord('X'), LC_ATTR_BOLD)
```

### `lc_wput(win: LCWin, ch: int, attr: int) -> int`

Write a single character with attributes at the cursor position in a specific window. Under the current saturating cursor policy, a write at the final writable cell succeeds and leaves the cursor at that same cell.

```python
from lc_window import lc_wput
from lc_term import LC_ATTR_NONE

lc_wput(my_window, ord('A'), LC_ATTR_NONE)
```

### `lc_addstr(s: str) -> int`

Write a string at the current cursor position on the standard screen.

```python
from lc_screen import lc_session, lc_move, lc_addstr

with lc_session():
    lc_move(0, 0)
    lc_addstr("Hello, World!")
```

### `lc_mvaddstr(y: int, x: int, s: str) -> int`

Move to `(y, x)` and write a string.

```python
from lc_screen import lc_session, lc_mvaddstr

with lc_session():
    lc_mvaddstr(5, 10, "Message here")
```

### `lc_addstr_at(y: int, x: int, s: str) -> int`

Write a string at position `(y, x)`. Equivalent to calling `lc_mvwaddstr(lc.stdscr, y, x, s)` internally.

```python
from lc_screen import lc_session, lc_addstr_at

with lc_session():
    lc_addstr_at(3, 0, "Line 3")
```

### `lc_addstr_centered(y: int, s: str) -> int`

Write a string horizontally centered on row `y`.

```python
from lc_screen import lc_session, lc_addstr_centered

with lc_session():
    lc_addstr_centered(0, "Title")
```

### `lc_waddstr(win: LCWin, s: str) -> int`

Write a string at the cursor position in a specific window. This is a cursor-driven prefix-success write under the current saturating cursor policy: if the write reaches the final writable cell, that cell is written, the cursor remains there, and the function still returns success even though the remaining suffix is not written.

```python
from lc_window import lc_waddstr

lc_waddstr(my_window, "Window text")
```

### `lc_mvwaddstr(win: LCWin, y: int, x: int, s: str) -> int`

Move to `(y, x)` within a window and write a string.

```python
from lc_window import lc_mvwaddstr

lc_mvwaddstr(my_window, 1, 2, "Hello")
```

### `lc_center_x(width: int, text: str) -> int`

Calculate the x-offset to center text within a given width.

```python
from lc_screen import lc_center_x

x = lc_center_x(80, "Title")  # Returns offset to center "Title" in 80 columns
```

---

## Drawing Primitives

### `lc_draw_hline(y: int, x: int, width: int, ch: str = "-", attr: int = LC_ATTR_NONE) -> int`

Draw a horizontal line on the standard screen.

```python
from lc_screen import lc_session, lc_draw_hline

with lc_session():
    lc_draw_hline(5, 0, 40)  # Draw 40-char line at row 5
```

### `lc_draw_vline(y: int, x: int, height: int, ch: str = "|", attr: int = LC_ATTR_NONE) -> int`

Draw a vertical line on the standard screen.

```python
from lc_screen import lc_session, lc_draw_vline

with lc_session():
    lc_draw_vline(0, 10, 20)  # Draw 20-char vertical line at column 10
```

### `lc_draw_box(y: int, x: int, height: int, width: int, attr: int = LC_ATTR_NONE, hch: str = "-", vch: str = "|", tl: str = "+", tr: str = "+", bl: str = "+", br: str = "+") -> int`

Draw a box on the standard screen.

```python
from lc_screen import lc_session, lc_draw_box

with lc_session():
    lc_draw_box(2, 2, 10, 30)  # 10x30 box at position (2, 2)
```

### `lc_draw_box_title(y: int, x: int, height: int, width: int, title: str, attr: int = LC_ATTR_NONE) -> int`

Draw a title on the top edge of a box (assumes box is already drawn).

```python
from lc_screen import lc_session, lc_draw_box, lc_draw_box_title

with lc_session():
    lc_draw_box(0, 0, 10, 40)
    lc_draw_box_title(0, 0, 10, 40, "My Panel")
```

### `lc_draw_panel(y: int, x: int, height: int, width: int, title: Optional[str] = None, frame_attr: int = LC_ATTR_NONE, fill: Optional[str] = None, fill_attr: int = LC_ATTR_NONE, ...) -> int`

Draw a complete panel with optional title and interior fill.

```python
from lc_screen import lc_session, lc_draw_panel

with lc_session():
    lc_draw_panel(1, 1, 12, 40, title="Status", fill=" ")
```

### `lc_wdraw_hline(win: LCWin, y: int, x: int, width: int, ch: str = "-", attr: int = LC_ATTR_NONE) -> int`

Draw a horizontal line in a specific window.

```python
from lc_window import lc_wdraw_hline

lc_wdraw_hline(my_window, 0, 0, 20)
```

### `lc_wdraw_vline(win: LCWin, y: int, x: int, height: int, ch: str = "|", attr: int = LC_ATTR_NONE) -> int`

Draw a vertical line in a specific window.

```python
from lc_window import lc_wdraw_vline

lc_wdraw_vline(my_window, 0, 0, 10)
```

### `lc_wdraw_box(win: LCWin, y: int, x: int, height: int, width: int, attr: int = LC_ATTR_NONE, ...) -> int`

Draw a box in a specific window.

```python
from lc_window import lc_wdraw_box

lc_wdraw_box(my_window, 0, 0, 5, 20)
```

### `lc_wdraw_box_title(win: LCWin, y: int, x: int, height: int, width: int, title: str, attr: int = LC_ATTR_NONE) -> int`

Draw a title on a box within a specific window.

```python
from lc_window import lc_wdraw_box, lc_wdraw_box_title

lc_wdraw_box(my_window, 0, 0, 10, 30)
lc_wdraw_box_title(my_window, 0, 0, 10, 30, "Title")
```

### `lc_wdraw_panel(win: LCWin, y: int, x: int, height: int, width: int, title: Optional[str] = None, ...) -> int`

Draw a complete panel within a specific window.

```python
from lc_window import lc_wdraw_panel

lc_wdraw_panel(my_window, 0, 0, 8, 25, title="Info")
```

---

## Fill and Clear

### `lc_fill(y: int, x: int, height: int, width: int, ch: str = " ", attr: int = LC_ATTR_NONE) -> int`

Fill a rectangular area on the standard screen.

```python
from lc_screen import lc_session, lc_fill

with lc_session():
    lc_fill(2, 2, 5, 10, ".", 0)  # Fill 5x10 area with dots
```

### `lc_wfill(win: LCWin, y: int, x: int, height: int, width: int, ch: str = " ", attr: int = LC_ATTR_NONE) -> int`

Fill a rectangular area within a specific window.

```python
from lc_window import lc_wfill

lc_wfill(my_window, 0, 0, 3, 10, "#")
```

### `lc_wclear(win: LCWin) -> int`

Clear a window (fill with spaces and reset cursor to `(0, 0)`).

```python
from lc_window import lc_wclear
from lc_screen import lc

lc_wclear(lc.stdscr)
```

### `lc_wclrtoeol(win: LCWin) -> int`

Clear from the cursor position to the end of the current line.

```python
from lc_window import lc_wclrtoeol

lc_wclrtoeol(my_window)
```

### `lc_wclrtobot(win: LCWin) -> int`

Clear from the cursor position to the bottom of the window.

```python
from lc_window import lc_wclrtobot

lc_wclrtobot(my_window)
```

---

## Window Operations

### `lc_new(nlines: int, ncols: int, begin_y: int, begin_x: int) -> Optional[LCWin]`

Create a new top-level window with its own backing storage.

```python
from lc_window import lc_new

win = lc_new(10, 40, 0, 0)  # 10 rows, 40 cols, at origin
```

### `lc_subwindow(nlines: int, ncols: int, begin_y: int, begin_x: int) -> Optional[LCWin]`

Create a subwindow of the standard screen (shared backing storage).

```python
from lc_screen import lc_session, lc_subwindow

with lc_session():
    sub = lc_subwindow(5, 20, 2, 2)  # 5x20 subwindow at (2, 2)
```

### `lc_subwindow_from(parent: LCWin, nlines: int, ncols: int, begin_y: int, begin_x: int) -> Optional[LCWin]`

Create a subwindow from a specific parent window.

```python
from lc_screen import lc_subwindow_from

child = lc_subwindow_from(parent_win, 4, 10, 1, 1)
```

### `lc_subwin(parent: LCWin, nlines: int, ncols: int, begin_y: int, begin_x: int) -> Optional[LCWin]`

Low-level function to create a subwindow from a parent (parent-relative coordinates).

```python
from lc_window import lc_subwin

sub = lc_subwin(parent, 5, 20, 0, 0)
```

### `lc_free(win: LCWin) -> int`

Free a window and all its children. Returns `0` on success.

```python
from lc_window import lc_new, lc_free

win = lc_new(10, 20, 0, 0)
# ... use window ...
lc_free(win)
```

### `lc_invalidate_children(win: LCWin) -> None`

Invalidate and free all child windows of a parent (used during resize).

```python
from lc_window import lc_invalidate_children

lc_invalidate_children(parent_win)
```

---

## Panel and Subwindow Helpers

### `lc_get_panel_content_rect(y: int, x: int, height: int, width: int) -> tuple[int, int, int, int]`

Get the interior content rectangle of a panel (inside the border).

```python
from lc_screen import lc_get_panel_content_rect

inner_y, inner_x, inner_h, inner_w = lc_get_panel_content_rect(0, 0, 10, 30)
# Returns (1, 1, 8, 28) for a 10x30 panel
```

### `lc_panel_content_subwindow(y: int, x: int, height: int, width: int) -> Optional[LCWin]`

Create a subwindow for the interior content area of a panel on the standard screen.

```python
from lc_screen import lc_session, lc_draw_panel, lc_panel_content_subwindow
from lc_window import lc_waddstr

with lc_session():
    lc_draw_panel(2, 2, 10, 30, title="Panel")
    content = lc_panel_content_subwindow(2, 2, 10, 30)
    if content:
        lc_waddstr(content, "Content inside panel")
```

### `lc_panel_content_subwindow_from(parent: LCWin, y: int, x: int, height: int, width: int) -> Optional[LCWin]`

Create a panel content subwindow from a specific parent.

```python
from lc_screen import lc_panel_content_subwindow_from

content = lc_panel_content_subwindow_from(my_window, 0, 0, 10, 20)
```

### `lc_panel_subwin(parent: LCWin, y: int, x: int, height: int, width: int) -> Optional[LCWin]`

Low-level function to create a panel content subwindow.

```python
from lc_window import lc_panel_subwin

content = lc_panel_subwin(parent, 0, 0, 10, 20)
```

### `lc_panel_content_rect(y: int, x: int, height: int, width: int) -> tuple[int, int, int, int]`

Calculate the interior content rectangle for a panel (low-level).

```python
from lc_window import lc_panel_content_rect

iy, ix, ih, iw = lc_panel_content_rect(0, 0, 10, 30)
```

---

## Input Handling

### `lc_readkey(out: LCKey) -> int`

Read a key event into an `LCKey` structure. Returns `0` (LC_OK) on success, `-1` (LC_ERR) on failure.

```python
from lc_keys import LCKey, lc_readkey, LC_KT_CHAR, LC_KT_KEYSYM, LC_KEY_RESIZE
from lc_screen import lc_session

with lc_session():
    key = LCKey()
    if lc_readkey(key) == 0:
        if key.type == LC_KT_CHAR:
            print(f"Character: {chr(key.rune)}")
        elif key.type == LC_KT_KEYSYM:
            if key.keysym == LC_KEY_RESIZE:
                print("Terminal resized")
```

### `lc_getch() -> int`

Simple blocking read that returns a character code or keysym. Returns `-1` on error.

```python
from lc_keys import lc_getch, LC_KEY_UP
from lc_screen import lc_session

with lc_session():
    ch = lc_getch()
    if ch == ord('q'):
        print("Quit")
    elif ch == LC_KEY_UP:
        print("Up arrow pressed")
```

### `LCKey`

Data class for key events.

```python
from lc_keys import LCKey, LC_KT_CHAR, LC_KT_KEYSYM

key = LCKey()
# After lc_readkey(key):
# key.type    - LC_KT_CHAR or LC_KT_KEYSYM
# key.mods    - Modifier flags (LC_MOD_SHIFT, LC_MOD_ALT, LC_MOD_CTRL)
# key.rune    - Unicode codepoint (when type == LC_KT_CHAR)
# key.keysym  - Key symbol constant (when type == LC_KT_KEYSYM)
```

### Input Functions (Low-Level)

```python
from lc_input import read_byte, unread_byte, input_pending

# Read a single byte from input
b = read_byte()  # Returns int 0-255 or None

# Push back a byte
unread_byte(b)

# Check if input is available
if input_pending(100):  # 100ms timeout
    b = read_byte()
```

---

## Terminal Mode Control

### `lc_raw() -> int`

Enable raw mode (no line buffering, no signal processing).

```python
from lc_screen import lc_session, lc_raw

with lc_session():
    lc_raw()
```

### `lc_noraw() -> int`

Disable raw mode.

```python
from lc_screen import lc_noraw

lc_noraw()
```

### `lc_cbreak() -> int`

Enable cbreak mode (no line buffering, signals still work).

```python
from lc_screen import lc_cbreak

lc_cbreak()
```

### `lc_nocbreak() -> int`

Disable cbreak mode.

```python
from lc_screen import lc_nocbreak

lc_nocbreak()
```

### `lc_echo() -> int`

Enable input echo.

```python
from lc_screen import lc_echo

lc_echo()
```

### `lc_noecho() -> int`

Disable input echo.

```python
from lc_screen import lc_noecho

lc_noecho()
```

### `lc_keypad(on: bool) -> int`

Enable or disable keypad transmit mode (for arrow keys, function keys).

```python
from lc_screen import lc_keypad

lc_keypad(True)   # Enable special key recognition
lc_keypad(False)  # Disable
```

---

## Refresh

### `lc_refresh() -> int`

Refresh the standard screen (send pending changes to terminal).

```python
from lc_screen import lc_session, lc_addstr_at
from lc_refresh import lc_refresh

with lc_session():
    lc_addstr_at(0, 0, "Hello")
    lc_refresh()  # Display changes
```

### `lc_wrefresh(win: LCWin) -> int`

Refresh a specific window immediately (stage + flush).

```python
from lc_refresh import lc_wrefresh

lc_wrefresh(my_window)
```

### `lc_wnoutrefresh(win: LCWin) -> int`

Stage a specific window into the global desired screen without writing output.

```python
from lc_refresh import lc_wnoutrefresh

lc_wnoutrefresh(my_window)
```

### `lc_doupdate() -> int`

Flush staged desired-screen changes to the terminal.

```python
from lc_refresh import lc_wnoutrefresh, lc_doupdate

lc_wnoutrefresh(win_a)
lc_wnoutrefresh(win_b)
lc_doupdate()
```

---

## Input Settings

### `lc_set_escdelay(ms: int) -> int`

Set the delay for distinguishing ESC key from escape sequences.

```python
from lc_screen import lc_set_escdelay

lc_set_escdelay(25)  # 25ms delay
```

### `lc_nodelay(on: bool) -> int`

Enable or disable non-blocking input mode.

```python
from lc_screen import lc_nodelay

lc_nodelay(True)   # Non-blocking reads
lc_nodelay(False)  # Blocking reads (default)
```

### `lc_meta_esc(on: bool) -> int`

Enable or disable meta-key (Alt) detection via ESC prefix.

```python
from lc_screen import lc_meta_esc

lc_meta_esc(True)   # Enable Alt key detection
lc_meta_esc(False)  # Disable
```

---

## Constants

### Return Codes

```python
from lc_term import LC_OK, LC_ERR

LC_OK  = 0   # Success
LC_ERR = -1  # Failure
```

### Text Attributes

```python
from lc_term import LC_ATTR_NONE, LC_ATTR_BOLD, LC_ATTR_UNDERLINE, LC_ATTR_REVERSE

LC_ATTR_NONE      = 0        # No attributes
LC_ATTR_BOLD      = 1 << 0   # Bold text
LC_ATTR_UNDERLINE = 1 << 1   # Underlined text
LC_ATTR_REVERSE   = 1 << 2   # Reverse video
```

### Key Types

```python
from lc_keys import LC_KT_CHAR, LC_KT_KEYSYM

LC_KT_CHAR   = 1  # Regular character
LC_KT_KEYSYM = 2  # Special key (arrow, function key, etc.)
```

### Modifier Flags

These are bitwise flags that can be combined using bitwise OR to check for multiple modifiers simultaneously (e.g., `LC_MOD_SHIFT | LC_MOD_CTRL` for Shift+Ctrl).

```python
from lc_keys import LC_MOD_SHIFT, LC_MOD_ALT, LC_MOD_CTRL

LC_MOD_SHIFT = 1  # Shift modifier
LC_MOD_ALT   = 2  # Alt/Meta modifier
LC_MOD_CTRL  = 4  # Control modifier

# Example: Check for Ctrl+Shift combination
if key.mods & (LC_MOD_CTRL | LC_MOD_SHIFT) == (LC_MOD_CTRL | LC_MOD_SHIFT):
    print("Ctrl+Shift held")
```

### Key Symbols

```python
from lc_keys import (
    LC_KEY_RESIZE,
    LC_KEY_UP, LC_KEY_DOWN, LC_KEY_RIGHT, LC_KEY_LEFT,
    LC_KEY_HOME, LC_KEY_END,
    LC_KEY_PGUP, LC_KEY_PGDOWN,
    LC_KEY_INSERT, LC_KEY_DELETE,
    LC_KEY_BTAB,
    LC_KEY_F1, LC_KEY_F2, LC_KEY_F3, LC_KEY_F4,
    LC_KEY_F5, LC_KEY_F6, LC_KEY_F7, LC_KEY_F8,
    LC_KEY_F9, LC_KEY_F10, LC_KEY_F11, LC_KEY_F12,
    # Shifted arrows
    LC_KEY_SHIFT_UP, LC_KEY_SHIFT_DOWN,
    LC_KEY_SHIFT_RIGHT, LC_KEY_SHIFT_LEFT,
    LC_KEY_SHIFT_HOME, LC_KEY_SHIFT_END,
    LC_KEY_SHIFT_PGUP, LC_KEY_SHIFT_PGDOWN,
    # Ctrl arrows
    LC_KEY_CTRL_UP, LC_KEY_CTRL_DOWN,
    LC_KEY_CTRL_RIGHT, LC_KEY_CTRL_LEFT,
)
```

---

## Complete Example

```python
from lc_keys import LCKey, lc_readkey, LC_KT_CHAR, LC_KT_KEYSYM, LC_KEY_RESIZE
from lc_refresh import lc_refresh
from lc_screen import (
    lc_session,
    lc_get_size,
    lc_addstr_centered,
    lc_addstr_at,
    lc_draw_box,
)
from lc_window import lc_wclear
from lc_screen import lc

def main():
    with lc_session() as stdscr:
        rows, cols = lc_get_size()
        
        # Draw a border
        lc_draw_box(0, 0, rows, cols)
        
        # Draw centered title
        lc_addstr_centered(0, " My App ")
        
        # Draw instructions
        lc_addstr_at(rows - 1, 2, "Press 'q' to quit")
        
        lc_refresh()
        
        # Main loop
        while True:
            key = LCKey()
            if lc_readkey(key) != 0:
                continue
            
            if key.type == LC_KT_KEYSYM and key.keysym == LC_KEY_RESIZE:
                rows, cols = lc_get_size()
                lc_wclear(lc.stdscr)
                lc_draw_box(0, 0, rows, cols)
                lc_addstr_centered(0, " My App ")
                lc_addstr_at(rows - 1, 2, "Press 'q' to quit")
                lc_refresh()
                continue
            
            if key.type == LC_KT_CHAR and key.rune == ord('q'):
                break

if __name__ == "__main__":
    main()
```
