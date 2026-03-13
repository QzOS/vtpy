"""
Example: Simple File Browser

A two-pane file browser demonstrating vtpy's capabilities:
- ListBox widget for file listing
- Panel layout with borders
- Keyboard navigation
- Status bar

Usage:
    python examples/file_browser.py

Controls:
    UP/DOWN, j/k  - Navigate list
    ENTER         - Enter directory / view file info
    BACKSPACE     - Go to parent directory
    q             - Quit
"""

import os
import stat
from pathlib import Path

from lc_keys import (
    LCKey,
    lc_readkey,
    LC_KT_CHAR,
    LC_KT_KEYSYM,
    LC_KEY_RESIZE,
    LC_KEY_UP,
    LC_KEY_DOWN,
    LC_KEY_BACKSPACE,
)
from lc_refresh import lc_refresh
from lc_screen import (
    lc,
    lc_session,
    lc_get_size,
    lc_addstr_at,
    lc_addstr_centered,
    lc_draw_box,
)
from lc_window import lc_wclear, lc_wfill, lc_subwin, lc_wmove, lc_wput, lc_waddstr
from lc_term import LC_ATTR_REVERSE, LC_ATTR_BOLD, LC_ATTR_NONE


class FileBrowser:
    """Simple two-pane file browser."""
    
    def __init__(self):
        self.current_path = Path.cwd()
        self.files: list[Path] = []
        self.selected_index = 0
        self.scroll_offset = 0
        self.status_message = ""
        self.running = True
    
    def load_directory(self) -> None:
        """Load files from current directory."""
        try:
            entries = list(self.current_path.iterdir())
            # Sort: directories first, then files
            dirs = sorted([e for e in entries if e.is_dir()], key=lambda p: p.name.lower())
            files = sorted([e for e in entries if e.is_file()], key=lambda p: p.name.lower())
            self.files = dirs + files
        except PermissionError:
            self.files = []
            self.status_message = "Permission denied"
        except Exception as e:
            self.files = []
            self.status_message = str(e)
        
        self.selected_index = 0
        self.scroll_offset = 0
    
    def get_file_info(self, path: Path) -> str:
        """Get human-readable file info."""
        try:
            st = path.stat()
            size = st.st_size
            if size < 1024:
                size_str = f"{size} B"
            elif size < 1024 * 1024:
                size_str = f"{size // 1024} KB"
            else:
                size_str = f"{size // (1024 * 1024)} MB"
            
            if path.is_dir():
                return f"Directory"
            return f"{size_str}"
        except:
            return "?"
    
    def format_entry(self, path: Path, width: int) -> str:
        """Format a file entry for display."""
        name = path.name
        if path.is_dir():
            name = "[DIR] " + name + "/"
        else:
            # Use simple extension-based indicators
            ext = path.suffix.lower()
            if ext in ('.py', '.pyw'):
                name = "[PY]  " + name
            elif ext in ('.txt', '.md', '.rst'):
                name = "[TXT] " + name
            elif ext in ('.json', '.yaml', '.yml', '.toml'):
                name = "[CFG] " + name
            else:
                name = "      " + name
        
        # Truncate if needed
        if len(name) > width - 2:
            name = name[:width - 5] + "..."
        
        return name
    
    def draw(self) -> None:
        """Draw the entire UI."""
        rows, cols = lc_get_size()
        
        # Clear screen
        lc_wclear(lc.stdscr)
        
        # Calculate layout
        list_width = min(cols // 2, 50)
        info_width = cols - list_width
        list_height = rows - 3  # Leave room for title and status
        
        # Draw outer border
        lc_draw_box(0, 0, rows, cols)
        
        # Draw title
        title = f" File Browser: {self.current_path} "
        if len(title) > cols - 4:
            title = f" {self.current_path.name} "
        lc_addstr_centered(0, title)
        
        # Draw vertical divider
        for row in range(1, rows - 2):
            lc_addstr_at(row, list_width, "│")
        
        # Draw file list
        self._draw_file_list(1, 1, list_height, list_width - 2)
        
        # Draw info panel
        self._draw_info_panel(1, list_width + 1, list_height, info_width - 2)
        
        # Draw status bar
        self._draw_status_bar(rows - 1, 1, cols - 2)
        
        lc_refresh()
    
    def _draw_file_list(self, y: int, x: int, height: int, width: int) -> None:
        """Draw the file listing panel."""
        # Ensure selected item is visible
        if self.selected_index < self.scroll_offset:
            self.scroll_offset = self.selected_index
        elif self.selected_index >= self.scroll_offset + height:
            self.scroll_offset = self.selected_index - height + 1
        
        # Draw parent directory entry
        if y < height:
            is_first = (self.selected_index == -1)
            # We don't use -1 for parent, just show it differently
        
        # Draw files
        for i in range(height):
            file_index = self.scroll_offset + i
            row = y + i
            
            if file_index >= len(self.files):
                break
            
            path = self.files[file_index]
            text = self.format_entry(path, width)
            
            # Pad to width
            text = text.ljust(width)
            
            # Highlight selected
            if file_index == self.selected_index:
                attr = LC_ATTR_REVERSE | LC_ATTR_BOLD
            else:
                attr = LC_ATTR_NONE
            
            # Draw the row - use different method for highlighted vs normal
            if attr == LC_ATTR_NONE:
                for col, ch in enumerate(text[:width]):
                    lc_addstr_at(row, x + col, ch)
            else:
                # For highlighted row, use attribute
                lc_wmove(lc.stdscr, row, x)
                for ch in text[:width]:
                    lc_wput(lc.stdscr, ord(ch), attr)
        
        # Show scroll indicators if needed
        if self.scroll_offset > 0:
            lc_addstr_at(y, x + width - 1, "^")
        if self.scroll_offset + height < len(self.files):
            lc_addstr_at(y + height - 1, x + width - 1, "v")
    
    def _draw_info_panel(self, y: int, x: int, height: int, width: int) -> None:
        """Draw the info panel for selected file."""
        if not self.files or self.selected_index >= len(self.files):
            lc_addstr_at(y, x, "(empty)")
            return
        
        path = self.files[self.selected_index]
        
        # File name
        lc_addstr_at(y, x, "Name:")
        lc_addstr_at(y + 1, x + 2, path.name[:width - 2])
        
        # Type
        lc_addstr_at(y + 3, x, "Type:")
        if path.is_dir():
            type_str = "Directory"
        elif path.is_symlink():
            type_str = "Symbolic Link"
        else:
            type_str = f"File ({path.suffix or 'no extension'})"
        lc_addstr_at(y + 4, x + 2, type_str[:width - 2])
        
        # Size
        try:
            st = path.stat()
            size = st.st_size
            if size < 1024:
                size_str = f"{size} bytes"
            elif size < 1024 * 1024:
                size_str = f"{size / 1024:.1f} KB"
            elif size < 1024 * 1024 * 1024:
                size_str = f"{size / (1024 * 1024):.1f} MB"
            else:
                size_str = f"{size / (1024 * 1024 * 1024):.1f} GB"
            
            lc_addstr_at(y + 6, x, "Size:")
            lc_addstr_at(y + 7, x + 2, size_str)
        except:
            pass
        
        # Preview for text files
        if path.is_file() and path.suffix.lower() in ('.txt', '.md', '.py', '.json', '.yaml', '.toml', '.rst'):
            lc_addstr_at(y + 9, x, "Preview:")
            try:
                with open(path, 'r', errors='replace') as f:
                    preview_lines = f.readlines()[:height - 11]
                for i, line in enumerate(preview_lines):
                    line = line.rstrip()[:width - 2]
                    lc_addstr_at(y + 10 + i, x + 2, line)
            except:
                lc_addstr_at(y + 10, x + 2, "(unable to read)")
    
    def _draw_status_bar(self, row: int, x: int, width: int) -> None:
        """Draw the status bar."""
        left = f" {len(self.files)} items"
        right = "q:quit  ↑↓:nav  Enter:open  Backspace:up "
        
        middle = self.status_message if self.status_message else ""
        
        # Build status line
        line = left + " " * (width - len(left) - len(right) - len(middle)) + middle + right
        line = line[:width]
        
        lc_addstr_at(row, x, line)
    
    def handle_key(self, key: LCKey) -> None:
        """Handle keyboard input."""
        self.status_message = ""
        
        if key.type == LC_KT_KEYSYM:
            if key.keysym == LC_KEY_UP:
                if self.selected_index > 0:
                    self.selected_index -= 1
            elif key.keysym == LC_KEY_DOWN:
                if self.selected_index < len(self.files) - 1:
                    self.selected_index += 1
            elif key.keysym == LC_KEY_BACKSPACE:
                # Go to parent directory
                parent = self.current_path.parent
                if parent != self.current_path:
                    self.current_path = parent
                    self.load_directory()
        
        elif key.type == LC_KT_CHAR:
            ch = chr(key.rune) if 32 <= key.rune < 127 else ''
            
            if ch == 'q':
                self.running = False
            elif ch == 'j':  # vim-style down
                if self.selected_index < len(self.files) - 1:
                    self.selected_index += 1
            elif ch == 'k':  # vim-style up
                if self.selected_index > 0:
                    self.selected_index -= 1
            elif ch == 'g':  # go to top
                self.selected_index = 0
            elif ch == 'G':  # go to bottom
                self.selected_index = max(0, len(self.files) - 1)
            elif key.rune == ord('\n') or key.rune == ord('\r'):
                # Enter directory or show file info
                if self.files and 0 <= self.selected_index < len(self.files):
                    path = self.files[self.selected_index]
                    if path.is_dir():
                        self.current_path = path
                        self.load_directory()
                    else:
                        self.status_message = f"Selected: {path.name}"
            elif key.rune == 127 or key.rune == 8:  # Backspace
                parent = self.current_path.parent
                if parent != self.current_path:
                    self.current_path = parent
                    self.load_directory()
    
    def run(self) -> None:
        """Main event loop."""
        self.load_directory()
        
        with lc_session():
            self.draw()
            
            while self.running:
                key = LCKey()
                rc = lc_readkey(key)
                
                if rc != 0:
                    continue
                
                if key.type == LC_KT_KEYSYM and key.keysym == LC_KEY_RESIZE:
                    # Handle resize
                    self.draw()
                    continue
                
                self.handle_key(key)
                self.draw()


def main():
    """Entry point."""
    browser = FileBrowser()
    browser.run()


if __name__ == "__main__":
    main()
