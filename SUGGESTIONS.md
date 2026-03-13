# Förslag för att lyfta vtpy till något användbart

> This document provides concrete suggestions for elevating vtpy from a well-architected terminal library into a practical, production-ready toolkit for building text-based user interfaces.

## Sammanfattning

vtpy has a solid foundation:
- Clean architecture with explicit backend/core/UI separation
- Well-tested codebase (241 tests passing)
- Explicit contracts and design documentation
- Platform abstraction (POSIX/Windows)
- Diff-based rendering with dirty tracking

The missing pieces to become truly useful are:

1. **Real-world widgets** - Common UI components people actually need
2. **Example applications** - Demonstrating practical use cases
3. **Documentation improvements** - Getting started guide and tutorials
4. **Package distribution** - PyPI availability
5. **Developer experience** - Better error messages and debugging

---

## 1. Praktiska widgets (Priority: HIGH)

### 1.1 Text Input Field

The single most needed widget for any interactive application.

```python
# Proposed API
from vtpy.widgets import InputField

field = InputField(
    id="username",
    placeholder="Enter username...",
    max_length=32,
    password=False,  # Show asterisks instead of chars
)

# In your event handler
def on_submit(value: str):
    print(f"User entered: {value}")

field.on_submit = on_submit
```

**Implementation notes:**
- Cursor position tracking
- Insert/overwrite modes
- Character deletion (backspace, delete)
- Clipboard support (optional)
- Password masking mode

### 1.2 List/Menu Selection

Essential for file browsers, option menus, and command palettes.

```python
from vtpy.widgets import ListBox

items = ["Option A", "Option B", "Option C"]
listbox = ListBox(id="menu", items=items, height=10)

# Current selection
selected = listbox.selected_index
selected_item = listbox.selected_item

# Events
listbox.on_select = lambda idx, item: print(f"Selected: {item}")
```

**Features to include:**
- Keyboard navigation (arrows, page up/down, home/end)
- Scrolling for long lists
- Search/filter as you type (optional)
- Single and multi-select modes

### 1.3 Progress Bar

For long-running operations.

```python
from vtpy.widgets import ProgressBar

progress = ProgressBar(id="download", width=40)
progress.set_value(0.5)  # 50%
progress.set_label("Downloading... 50%")
```

### 1.4 Status Bar

For application chrome.

```python
from vtpy.widgets import StatusBar

status = StatusBar(id="status")
status.set_left("myapp v1.0")
status.set_center("file.txt [modified]")
status.set_right("Line 42, Col 10")
```

### 1.5 Message Dialog

For alerts and confirmations.

```python
from vtpy.widgets import MessageDialog

dialog = MessageDialog(
    title="Confirm",
    message="Save changes before closing?",
    buttons=["Save", "Don't Save", "Cancel"],
)
result = dialog.show()  # Returns button index or -1 if escaped
```

---

## 2. Praktiska exempelapplikationer (Priority: HIGH)

### 2.1 File Browser Demo

A simple two-pane file manager demonstrating:
- Directory listing
- Navigation with arrow keys
- File preview
- Status bar with current path

```
┌─ Left Pane ──────────────┐ ┌─ Right Pane ─────────────┐
│ ..                       │ │ # README.md              │
│ 📁 src/                  │ │                          │
│ 📁 tests/                │ │ This is the content of   │
│ 📄 README.md         ◀   │ │ the selected file shown  │
│ 📄 setup.py              │ │ in the preview pane.     │
│                          │ │                          │
└──────────────────────────┘ └──────────────────────────┘
──────────────────────────────────────────────────────────
/home/user/project                   12 items | 2.3 MB free
```

### 2.2 Log Viewer

A real-time log viewer demonstrating:
- Scrolling text area
- Auto-follow mode
- Search/filter
- Line highlighting

### 2.3 System Monitor

A simple htop-like display showing:
- CPU/memory bars
- Process list
- Refresh on timer
- Resize handling

### 2.4 Simple Text Editor

Basic editor demonstrating:
- Text buffer management
- Cursor movement
- Insert/delete
- Save/load files

---

## 3. Förbättrad dokumentation (Priority: MEDIUM)

### 3.1 Getting Started Guide

A simple tutorial that gets users productive in 5 minutes:

```markdown
# Getting Started with vtpy

## Installation

    pip install vtpy

## Your First App

```python
from vtpy import Session, Label, run

def main():
    with Session() as app:
        label = Label("Hello, vtpy!")
        app.add(label)
        run(app)

if __name__ == "__main__":
    main()
```

## Key Concepts

1. **Session** - Manages terminal state
2. **Views** - UI components
3. **Events** - User input handling
4. **Commands** - Semantic actions
```

### 3.2 API Reference with Examples

Each public function should have:
- Clear description
- Parameter documentation
- Return value documentation
- Code example
- Common pitfalls

### 3.3 Architecture Overview for Contributors

Visual diagram of the module relationships:

```
┌─────────────────────────────────────────────────────────────┐
│                     Your Application                        │
├─────────────────────────────────────────────────────────────┤
│                      UI Runtime                             │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────────────┐   │
│  │ Views   │ │ Events  │ │ Layout  │ │ Focus/Commands  │   │
│  └─────────┘ └─────────┘ └─────────┘ └─────────────────┘   │
├─────────────────────────────────────────────────────────────┤
│                    Terminal Core                            │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────────────┐   │
│  │ Screen  │ │ Window  │ │ Refresh │ │ Keys/Input      │   │
│  └─────────┘ └─────────┘ └─────────┘ └─────────────────┘   │
├─────────────────────────────────────────────────────────────┤
│                    Platform Backend                         │
│           ┌──────────┐         ┌──────────┐                 │
│           │  POSIX   │         │ Windows  │                 │
│           └──────────┘         └──────────┘                 │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. Paketdistribution (Priority: MEDIUM)

### 4.1 PyPI Package

Create proper package structure:

```
vtpy/
├── pyproject.toml
├── src/
│   └── vtpy/
│       ├── __init__.py       # Public API exports
│       ├── core/             # lc_* modules
│       ├── ui/               # ui_* modules
│       ├── backends/         # _posix.py, _win.py
│       └── widgets/          # New widget library
├── tests/
├── examples/
└── docs/
```

### 4.2 pyproject.toml

```toml
[project]
name = "vtpy"
version = "0.1.0"
description = "Explicit, VT-oriented terminal UI library for Python"
readme = "README.md"
license = { text = "MIT" }
requires-python = ">=3.10"
authors = [{ name = "Your Name", email = "you@example.com" }]
keywords = ["terminal", "tui", "ui", "curses", "console"]
classifiers = [
    "Development Status :: 4 - Beta",
    "Environment :: Console",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Operating System :: OS Independent",
    "Programming Language :: Python :: 3",
    "Topic :: Software Development :: User Interfaces",
]

[project.urls]
Homepage = "https://github.com/QzOS/vtpy"
Documentation = "https://vtpy.readthedocs.io"
Repository = "https://github.com/QzOS/vtpy"
```

---

## 5. Förbättrad utvecklarupplevelse (Priority: MEDIUM)

### 5.1 Better Error Messages

Current errors are sometimes cryptic. Improve with:

```python
# Bad:
return -1

# Good:
raise VTPYError(
    "Cannot create subwindow: parent window is not alive. "
    "Ensure parent window has not been freed before creating subwindows."
)
```

### 5.2 Debug Mode

Add optional debug logging:

```python
import vtpy
vtpy.set_debug(True)  # Enables verbose logging

# Or via environment variable
# VTPY_DEBUG=1 python myapp.py
```

### 5.3 Terminal Capability Detection

```python
from vtpy import terminal_info

print(terminal_info.colors)        # 256 or 16 or 8
print(terminal_info.unicode)       # True/False
print(terminal_info.mouse)         # True/False
print(terminal_info.dimensions)    # (rows, cols)
```

---

## 6. Färgstöd (Priority: MEDIUM)

### 6.1 Simple Color API

```python
from vtpy import colors

# Named colors
label.attr = colors.RED | colors.BG_BLUE | colors.BOLD

# RGB (for 256-color/truecolor terminals)
label.attr = colors.fg_rgb(255, 128, 0)  # Orange foreground
label.attr = colors.bg_rgb(32, 32, 32)   # Dark gray background
```

### 6.2 Theme Support

```python
from vtpy.themes import Theme, apply_theme

dark_theme = Theme(
    background=colors.BLACK,
    foreground=colors.WHITE,
    accent=colors.CYAN,
    error=colors.RED,
    warning=colors.YELLOW,
    success=colors.GREEN,
)

apply_theme(app, dark_theme)
```

---

## 7. Layout Förbättringar (Priority: MEDIUM)

The current layout system is basic. Add:

### 7.1 Flex-like Layout

```python
from vtpy.layout import Row, Column, Flex

layout = Column([
    Row([
        Flex(sidebar, weight=1),
        Flex(content, weight=3),
    ], height="auto"),
    StatusBar(height=1),
])
```

### 7.2 Constraint-based Layout

```python
from vtpy.layout import constraints

# Pin to edges
view.constraints = [
    constraints.top(10),
    constraints.left(0),
    constraints.right(0),
    constraints.height(5),
]
```

---

## 8. Händelsehantering (Priority: LOW)

### 8.1 Event Bubbling

```python
# Events bubble up from focused view to root
@view.on("keypress")
def handle_key(event):
    if event.key == "q":
        event.stop_propagation()
        app.quit()
```

### 8.2 Custom Events

```python
from vtpy import Event

# Emit custom events
view.emit(Event("file_selected", path="/path/to/file"))

# Listen for custom events
@app.on("file_selected")
def handle_file_selected(event):
    open_file(event.path)
```

---

## 9. Prestanda (Priority: LOW)

### 9.1 Virtual Scrolling for Large Lists

For lists with thousands of items:

```python
listbox = ListBox(
    id="files",
    items=all_files,  # 100,000 items
    virtual=True,     # Only render visible items
)
```

### 9.2 Incremental Updates

Only redraw changed portions:

```python
# Current: full subtree redraw on any change
# Proposed: cell-level dirty tracking with minimal refresh
```

---

## 10. Integration (Priority: LOW)

### 10.1 asyncio Support

```python
import asyncio
from vtpy.async_runtime import AsyncApp

async def main():
    app = AsyncApp()
    
    # Non-blocking operations
    result = await fetch_data()
    label.text = result
    
    await app.run()

asyncio.run(main())
```

### 10.2 Mouse Support

```python
from vtpy import MouseEvent

@view.on("mouse")
def handle_mouse(event: MouseEvent):
    if event.button == 1:  # Left click
        select_at(event.x, event.y)
```

---

## Implementationsordning

Based on impact vs effort, recommended order:

### Phase 1: Make it Usable (1-2 weeks)
1. ✅ Input field widget
2. ✅ List/selection widget  
3. ✅ Simple file browser example
4. ✅ Getting started documentation

### Phase 2: Make it Distributable (1 week)
1. ✅ Package structure reorganization
2. ✅ pyproject.toml setup
3. ✅ PyPI publishing

### Phase 3: Make it Pleasant (2-3 weeks)
1. ✅ Color support
2. ✅ Better error messages
3. ✅ More example applications
4. ✅ Progress bar, status bar widgets

### Phase 4: Make it Powerful (Ongoing)
1. ⬜ Async support
2. ⬜ Mouse support
3. ⬜ Advanced layout
4. ⬜ Themes

---

## Konkreta första steg

To start immediately:

### 1. Create `vtpy/widgets/input_field.py`

```python
"""Simple single-line text input widget."""

from dataclasses import dataclass, field
from typing import Optional, Callable

from ui_view import UIView, ui_view_create, UI_VIEWKIND_GENERIC
from ui_event import UIEvent, UI_EVENT_KEY, UI_CMD_NONE, UI_CMD_REDRAW
from lc_window import lc_wmove, lc_wput, lc_wfill
from lc_term import LC_ATTR_REVERSE

UI_VIEWKIND_INPUT = 100


@dataclass
class InputField(UIView):
    """Single-line text input field."""
    
    value: str = ""
    cursor_pos: int = 0
    placeholder: str = ""
    max_length: int = 256
    password: bool = False
    on_change: Optional[Callable[[str], None]] = None
    on_submit: Optional[Callable[[str], None]] = None
    
    def __post_init__(self):
        self.kind = UI_VIEWKIND_INPUT
        self.flags |= UI_VIEW_FOCUSABLE
    
    def handle_event(self, ev: UIEvent) -> int:
        if ev.type != UI_EVENT_KEY:
            return UI_CMD_NONE
        
        ch = ev.rune
        
        # Enter submits
        if ch == ord('\n') or ch == ord('\r'):
            if self.on_submit:
                self.on_submit(self.value)
            return UI_CMD_NONE
        
        # Backspace
        if ch == 127 or ch == 8:
            if self.cursor_pos > 0:
                self.value = (
                    self.value[:self.cursor_pos-1] + 
                    self.value[self.cursor_pos:]
                )
                self.cursor_pos -= 1
                self._notify_change()
            return UI_CMD_REDRAW
        
        # Printable character
        if 32 <= ch < 127:
            if len(self.value) < self.max_length:
                self.value = (
                    self.value[:self.cursor_pos] + 
                    chr(ch) + 
                    self.value[self.cursor_pos:]
                )
                self.cursor_pos += 1
                self._notify_change()
            return UI_CMD_REDRAW
        
        return UI_CMD_NONE
    
    def _notify_change(self):
        if self.on_change:
            self.on_change(self.value)
    
    def draw_self(self) -> int:
        if self.bound_win is None:
            return -1
        
        # Clear background
        lc_wfill(self.bound_win, 0, 0, 1, self.content_rect.width, ' ', 0)
        
        # Draw value or placeholder
        display = self.value if self.value else self.placeholder
        if self.password and self.value:
            display = '*' * len(self.value)
        
        # Write visible portion
        width = self.content_rect.width
        start = max(0, self.cursor_pos - width + 1)
        visible = display[start:start + width]
        
        lc_wmove(self.bound_win, 0, 0)
        for i, ch in enumerate(visible):
            attr = LC_ATTR_REVERSE if (start + i == self.cursor_pos and self.has_focus) else 0
            lc_wput(self.bound_win, ord(ch), attr)
        
        # Draw cursor if at end
        if self.has_focus and self.cursor_pos >= len(display):
            cursor_x = min(len(visible), width - 1)
            lc_wmove(self.bound_win, 0, cursor_x)
            lc_wput(self.bound_win, ord(' '), LC_ATTR_REVERSE)
        
        return 0
```

### 2. Create `examples/file_browser.py`

A working file browser that demonstrates the library's capabilities.

### 3. Create `docs/getting_started.md`

Simple tutorial with copy-paste examples.

---

## Slutsats

vtpy has excellent architectural foundations. The path to usefulness is:

1. **Add practical widgets** that solve real problems
2. **Show working examples** that inspire confidence
3. **Package properly** for easy installation
4. **Document clearly** for quick adoption

The library doesn't need more internal refactoring—it needs user-facing features and polish. Focus on making it easy to build something useful today, not on achieving architectural perfection.

---

*Created: 2024*
*Author: GitHub Copilot Analysis*
