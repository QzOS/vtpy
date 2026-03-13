"""
Single-line text input widget.

Provides a focusable text input field with cursor movement, character
insertion/deletion, and optional password masking.
"""

from dataclasses import dataclass, field
from typing import Optional, Callable

from ui_view import (
    UIView,
    ui_view_create,
    ui_view_mark_dirty,
    UI_VIEWKIND_GENERIC,
    UI_VIEW_VISIBLE,
    UI_VIEW_ENABLED,
    UI_VIEW_FOCUSABLE,
    UI_VIEW_DIRTY,
)
from ui_event import (
    UIEvent,
    UI_EVENT_KEY,
    UI_CMD_NONE,
    UI_CMD_REDRAW,
)
from lc_keys import (
    LC_KT_CHAR,
    LC_KT_KEYSYM,
    LC_KEY_LEFT,
    LC_KEY_RIGHT,
    LC_KEY_HOME,
    LC_KEY_END,
    LC_KEY_DELETE,
)
from lc_window import lc_wmove, lc_wput, lc_wfill
from lc_term import LC_ATTR_NONE, LC_ATTR_REVERSE


UI_VIEWKIND_INPUT = 100


@dataclass
class InputField:
    """
    Single-line text input field widget.
    
    Attributes:
        id: Unique identifier for this input field
        value: Current text value
        cursor_pos: Current cursor position within value
        placeholder: Text shown when value is empty
        max_length: Maximum allowed input length
        password: If True, show asterisks instead of actual characters
        on_change: Callback when value changes, receives new value
        on_submit: Callback when Enter is pressed, receives final value
    
    Usage:
        field = InputField(id="username", placeholder="Enter name...")
        field.on_submit = lambda val: print(f"Submitted: {val}")
    """
    id: str = ""
    value: str = ""
    cursor_pos: int = 0
    placeholder: str = ""
    max_length: int = 256
    password: bool = False
    on_change: Optional[Callable[[str], None]] = None
    on_submit: Optional[Callable[[str], None]] = None
    
    # Internal view state (managed by UI runtime)
    _view: Optional[UIView] = field(default=None, repr=False)
    
    def __post_init__(self) -> None:
        """Initialize the internal view state."""
        pass
    
    def set_value(self, value: str) -> None:
        """Set the input value and reset cursor to end."""
        if value is None:
            value = ""
        if len(value) > self.max_length:
            value = value[:self.max_length]
        self.value = value
        self.cursor_pos = len(value)
        self._notify_change()
        self._mark_dirty()
    
    def clear(self) -> None:
        """Clear the input value."""
        self.value = ""
        self.cursor_pos = 0
        self._notify_change()
        self._mark_dirty()
    
    def handle_key_event(self, key_type: int, rune: int, keysym: int, mods: int) -> int:
        """
        Handle a key event.
        
        Returns UI_CMD_REDRAW if the field was modified, UI_CMD_NONE otherwise.
        """
        # Handle keysyms (arrow keys, home, end, etc.)
        if key_type == LC_KT_KEYSYM:
            return self._handle_keysym(keysym, mods)
        
        # Handle character input
        if key_type == LC_KT_CHAR:
            return self._handle_char(rune, mods)
        
        return UI_CMD_NONE
    
    def _handle_keysym(self, keysym: int, mods: int) -> int:
        """Handle special key events."""
        if keysym == LC_KEY_LEFT:
            if self.cursor_pos > 0:
                self.cursor_pos -= 1
                return UI_CMD_REDRAW
            return UI_CMD_NONE
        
        if keysym == LC_KEY_RIGHT:
            if self.cursor_pos < len(self.value):
                self.cursor_pos += 1
                return UI_CMD_REDRAW
            return UI_CMD_NONE
        
        if keysym == LC_KEY_HOME:
            if self.cursor_pos != 0:
                self.cursor_pos = 0
                return UI_CMD_REDRAW
            return UI_CMD_NONE
        
        if keysym == LC_KEY_END:
            if self.cursor_pos != len(self.value):
                self.cursor_pos = len(self.value)
                return UI_CMD_REDRAW
            return UI_CMD_NONE
        
        if keysym == LC_KEY_DELETE:
            if self.cursor_pos < len(self.value):
                self.value = (
                    self.value[:self.cursor_pos] +
                    self.value[self.cursor_pos + 1:]
                )
                self._notify_change()
                return UI_CMD_REDRAW
            return UI_CMD_NONE
        
        return UI_CMD_NONE
    
    def _handle_char(self, rune: int, mods: int) -> int:
        """Handle character input."""
        # Enter key submits
        if rune == ord('\n') or rune == ord('\r'):
            if self.on_submit is not None:
                self.on_submit(self.value)
            return UI_CMD_NONE
        
        # Backspace (some terminals send this as char)
        if rune == 127 or rune == 8:
            if self.cursor_pos > 0:
                self.value = (
                    self.value[:self.cursor_pos - 1] +
                    self.value[self.cursor_pos:]
                )
                self.cursor_pos -= 1
                self._notify_change()
                return UI_CMD_REDRAW
            return UI_CMD_NONE
        
        # Escape - could be used to cancel
        if rune == 27:
            return UI_CMD_NONE
        
        # Tab - could be used for focus navigation
        if rune == 9:
            return UI_CMD_NONE
        
        # Printable ASCII characters
        if 32 <= rune < 127:
            if len(self.value) < self.max_length:
                ch = chr(rune)
                self.value = (
                    self.value[:self.cursor_pos] +
                    ch +
                    self.value[self.cursor_pos:]
                )
                self.cursor_pos += 1
                self._notify_change()
                return UI_CMD_REDRAW
            return UI_CMD_NONE
        
        return UI_CMD_NONE
    
    def _notify_change(self) -> None:
        """Call the on_change callback if set."""
        if self.on_change is not None:
            self.on_change(self.value)
    
    def _mark_dirty(self) -> None:
        """Mark the associated view as dirty if it exists."""
        if self._view is not None:
            ui_view_mark_dirty(self._view)
    
    def get_display_text(self) -> str:
        """Get the text to display (handles password masking)."""
        if self.value:
            if self.password:
                return '*' * len(self.value)
            return self.value
        return self.placeholder
    
    def get_visible_range(self, width: int) -> tuple[int, int]:
        """
        Calculate the visible character range for scrolling.
        
        Returns (start_index, end_index) of the visible portion.
        """
        if width <= 0:
            return (0, 0)
        
        text_len = len(self.value)
        
        # Ensure cursor is always visible
        if self.cursor_pos < width:
            # Cursor fits without scrolling
            start = 0
        else:
            # Scroll so cursor is at the right edge
            start = self.cursor_pos - width + 1
        
        end = min(start + width, text_len)
        return (start, end)


def input_field_create(
    view_id: str,
    y: int,
    x: int,
    width: int,
    placeholder: str = "",
    password: bool = False,
    max_length: int = 256,
) -> tuple[UIView, InputField]:
    """
    Create an InputField with its associated UIView.
    
    Args:
        view_id: Unique identifier for the view
        y: Vertical position (row)
        x: Horizontal position (column)
        width: Width of the input field
        placeholder: Placeholder text when empty
        password: Whether to mask input
        max_length: Maximum input length
    
    Returns:
        Tuple of (UIView, InputField) for integration with UI runtime
    
    Usage:
        view, field = input_field_create("username", 5, 10, 30)
        field.on_submit = lambda val: save_username(val)
        ui_view_add_child(root, view)
    """
    # Create the view
    flags = UI_VIEW_VISIBLE | UI_VIEW_ENABLED | UI_VIEW_FOCUSABLE | UI_VIEW_DIRTY
    view = ui_view_create(
        view_id=view_id,
        y=y,
        x=x,
        height=1,  # Single line
        width=width,
        focusable=True,
        panel=False,
        container=False,
        kind=UI_VIEWKIND_INPUT,
    )
    
    # Create the input field
    input_field = InputField(
        id=view_id,
        placeholder=placeholder,
        password=password,
        max_length=max_length,
    )
    input_field._view = view
    
    # Store reference in user_data
    view.user_data = input_field
    
    return view, input_field


def input_field_draw(view: UIView, has_focus: bool) -> int:
    """
    Draw an InputField into its bound window.
    
    Args:
        view: The UIView containing the InputField
        has_focus: Whether the field currently has focus
    
    Returns:
        0 on success, -1 on error
    """
    if view is None or view.bound_win is None:
        return -1
    
    if view.user_data is None:
        return -1
    
    field = view.user_data
    if not isinstance(field, InputField):
        return -1
    
    win = view.bound_win
    width = view.content_rect.width
    
    if width <= 0:
        return 0
    
    # Clear the line
    if lc_wfill(win, 0, 0, 1, width, ' ', LC_ATTR_NONE) != 0:
        return -1
    
    # Get display text
    display_text = field.get_display_text()
    is_placeholder = (field.value == "" and field.placeholder != "")
    
    # Calculate visible range
    start, end = field.get_visible_range(width)
    
    # Handle placeholder vs value display
    if is_placeholder:
        visible = field.placeholder[:width]
        # Draw placeholder in dim/italic style (using underline as fallback)
        lc_wmove(win, 0, 0)
        for ch in visible:
            lc_wput(win, ord(ch), LC_ATTR_NONE)
    else:
        # Draw value with cursor
        visible = field.value[start:end] if field.value else ""
        cursor_in_visible = field.cursor_pos - start
        
        lc_wmove(win, 0, 0)
        for i, ch in enumerate(visible):
            if has_focus and i == cursor_in_visible:
                # Draw cursor position with reverse video
                if field.password:
                    lc_wput(win, ord('*'), LC_ATTR_REVERSE)
                else:
                    lc_wput(win, ord(ch), LC_ATTR_REVERSE)
            else:
                if field.password:
                    lc_wput(win, ord('*'), LC_ATTR_NONE)
                else:
                    lc_wput(win, ord(ch), LC_ATTR_NONE)
        
        # If cursor is past the text, draw it as a space
        if has_focus and cursor_in_visible >= len(visible) and cursor_in_visible < width:
            lc_wmove(win, 0, len(visible))
            lc_wput(win, ord(' '), LC_ATTR_REVERSE)
    
    return 0


def input_field_handle_event(view: UIView, ev: UIEvent) -> int:
    """
    Handle an event for an InputField.
    
    Args:
        view: The UIView containing the InputField
        ev: The event to handle
    
    Returns:
        Command code (UI_CMD_REDRAW if changed, UI_CMD_NONE otherwise)
    """
    if view is None or ev is None:
        return UI_CMD_NONE
    
    if view.user_data is None:
        return UI_CMD_NONE
    
    field = view.user_data
    if not isinstance(field, InputField):
        return UI_CMD_NONE
    
    if ev.type != UI_EVENT_KEY:
        return UI_CMD_NONE
    
    if ev.key is None:
        return UI_CMD_NONE
    
    return field.handle_key_event(ev.key.type, ev.key.rune, ev.key.keysym, ev.key.mods)
