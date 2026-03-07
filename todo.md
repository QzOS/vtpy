# TODO

This file records the current state of the library, the design decisions already made, and the next work items in a sensible order.

## Project snapshot

The codebase is now a small VT-oriented TUI core with:

- a backend split (`_posix.py`, `_win.py`, `lc_platform.py`)
- a byte-oriented input path with VT key decoding
- a screen state layer (`lc_screen.py`)
- a window model with dirty tracking (`lc_window.py`)
- a batched renderer (`lc_refresh.py`)
- subwindows with shared backing store
- panel helpers and panel-content subwindow helpers
- explicit resize handling through `LC_KEY_RESIZE`

The project is no longer a rough ANSI experiment. It now has a real internal architecture and a usable contract surface.

## Design decisions already made

### Terminal model
- The library is VT/ANSI oriented.
- Output is escape-sequence based.
- Input is byte-oriented and decoded in the core.
- Windows support is provided through a backend, not by pretending Windows is POSIX.

### Backend contract
- Backends must implement the API declared in `lc_platform.py`.
- The core owns rendering and key decoding.
- The backend owns terminal mode setup, raw/cbreak/echo toggles, byte input, and resize observation.

### Window model
- `LCWin` is the central window object.
- Rows store dirty spans (`firstch`, `lastch`, `flags`).
- Clipping is explicit and helper-based.
- Refresh coherence is currently root-oriented.
- Every live window has a non-`None` `root`; a top-level live window has `root is self`.
- Drawing helpers operate on clipped geometry instead of assuming full visibility.

### Subwindow model
- Subwindows share backing store with their parent.
- Dirty changes propagate upward through the parent chain.
- Subwindows are parent-relative at creation time.
- Shared backing currently means shared cell content, not fully shared dirty
  metadata across every alias.
- Derived windows inherit the top-level root identity of their current backing topology.
- Dead windows clear `root`.
- As a result, root refresh is the fully coherent presentation path for
  shared-backing topologies.
- Derived-window refresh is currently limited by the dirty state tracked on that view.
- Each window tracks `parent`, `root`, `pary`, `parx`, `alive`, and `children`.

### Lifecycle model
- Windows are either alive or dead.
- Freeing a parent recursively frees its subtree.
- Operations on dead windows fail.
- Live windows always have a valid `root`.
- Subwindows do not survive parent teardown.

### Resize model
- Resize replacement is explicit: invalidate old derived topology, build a new
  root object, copy overlap, retire the old root, and require the app to rebuild
  derived windows against the replacement.
- A root resize invalidates all derived subwindows.
- The application is expected to rebuild subwindows after receiving `LC_KEY_RESIZE`.
- This is intentional. The library does not currently attempt to remap derived windows across a resize.
- An explicit refresh of an invalidated derived window must fail rather than
  silently falling through to the rebuilt root.

### Panel model
- A panel is currently a composed drawing operation:
  - box
  - optional title
  - optional interior fill
- Panel content geometry is defined by the box interior.
- Panel content may be accessed through a derived subwindow.

### Write-family model
- Cursor-driven writes (`lc_wput`, `lc_waddstr`) are one operation family.
- Clipped drawing/fill operations are another family.
- Internal bulk/span helpers are implementation helpers, not a license to widen semantics.
- Cursor-driven writes must share the same final-cell cursor policy.
- Bulk/span helpers must preserve visible cell state and dirty-range semantics
  for the operation family they implement.

## What is stable enough right now

These areas are in decent shape and can be treated as the current base:

- backend split and backend contract
- basic terminal mode switching
- alternate screen usage
- dirty-row rendering with batching
- clipping helpers for rects and spans
- box, line, fill, title, and panel primitives
- shared-backing subwindows
- live-window root identity invariants
- explicit resize invalidate/rebuild/replace model
- root-oriented refresh coherence
- recursive free and child invalidation
- resize -> `LC_KEY_RESIZE` flow

## Known technical weaknesses

These are the most important current weaknesses, not vague future dreams.

### 1. Refresh path does not guard dead windows strongly enough
`lc_wrefresh()` should reject dead windows immediately.

Current risk:
- dead windows may have `lines == []`
- stale callers may still pass them into refresh
- this can lead to index errors or undefined rendering behavior

### 2. Internal write-helper consistency is still looser than it should be
Some operations converge through `_set_cell()`, while some bulk/span helpers write
rows directly and then mark dirty.

This is not currently a correctness bug, but it is still a maintenance risk:

- visible cell-state semantics can drift
- dirty-range semantics can drift
- helper layering is not as explicit as it should be
- future Unicode or attribute changes would have too many write paths to audit

### 3. Shared-backing refresh semantics are intentionally asymmetric
Shared cell content and local dirty metadata are not the same thing.

Current consequence:
- a child write propagates dirtiness upward
- a parent or sibling write is not guaranteed to mark every overlapping child dirty

The current chosen model is:

- saturating cursor at the last valid cell

Current rule:

- a successful write at the final cell leaves the cursor at that cell
- subsequent writes continue to target that same cell until the cursor is moved

Some operations use `_set_cell()`, while `_write_text_clipped()` performs direct row writes and then marks dirty.
This is not broken, but it is a maintenance smell.
A cleaner internal bulk-write path would reduce drift.

## Immediate next tasks

These are the next sensible tasks in order.

This is acceptable only if the project continues to treat root refresh as the
fully coherent presentation path for shared-backing windows.

### Priority 1: close correctness gaps
- [x] Add an `alive` guard at the start of `lc_wrefresh()`.
- [x] Audit refresh-adjacent helpers for dead-window assumptions.
- [x] Add tests that explicitly verify refresh on dead windows fails cleanly.

### Priority 2: fix cursor semantics
- [x] Choose and document the cursor model at the last cell.
- [x] Update `_advance_cursor()` and write paths accordingly.
- [x] Add tests for final-column write, final-cell write, and repeated writes after the last writable cell.

### Priority 3: lock down shared-backing refresh semantics
- [x] Decide that root refresh is the fully coherent presentation path for the
  current shared-backing model.
- [x] Document that decision in `README.md` and `todo.md`.
- [x] Add tests that verify:
  - child write -> parent refresh works
  - parent write -> child refresh is not assumed coherent unless the child view is dirty
  - sibling write -> sibling refresh is not assumed coherent unless local dirty state demands it
  - refresh of an invalidated derived window fails after resize

### Priority 4: lock down root identity and write-helper invariants
- [x] Decide that every live window has a non-`None` `root`.
- [x] Decide that a live top-level window has `root is self`.
- [x] Decide that dead windows clear `root`.
- [x] Add or keep tests that verify root/self-root invariants across create/subwin/free/resize replacement.
- [x] Document write operation families more explicitly in code comments where helpers currently look interchangeable.
- [x] Consolidate internal write helpers into a smaller explicit hierarchy.
- [x] Add tests that compare bulk/span helper effects against the visible cell-state
  and dirty-range semantics expected for their operation family.

## Next structural tasks

Once the immediate correctness gaps are closed, these are the next worthwhile structural improvements.

### Geometry and layout
- [ ] Add simple layout helpers for vertical and horizontal splits.
- [ ] Consider a small rect helper module if geometry keeps growing.
- [ ] Keep clipping policy centralized and test-driven.

### Panel/content workflow
- [ ] Add optional header-band support for panels.
- [ ] Decide whether headers are visual only or define a separate content origin.
- [ ] If headers become real layout regions, add helper(s) for header/body rect extraction.

### Rendering
- [ ] Review whether dirty tracking plus hash tracking is redundant in some hot paths.
- [ ] Decide whether future fully coherent derived refresh would require shared
  dirty metadata, a different invalidation structure, or a different window
  class rather than changing current shared-backing semantics in place.
- [ ] Keep resize replacement explicit; do not blur invalidation of old topology
  and creation of replacement root into in-place remapping magic.
- [ ] Consider a more explicit row-level bulk emit helper.
- [ ] Add regression tests for large dirty spans and clipped redraws.
- [x] Separate refresh/session-lifecycle policy from the diff/flush path.
  `lc_screen` now owns session-validity, resize-gate, and topology-liveness
  logic through `lc_refresh_session_ready`, `lc_refresh_resize_gate`, and
  related helpers.  `lc_refresh` consumes that contract and stays focused on
  staging and terminal output.
- [x] Introduce `lc_wstage` / `lc_wstageflush` as the canonical public
  names for the two-phase and combined refresh paths.  `lc_wnoutrefresh` and
  `lc_wrefresh` remain as aliases for backward compatibility.

### Input
- [ ] Add more explicit tests for ALT-modified input.
- [ ] Add tests for ESC timing behavior.
- [ ] Decide how far function-key compatibility should go across terminals.

### Backend discipline
- [ ] Add backend contract tests where practical.
- [ ] Keep Windows behavior byte-oriented and explicit.
- [ ] Avoid introducing POSIX assumptions into the generic core.

## Larger future work

These are real future items, but not the next thing to touch.

### Window hierarchy evolution
- [ ] Decide whether to add true derived-window variants beyond the current `lc_subwin()` model.
- [ ] If independently refreshable child windows are needed later, decide
  whether that should mean copied backing rather than stronger shared-backing magic.
- [ ] Decide whether child windows should ever be automatically recreated across resize.
- [ ] If automatic remapping is ever considered, write the invariants first before touching code.

### Attributes and styling
- [ ] Extend attributes beyond bold/underline/reverse only if the terminal contract stays clear.
- [ ] Decide whether colors belong in the same attr model or in a separate encoding layer.

### API shaping
- [ ] Clean up naming once the core stabilizes.
- [ ] Decide project name based on what the library actually is, not what sounds cute.
- [ ] Keep the public API small until semantics are fully nailed down.

## Rules to keep while moving forward

- Do not add features that blur backend/core responsibilities.
- Do not add convenience helpers that hide unresolved semantics.
- Do not preserve subwindows across resize unless the full remap contract is designed first.
- Do not describe derived-window refresh as fully coherent while dirty tracking
  remains local to each window view.
- Do not weaken the live-window root invariant by reintroducing ambiguous `root=None`
  states for living windows.
- Do not let bulk/span write helpers quietly grow semantics that differ from the
  operation family they are implementing.
- Prefer explicit invalidation and rebuild over clever hidden behavior.
- Do not silently redirect an explicit refresh of an invalidated derived window
  to the rebuilt root window.
- Keep tests focused on contracts and invariants, not just happy-path screenshots.

## Working definition of the project

For now, the most accurate description is:

> A small, explicit, VT-oriented TUI core for Python with backend abstraction,
> byte-oriented input decoding, dirty-region rendering, and a lightweight
> shared-backing window model.

