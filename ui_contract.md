# UI Contract

This document describes the intended UI-layer contract for vtpy.
It does not redefine the current low-level terminal core. That core should be
described by `lc_contract.md`. This document describes the next stable layer
that should sit above the existing window, input, and refresh machinery.

The purpose is simple:

- keep the terminal core small and honest
- let more structured text UI behavior grow above it
- define boundaries early so future UI code does not turn into ad hoc screen painting
- provide a reference model for a future OS-native text UI runtime

## 1. Scope

This document is layered on top of `lc_contract.md`.

This contract covers the UI layer above the current core:

- views
- commands
- focus
- actions
- event dispatch
- invalidation and redraw policy
- layout and panel composition
- input translation at the UI boundary

This contract does not redefine:

- backend terminal control
- byte acquisition
- VT parsing in the key decoder
- low-level cell storage
- low-level diff rendering

Those remain core concerns and should keep the meanings defined by
`lc_contract.md`.

## 2. Architectural position

The intended stack is:

- backend layer: platform terminal control
- core terminal layer: screen state, cells, windows, refresh, key decoding
- UI layer: views, focus, layout, command routing, redraw policy
- application layer: editor, file manager, shell UI, monitor, installer, debugger, and so on

The core/UI boundary should remain explicit.

The UI layer must depend on the core.
The core must not depend on the UI layer.

## 3. Design goals

The UI layer should provide enough structure to build serious text applications without dragging the core toward curses-style global soup.

The goals are:

- deterministic redraw behavior
- explicit ownership and lifecycle
- explicit focus routing
- explicit command dispatch
- stable geometry boundaries
- composable panels and content regions
- small and testable primitives
- zero hidden dependence on platform backends

The UI layer should feel closer to a runtime than to a bag of helper functions.

## 4. Non-goals

At least for the first serious version, the UI layer is not trying to be:

- a widget zoo
- a theme engine
- an HTML/CSS clone
- a retained-mode scene graph with arbitrary overlap rules
- a generic desktop GUI abstraction
- a full curses compatibility shim

The model should stay text-first, pane-first, and command-first, while
remaining honest about current core constraints.

## 5. Core UI concepts

### 5.1 View

A view is the primary UI object.
A view is a logical region with behavior.

A view owns:

- a rectangle in parent coordinates
- local state
- drawing logic
- event handlers
- focus policy
- optional child views
- invalidation state

A view does not own terminal backend state.
A view does not talk directly to `_posix.py` or `_win.py`.

### 5.2 Root view

The root view is the UI object bound to `stdscr` or to the current rebuilt root after resize.

The root view owns:

- the top-level layout
- global focus chain root
- command bubbling fallback
- full redraw fallback

### 5.3 Panel/container view

A panel or container view is a view that:

- defines geometry for children
- may draw its own border, title, or header
- may expose a content rect
- may host child views inside that content rect

This should map naturally onto the existing panel and subwindow helpers.

### 5.4 Leaf view

A leaf view is a view with no children or with child composition that is not externally addressable.

Typical leaf views later might be:

- label
- status line
- list
- text area
- log pane
- menu bar
- input field

## 6. View contract

A view should obey the following contract.

### 6.1 Identity and lifetime

A view has:

- a parent or `None` for root
- an alive/dead state
- a stable type-specific behavior contract

Destroying a parent destroys the subtree.
A dead view must reject future events and redraw requests.

### 6.2 Geometry

A view has a logical rectangle:

- `y`
- `x`
- `height`
- `width`

Geometry is always parent-relative.
The view may also expose derived rects such as:

- frame rect
- header rect
- content rect
- footer rect

The UI layer should centralize rect math instead of sprinkling offsets through drawing code.

### 6.3 Draw entry point

Each view should have a draw method conceptually like:

- `draw(surface)`

Where `surface` is a window-like drawing target already clipped to the view domain, or a root drawing context that can derive such a target.

The draw rule is:

- drawing must stay inside the view's assigned rect
- child drawing must stay inside child rects
- redraw output must be deterministic from state

### 6.4 Event entry point

Each view should have an event handler conceptually like:

- `handle_event(event) -> result`

The result should tell the dispatcher whether the event was:

- handled
- ignored
- transformed into a command
- requesting focus transfer
- requesting redraw or layout

### 6.5 Focus capability

A view may be:

- non-focusable
- focusable
- focus container

A focusable view must define what it means to enter focus, leave focus, and handle focused key input.

## 7. Event contract

The UI layer should not work directly on raw bytes.
It should work on normalized events.

## 7.1 Event classes

At minimum, the UI layer should define event classes conceptually like:

- key event
- character event
- command event
- resize event
- focus event
- timer event later, if ever added

## 7.2 Key event

A key event should carry:

- keysym or rune
- modifier state
- source context if needed

The existing `LCKey` is a reasonable low-level basis.
The UI layer should wrap or normalize it rather than force every widget-like object to know terminal parser details.

## 7.3 Resize event

A resize event should be explicit.

The existing `LC_KEY_RESIZE` should become a UI-visible structural event, not just another random key code in app code.

Applications should be able to treat resize as:

- layout invalidation
- subview binding rebuild trigger
- full redraw request

Concrete `LCWin` bindings may be rebuilt freely as long as logical view identity survives.

## 7.4 Event routing

The default routing order should be:

- focused view first
- then its ancestors by bubbling
- then root/global handlers

Container-local pre-routing is acceptable for arrows, tab movement, or menu activation, but it should be explicit.

## 8. Command contract

A command is a semantic action, not a raw keystroke.

Examples:

- quit
- save
- open
- next-pane
- previous-pane
- page-down
- cursor-left
- activate
- cancel
- help

The UI layer should separate:

- raw input mapping
- semantic commands
- application actions

That separation is crucial if you later want:

- configurable keymaps
- platform-independent bindings
- command palette behavior
- macro recording
- scripted test injection

## 8.1 Command routing

Commands should route similarly to events:

- focused view first
- then parent chain
- then application/root command handler

The command layer should answer:

- handled or not handled
- produced state change or not
- requires redraw or not

## 9. Focus contract

Focus needs a real contract or the whole UI layer turns into spaghetti.

## 9.1 Single active focus target

There should be exactly one active focused leaf view at a time inside a root UI tree.

Containers may maintain local ordering, but there should still be a single effective focused target for input routing.

## 9.2 Focus traversal

Traversal policy should be container-owned, not global magic.

A container may define:

- tab order
- arrow-based neighbor navigation
- explicit next/previous focus mapping

## 9.3 Focus lifecycle

Focusable views should support conceptual hooks like:

- `on_focus_enter()`
- `on_focus_leave()`

These should update internal state and invalidation, not perform random
immediate refreshes or bypass root commit.

## 10. Invalidation contract

The UI layer should be retained-mode in the minimal honest sense:

- state changes mark views dirty
- dirty views or layout changes cause redraw scheduling
- refresh happens explicitly at the root commit stage

Views should not call terminal output directly.
Views should invalidate themselves or request redraw through the UI runtime.

## 10.1 Invalidation levels

Useful invalidation levels later may be:

- self redraw
- subtree redraw
- layout recalculation
- full root redraw

Do not need all of them on day one, but the model should allow them.

## 10.2 Commit rule

The root runtime commits visual state.
That must stay aligned with the core refresh contract described in
`lc_contract.md`.

In practice:

- views draw into the shared backing model or into runtime-supplied drawing
  targets derived from it
- the root runtime decides when to call `lc_refresh()` or equivalent root
  refresh
- derived view refresh should not become the main semantic path
- view-local invalidation must not be confused with terminal staleness
- UI redraw scheduling should treat core window dirty metadata as local staging
  debt, not as a full presentation-truth signal

That keeps the UI contract aligned with the current engine truth instead of fighting it.

## 11. Layout contract

The UI layer needs a layout model before it grows real applications.

## 11.1 Minimal layout primitives

A good minimal set is:

- fixed rect
- vertical split
- horizontal split
- content-rect inset
- panel with optional title/header/footer bands

This is enough to build:

- editor + status bar
- two-pane file manager
- dialog with button row
- form layout
- inspector layout

## 11.2 Layout ownership

Containers own child layout.
Children do not negotiate arbitrary geometry upward in the first version.

That means the first version should prefer:

- parent-computed layout
- explicit rect assignment

rather than a large constraint system.

## 11.3 Resize behavior

On resize:

- root layout recomputes
- stale derived windows are rebuilt as runtime bindings
- focus is preserved if the focused logical view survives
- otherwise focus falls back deterministically

The important thing is this: preserve logical view identity if possible, but rebuild drawing surfaces freely.

## 12. Surface/window contract between UI and core

The UI layer should not assume that every view permanently owns a `LCWin` created once forever.

Better rule:

- a view may draw through a supplied target window
- container/root code may derive subwindows when useful
- subwindows are an implementation tool, not the whole UI identity

That matters because current resize semantics intentionally invalidate derived windows.
So logical views must outlive the current concrete subwindow objects.

This is a big design point.

If you want something tvision-like later, think:

- view identity is stable
- backing `LCWin` bindings are rebuildable runtime resources
- root commit remains the coherent presentation path
- concrete subwindows participate in local staging, not independent presentation truth

not:

- every view permanently is a specific `LCWin`

## 13. Recommended internal split for the future UI layer

A sane future split could look like this:

- `ui_event.py` - event and command types
- `ui_rect.py` - rect helpers, insets, splits, content bands
- `ui_view.py` - base view contract
- `ui_focus.py` - focus management and traversal
- `ui_layout.py` - parent-owned layout helpers
- `ui_runtime.py` - root dispatch, invalidation, redraw commit
- `ui_controls.py` or later-specific modules for reusable views

Do not need to build all of that now.
But this is the direction that avoids a mess.

## 14. What to keep out of the core

The following should stay out of `lc_screen.py`, `lc_refresh.py`, and the backend layer:

- focus chains
- command routing
- dialog behavior
- menu semantics
- selection models
- validation logic
- application state machines
- key binding policy beyond low-level decode

The core should remain a terminal runtime.
The UI layer should be the first place where application semantics appear,
without redefining core refresh, resize, or backing-store truth.

## 15. What to keep out of the first UI version

- skinnable themes
- dynamic style inheritance
- overlapping z-order windows with arbitrary repaint semantics
- generalized mouse model if the apps do not need it yet
- deeply abstract widget registries
- declarative layout DSLs

Start with boring, strong bones.

## 16. The key mental model

Think in these layers:

- core answers: how do bytes, cells, windows, and refresh work?
- UI answers: which logical view handles input, owns focus, and redraws where?
- app answers: what does the program mean?

If a future feature cannot clearly say which layer owns it, the design is still mush.

## 17. Practical near-term recommendation

If I were structuring the next phase, I would do it in this order:

1. define `Rect` helpers or a tiny `ui_rect` module
2. define a minimal `UIEvent` / `UICommand` model
3. define a minimal `View` base contract
4. define a `RootUI` runtime with:
   - focused view
   - dispatch loop
   - invalidate flag
   - root redraw commit
5. implement one real container view
6. implement one real leaf view such as a label/list/text area
7. only then decide whether you need more widget-like abstractions

## 18. One-line summary

A small, explicit, text-first UI runtime layered above vtpy core, where
logical views, focus, commands, layout, and redraw are stable contracts, while
concrete terminal surfaces remain rebuildable implementation details under the
core's staged-refresh and resize-rebuild truth.
