# vtpy README

This document is for us, not for users. The goal is to state clearly what is being built, what is intentionally not being built yet, and what contracts the code is supposed to obey.

## 1. What this library is

vtpy is a Python terminal library built around a simple idea:

- terminal I/O is a byte stream plus a character-cell screen model
- rendering is explicit and diff-based
- input decoding is explicit and protocol-aware
- platform-specific terminal control belongs in backends
- higher-level semantics belong in OS-neutral core code
- reference design for a future OS-native text ui runtime

This is not a wrapper around curses.
This is not trying to pretend ncurses history never happened either.
The point is to build a terminal library with clear internal contracts, modern enough to live comfortably in VT/xterm-style terminals, and structured so that POSIX and Windows can both exist under the same core model.

## 2. What this library is not

At the current stage, vtpy is not:

- a drop-in curses clone
- a full terminal capability database
- a Unicode-width-correct rendering engine
- a widget toolkit
- a portability layer for arbitrary historical terminals
- a complete window hierarchy system

Those may become future directions, but they are not current promises.

## 3. Current architecture

The codebase is split into two broad layers.

### 3.1 OS-neutral core

These modules define the main behavior of the library:

- `lc_window.py` - in-memory window and cell model, dirty tracking, drawing primitives
- `lc_refresh.py` - diff-based screen refresh and batching
- `lc_keys.py` - input parser from byte stream to chars/keysyms
- `lc_term.py` - VT/ANSI sequence encoding and terminal-output helpers
- `lc_screen.py` - public API and overall state orchestration

These modules should not depend on POSIX or Win32 details except through the backend contract.

### 3.2 Platform backends

These modules own platform-specific terminal control:

- `_posix.py`
- `_win.py`
- `lc_platform.py` chooses the active backend

Backends are responsible for:

- terminal mode setup/restore
- raw/cbreak/echo semantics for that platform
- terminal size discovery
- input-byte acquisition
- resize observation

Backends are not responsible for:

- screen diffing
- key decoding above byte-stream level
- window clipping semantics
- rendering policy

## 4. Current data model

### 4.1 Cell model

A cell currently contains:

- `ch: str`
- `attr: int`

This is a character-cell model, not a grapheme-cluster model.

### 4.2 Row model

Each row contains:

- a list of cells
- `firstch` / `lastch`
- dirty flags

Dirty ranges are the basic repaint unit inside the window layer.

### 4.3 Window model

A window may be either a root backing store or a derived subwindow.

A window currently contains:

- dimensions: `maxy`, `maxx`
- origin relative to the screen: `begy`, `begx`
- cursor: `cury`, `curx`
- row storage
- optional parent/root relationship
- parent-relative origin: `pary`, `parx`
- lifecycle state: `alive`
- child list for recursive teardown

Subwindows share backing cells with their parent. They do not own independent cell storage.

## 5. Core contracts

## 5.1 Backend contract

The backend contract is byte-oriented.

Required functions:

- `init(state) -> int`
- `end(state) -> int`
- `get_size(state) -> (rows, cols)`
- `read_byte(state) -> int | None`
- `unread_byte(state, ch) -> None`
- `input_pending(state, timeout_ms) -> bool`
- `poll_resize(state) -> bool`
- `clear_resize(state) -> None`
- `apply_term(state) -> int`
- `raw(state) -> int`
- `noraw(state) -> int`
- `cbreak(state) -> int`
- `nocbreak(state) -> int`
- `echo(state) -> int`
- `noecho(state) -> int`

### Backend semantic rules

- `read_byte()` returns one byte-equivalent integer in range `0..255`, or `None` on EOF/error/unavailable terminal failure.
- `unread_byte()` provides one-byte pushback semantics.
- `input_pending()` means keyboard/input-byte readiness only. A pending resize alone must not make it return `True`.
- `poll_resize()` means a real terminal size change is pending observation by the core.
- `clear_resize()` clears backend resize state after the core has consumed it.
- Backends must not leak platform-specific input events into the core except as byte stream plus resize notification.

### Backend semantic consequences

This means:

- UTF-8 decoding belongs above the backend
- VT/CSI/SS3 parsing belongs above the backend
- Windows-specific key events must be translated into byte-stream-compatible form where practical
- POSIX stays raw-byte-oriented

## 5.2 Screen/state contract

`lc_screen.py` owns the public mutable runtime state.

This state is responsible for coordinating:

- active screen size
- current stdscr window
- render cache
- current cursor/attr output state
- input settings such as ESC delay, nodelay, meta handling

The public API should remain platform-neutral.

## 5.3 Window semantics contract

The window layer owns logical drawing semantics.

### Strict operations

These are strict and return `-1` on invalid coordinates:

- `lc_wmove()`
- APIs that depend on an already-valid cursor and cannot sensibly clip from nowhere

### Clipped operations

These clip against the window bounds and return `0` for valid operations even when the result is partial or fully invisible:

- `fill_rect()`
- `lc_waddstr()`
- `lc_wdraw_hline()`
- `lc_wdraw_vline()`
- `lc_wdraw_box()`

### Invariant

No window operation may read or write outside the window backing store.

## 5.4 Subwindow semantics contract

Subwindows are now part of the intended core model.

### Current subwindow rules

- `lc_subwin(parent, ...)` creates a child window in parent-relative coordinates.
- Subwindows share `LCCell` objects with the parent backing store.
- Writes through a subwindow must be visible through the parent and vice versa.
- Dirty tracking must propagate upward from child to parent chain.
- A child window is lifecycle-owned by its parent.

### Lifecycle rules

- Every window has an `alive` state.
- Operations on dead windows return `-1` where the operation normally reports failure, or act as no-op only for internal helpers that are intentionally silent.
- `lc_free(parent)` recursively frees the full child subtree first.
- A child cannot outlive its parent.

### Resize rule

Subwindows are tied to the current backing-store topology.
When the root window is resized, all existing subwindows are invalidated and freed.
Applications must rebuild derived windows after observing `LC_KEY_RESIZE`.

### Panel/content helper rules

- `lc_panel_content_rect(...)` returns the interior content rect for a boxed panel.
- `lc_panel_subwin(...)` creates a derived subwindow for that interior.
- Panel-content subwindows are ordinary subwindows and therefore follow the same lifecycle and resize rules.

## 5.5 Refresh semantics contract

The refresh layer compares window contents against a cached screen image and emits only changes.

Refresh is allowed to clip against physical screen bounds.
Window drawing is not.

That distinction matters:

- window clipping protects logical backing storage
- refresh clipping protects terminal output bounds

## 6. Current text model

The current text/input/rendering model is deliberately simple.

### Current truth

- input arrives as bytes
- UTF-8 is decoded in `lc_keys.py`
- cells currently store a Python `str` character
- rendering uses `str.encode('utf-8', 'replace')`
- screen advancement is still effectively one stored character per cell

### What is not solved yet

The library does not yet have a final answer for:

- wide characters
- combining characters
- grapheme clusters
- true display-width accounting

This is an intentional simplification for now. The current practical assumption is close to:

- one stored character occupies one logical cell

That assumption will eventually need revision if the library moves toward serious Unicode layout correctness.

## 7. Current clipping/geometry helpers

Internal geometry helpers now exist to make future semantics less ad hoc:

- `_clip_range()`
- `_clip_hspan()`
- `_clip_vspan()`
- `_clip_rect()`
- `_normalize_rect()`
- `_box_edges()`
- `_interior_rect()`

These are internal for now. They exist to give names to recurring rectangle logic and reduce repeated coordinate arithmetic.

The purpose is not abstraction for abstraction's sake. The purpose is to make later steps, such as titled boxes, content rects, and subwindow clipping, easier to implement without duplicating geometry logic in multiple public functions.

## 8. Resize model

Resize is modeled as an event-like condition surfaced through the backend and consumed by the core.

### Current flow

- backend notices resize
- backend reports `poll_resize() == True`
- core checks actual size
- core rebuilds stdscr and cached screen state
- key layer emits `LC_KEY_RESIZE`

### Important rule

A resize is not treated as input-byte readiness.
That is why `input_pending()` must not become `True` merely because a resize happened.

## 9. What is currently stable enough to rely on

These parts are stable enough to be treated as the current intended model:

- byte-oriented backend interface
- screen/state/backend separation
- diff-based refresh model
- dirty row/cell repainting
- clipped drawing primitives
- resize surfaced as `LC_KEY_RESIZE`
- shared-backing subwindows with upward dirty propagation
- panel-content subwindow helpers

## 10. What is still in motion

These areas are still under active design and should not yet be treated as frozen API truth:

- Unicode cell-width semantics
- whether future window types should include copied-backing windows in addition to shared-backing subwindows
- richer panel/header/content zoning
- richer attribute and color model
- broader terminal capability modeling beyond current VT-oriented assumptions
- resize-preserving child/window topologies, if we ever choose to support them

## 11. Likely next steps

The most likely near-term directions are:

### 11.1 Better panel zoning

Now that panel content rects and content subwindows exist, the next logical step is to formalize optional header bands or other internal panel regions without reintroducing ad hoc coordinate math.

### 11.2 Copied-backing versus shared-backing policy

At some point the project may need to choose explicitly whether every derived window remains shared-backing, or whether some future window types should own copied backing storage instead.

### 11.3 Unicode policy

At some point the project must choose explicitly between:

- a strict one-character/one-cell model
- a width-aware model
- a grapheme-aware model

Avoid drifting into accidental half-support.

### 11.4 Richer attributes

The current attribute model is intentionally thin. If the library grows up into more serious UI work, colors and richer style composition will need their own explicit contract rather than being implied piecemeal.

## 12. Development principles for this codebase

These are the working rules we should use when changing the library.

- Prefer explicit contracts over convenience folklore.
- Prefer small internal helpers over duplicated coordinate math.
- Keep platform details in backends.
- Keep parser logic above the backend.
- Keep clipping semantics consistent within operation families.
- Do not quietly broaden semantics without writing them down here.
- Do not fake support for things the model does not yet truly handle.

## 13. Short version

We are building:

- a Python terminal library
- with a byte-oriented backend contract
- a VT-oriented rendering and input model
- a window/cell backing-store core
- diff-based refresh
- explicit clipping semantics
- platform-specific backends under a platform-neutral public API

We are not yet building:

- full curses compatibility
- full Unicode layout correctness
- full terminal capability abstraction
- full window hierarchy semantics

That is the current truth.
