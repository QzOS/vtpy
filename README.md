# vtpy README

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
- top-level root identity: `root`
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

### Root identity rule

Every live window has a non-`None` `root`.

That means:

- for a top-level window, `root is self`
- for a derived window, `root` names the top-level backing root
- `parent is None` means the window is top-level
- `root is self` means the window is the top-level root object for its current backing topology
- dead windows clear `root`

### Cursor progression rule

The current cursor policy is saturating at the last writable cell.

That means:

- writing at any non-final cell advances normally
- writing at the final cell succeeds
- after a successful write at the final cell, the cursor remains at that cell
- subsequent writes continue to target that same final cell unless the application moves the cursor

This is intentional.
The library does not currently expose a public end-of-window sentinel state through
`cury` / `curx`.

Single-cell and bulk text writes are expected to obey the same final-cell rule.

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

Subwindows are part of the intended core model.

### Current subwindow rules

- `lc_subwin(parent, ...)` creates a child window in parent-relative coordinates.
- Subwindows share `LCCell` objects with the parent backing store.
- Shared backing means shared cell content, not a fully shared refresh state.
- Every live derived window has a non-`None` `root`.
- Writes through a subwindow must be visible through the parent and vice versa.
- Dirty tracking must propagate upward from child to parent chain.
- A child window is lifecycle-owned by its parent.

### Shared-backing refresh consequence

The current refresh model is root-oriented.

That means:

- shared-backing windows share cell contents
- they do not currently share dirty metadata symmetrically across every alias
- dirty changes are guaranteed to propagate upward from child to parent
- dirty changes made through a parent or sibling are not currently guaranteed to
  mark every overlapping child view dirty

As a result, refreshing the root window is the fully coherent presentation path
for a shared-backing window topology. A derived-window refresh is only guaranteed
with respect to dirty state tracked on that derived window and its upward propagation.

### Lifecycle rules

- Every window has an `alive` state.
- Live windows always have a valid `root`; dead windows clear `root`.
- Operations on dead windows return `-1` where the operation normally reports failure, or act as no-op only for internal helpers that are intentionally silent.
- `lc_free(parent)` recursively frees the full child subtree first.
- A child cannot outlive its parent.

### Resize rule

Subwindows are tied to the current backing-store topology.
When the root window is resized, all existing subwindows are invalidated and freed.
The previous root backing topology is then retired and replaced by a new root window object.
Applications must rebuild derived windows against that new root after observing `LC_KEY_RESIZE`.

Refresh behavior follows the same rule:

- refreshing a dead window fails
- refreshing a derived window from the pre-resize topology fails
- root refresh may continue on the rebuilt `stdscr`
- the library does not reinterpret an explicit refresh of an invalidated
  derived window as a refresh of the rebuilt root window

### Resize rebuild flow

The current resize rebuild model is intentionally explicit:

- the backend reports a real size change
- the core invalidates all derived windows from the old backing topology
- the core builds a replacement root window object
- overlapping contents and cursor position are copied/clamped into that replacement
- the old root object is retired
- `stdscr` is rebound to the replacement root
- applications must rebuild any derived topology they still need

### Practical refresh rule

Applications should treat derived windows primarily as shared-backing drawing
views, not as independently coherent presentation surfaces.

In practice:

- draw through root or derived windows as needed
- prefer refreshing the root window when shared-backing subwindows overlap or interact

### Panel/content helper rules

- `lc_panel_content_rect(...)` returns the interior content rect for a boxed panel.
- `lc_panel_subwin(...)` creates a derived subwindow for that interior.
- Panel-content subwindows are ordinary subwindows and therefore follow the same lifecycle and resize rules.

## 5.5 Refresh semantics contract

The refresh layer compares window contents against a cached screen image and emits only changes.

Refresh is allowed to clip against physical screen bounds.
Window drawing is not.
The cached screen image is global physical-screen state, not per-window state.

That distinction matters:

- window clipping protects logical backing storage
- refresh clipping protects terminal output bounds

### Refresh coherence rule

The root window is the fully coherent refresh source for the current
shared-backing model.

Derived-window refresh is supported only within the limits described in the
subwindow contract above.

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
- a refresh call may observe that resize before emitting output
- core checks actual size
- core rebuilds stdscr and cached screen state
- core invalidates all derived windows from the old topology
- key layer emits `LC_KEY_RESIZE`

Applications must rebuild any derived windows after that point before using
them again, including for explicit refresh calls.

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
- root-oriented refresh coherence for shared-backing windows
- live-window root identity (`root is self` for top-level windows)
- explicit resize invalidate/rebuild/replace flow
- shared-backing subwindows with upward dirty propagation
- panel-content subwindow helpers

## 10. What is still in motion

These areas are still under active design and should not yet be treated as frozen API truth:

- Unicode cell-width semantics
- whether derived-window refresh should remain limited or become fully coherent across shared aliases
- whether future window types should include copied-backing windows in addition to shared-backing subwindows
- how far internal bulk/span helper consolidation should go
- whether future write families should be separated more explicitly in the public API
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

## 14. UI runtime skeleton

The project now also has a minimal UI runtime skeleton:

- `ui_event.py`
- `ui_view.py`
- `ui_layout.py`
- `ui_runtime.py`

This is not a widget toolkit yet.
It is an architectural layer that establishes where future UI behavior belongs.

### 14.1 Intended responsibility split

- `lc_*` modules remain the terminal/core/runtime substrate
- `ui_event.py` translates runtime input into UI-facing events and commands
- `ui_view.py` defines logical view identity and tree semantics
- `ui_layout.py` owns logical rect/layout policy
- `ui_runtime.py` coordinates focus, dispatch, rebinding and redraw passes

### 14.2 Important design rule

A future logical UI view must not be identified by a concrete `LCWin`.

Instead:

- a `UIView` is the stable logical node
- a bound `LCWin` is a runtime drawing resource
- that binding may be rebuilt after resize or layout changes

This keeps the future UI layer compatible with resize-driven subwindow invalidation.

### 14.3 Root binding rule

The root `UIView` binds directly to `stdscr`.

It is not treated as a synthetic panel and is not bound through a fake
panel-content subwindow. This keeps the model honest:

- root layout is a logical UI concern
- root binding is a runtime concern
- panel/content semantics belong only to views that actually choose panel-like
  layout or framing

This is the baseline for future frame/content zoning and widget composition.
