# LC Contract

This document describes the current core-layer contract for vtpy.

It is the contract below any future UI runtime and above the active platform
backend. It describes what the `lc_*` layer is allowed to mean today, with
special attention to lifecycle, shared-backing windows, staged refresh, and
resize semantics.

The purpose is simple:

- keep the terminal core small and honest
- define the current stable runtime model in one place
- make refresh, resize, and window semantics explicit
- give the future UI layer a hard substrate instead of folklore

This document is normative for the current core model.

## 1. Scope

This contract covers the `lc_*` core layer:

- runtime/session state
- backend interaction boundary
- screen size and resize handling
- windows and subwindows
- backing storage and dirty tracking
- staged refresh and terminal flush
- key decoding boundary
- terminal output state tracking

This contract does not define higher-level UI concerns such as:

- focus chains
- command routing
- view trees
- widget behavior
- application actions

Those belong above the core.

## 2. Architectural position

The intended stack is:

- backend layer: terminal mode control, size discovery, input-byte acquisition, resize observation
- core layer: runtime state, windows, backing cells, dirty metadata, staged refresh, key decoding
- UI layer: logical views, focus, commands, layout, redraw policy
- application layer: editor, monitor, shell UI, debugger, installer, and so on

The core depends on the backend contract.
The backend does not know about windows or refresh policy above byte I/O.
A future UI layer may depend on the core.
The core must not depend on the UI layer.

## 3. Design goals

The core layer should provide:

- explicit runtime lifecycle
- explicit window ownership and liveness
- explicit resize invalidation and rebuild
- explicit staged refresh semantics
- explicit distinction between logical backing storage and physical terminal state
- platform-neutral public behavior above the backend contract
- small and testable state transitions

The core should feel like a runtime substrate, not a bag of incidental helpers.

## 4. Non-goals

The current core is not trying to be:

- a curses compatibility shim
- a full terminal capability database
- a full Unicode layout engine
- a full window-manager hierarchy with coherent independent aliases
- a widget toolkit
- a semantic UI runtime

The core remains terminal-first, cell-first, and refresh-first.

## 5. Runtime/session contract

The runtime distinguishes between:

- backend-started state
- fully active screen-session state

These are not identical.

### 5.1 Backend-started state

After backend initialization succeeds:

- backend-owned terminal/input resources are live
- backend shutdown is required during teardown
- the session is not yet fully active
- `stdscr` may still be absent

### 5.2 Session-active state

The session becomes fully active only after:

- backend init has succeeded
- terminal enter/setup steps have succeeded
- the root backing window has been created
- `stdscr` has been established

Only then may screen-oriented public operations assume an active session.

### 5.3 Teardown rule

Teardown must be safe for:

- partial initialization failure after backend startup
- normal shutdown
- repeated/idempotent shutdown calls

The runtime owns session validity.
Refresh code consumes that validity; it does not define it.

## 6. Backend boundary contract

The backend contract is byte-oriented.

Required backend responsibilities are:

- terminal mode setup and restore
- terminal size discovery
- raw byte acquisition
- one-byte pushback
- raw/noraw and cbreak/nocbreak symmetry
- resize observation
- backend-owned terminal/output handle establishment before core size discovery and terminal control use

The backend is not responsible for:

- UTF-8 decoding
- VT/CSI/SS3 parsing above byte level
- window clipping semantics
- dirty tracking
- staged refresh
- view/UI semantics

### 6.1 Byte-stream rule

`read_byte()` returns one byte-equivalent integer in range `0..255`, or `None`
on EOF/error/unavailable terminal failure.

### 6.2 Resize readiness rule

Resize is not input-byte readiness.

A pending resize alone must not make `input_pending()` report ready input.

### 6.3 Translation rule

Backend-specific input events may only enter the core as byte stream plus resize notification.

## 7. Window contract

A window is a logical drawing view over backing storage.

### 7.1 Window identity

Every live window has:

- dimensions
- origin relative to the physical screen
- cursor position
- row storage
- alive/dead state
- root identity
- optional parent relationship
- optional child list

### 7.2 Root identity rule

Every live window has a non-`None` `root`.

That means:

- for a top-level window, `root is self`
- for a derived window, `root` names the top-level backing root
- dead windows clear `root`

### 7.3 Subwindow/shared-backing rule

Derived windows are shared-backing subwindows.

That means:

- derived windows share `LCCell` objects with the parent backing store
- shared backing means shared cell content only
- shared backing does not imply fully symmetric dirty metadata

Writes through a subwindow must be visible through the parent and vice versa.

### 7.4 Dirty propagation rule

Writes through a child view must propagate dirty metadata upward through the parent chain.

Dirty changes made through a parent or sibling are not guaranteed to mark every overlapping child view dirty.

### 7.5 Liveness rule

Dead windows are invalid objects for normal public operations.

Operations on dead windows fail where the public API normally reports failure.

### 7.6 Resize invalidation rule

When the root window is resized:

- all derived windows from that topology are invalidated and freed
- the old root backing topology is retired
- a replacement root window is created
- overlapping content and cursor position are copied/clamped into the replacement
- `stdscr` is rebound to the replacement root

Applications must rebuild any derived windows they still need after observing resize.

## 8. Drawing contract

Window drawing operates on logical backing storage, not on the terminal directly.

### 8.1 Backing-store safety rule

No window operation may read or write outside the window backing store.

### 8.2 Strict vs clipped operations

Strict operations fail on invalid coordinates where partial clipping would not make semantic sense.

Clipped operations may partially or fully clip against window bounds and still succeed.

### 8.3 Cursor-driven write rule

Cursor-driven writes are prefix-success operations under a saturating cursor policy.

That means:

- writes at the current valid cursor succeed while writable space remains
- the final writable cell may be written successfully
- after a successful write at the final writable cell, the cursor remains there
- no public end-of-window sentinel cursor state is exposed

## 9. Refresh contract

Refresh is a staged global presentation model, not a direct per-window terminal write model.

The refresh pipeline is:

`window backing + local dirty metadata -> desired presentation buffer -> terminal diff flush`

### 9.1 Root coherence rule

The root window is the fully coherent refresh source for the current shared-backing model.

Derived-window refresh is supported only within the limits of that derived window's own tracked dirty state.

### 9.2 Window dirty rule

Window dirty metadata is **local staging debt**.

That means:

- it describes window-local content changes not yet staged into the global desired presentation buffer
- it is not the same thing as terminal staleness
- it is not the same thing as global presentation truth
- it is not symmetric across all shared-backing aliases

### 9.3 Desired-screen rule

The desired screen (`vscreen`) is the **global desired presentation buffer**.

That means:

- it represents the most recently staged visible physical-screen intent
- it is ordering-sensitive
- later staged windows may overwrite earlier staged content in overlapping regions
- it is not canonical backing-store truth

### 9.4 Virtual dirty rule

Virtual dirty ranges (`vdirty_*`) are **flush debt**.

That means:

- they describe which desired-screen regions still need comparison against the physical output cache and possible terminal emission
- they are independent from window-local dirty metadata

### 9.5 Physical cache rule

The physical screen cache (`screen`) is the **physical output cache**.

That means:

- it records what the terminal is believed to show after the most recent successful flush
- it is not authoritative backing-store data
- it may be reinitialized when terminal state assumptions are reset

### 9.6 Staging rule

`lc_wnoutrefresh()` / staged-refresh operations:

- read window backing plus window-local dirty metadata
- copy visible dirty content into the global desired presentation buffer
- consume window-local staging debt for the staged rows
- do not write terminal output
- do not inspect backing stores other than the requested window view

### 9.7 Flush rule

`lc_doupdate()` / flush operations:

- read only desired-screen state plus physical-cache state
- do not inspect window backing stores directly
- compare desired-screen content against the physical output cache
- emit only needed terminal changes
- consume virtual flush debt for the processed rows

### 9.8 Cursor presentation rule

The final hardware cursor after flush follows the most recently staged, physically visible cursor position.

Cursor presentation is desired-screen intent, not backing-store truth.

### 9.9 Convenience refresh rule

`lc_wrefresh(win)` is the immediate staged-refresh path for that explicit window view.

`lc_refresh()` is the fully coherent default presentation path for the current shared-backing model because it stages and flushes the root window.

## 10. Resize/refresh interaction contract

Resize rebuild is a topology event, not a local repaint detail.

### 10.1 Pre-flush resize rule

If a resize rebuild is observed before flush emits terminal output:

- all previously staged desired-screen state is discarded unconditionally
- stale derived windows from the retired topology remain invalid
- applications must rebuild any needed derived windows and restage against the replacement topology

### 10.2 Refresh validity ownership rule

Refresh validity after resize is owned by the runtime/screen layer.

The refresh layer may stage and flush only after the runtime has resolved whether the requested refresh target remains valid in the current topology.

### 10.3 No reinterpretation rule

Refreshing an invalidated derived window must fail.

The runtime must not reinterpret an explicit refresh of an invalidated derived window as a refresh of the rebuilt root window.

## 11. Input contract above the backend

The core key layer sits above the byte-oriented backend.

That means:

- UTF-8 decoding belongs in the key layer
- VT/CSI/SS3 parsing belongs in the key layer
- the key layer may surface character events and keysyms
- resize is surfaced as a structural key-layer event for core consumers

The key layer is still not the UI layer.
It provides normalized terminal input, not logical command routing.

### 11.1 ESC timing and Alt-prefix rule

ESC (`0x1B`) handling is delay-gated and intentionally ambiguous in the same
way real terminals are ambiguous.

- if no follow-up byte is pending before `escdelay`, ESC is emitted as a plain
  character event
- if a follow-up byte arrives in time and does not decode as CSI/SS3, ESC
  prefix is interpreted as Alt/Meta only when `meta_on` is enabled
- in nodelay mode with negative `escdelay`, timeout is treated as zero for
  disambiguation polling

### 11.2 Function-key compatibility floor

Function-key decoding is intentionally based on a conservative VT/xterm-style
sequence set.

Supported baseline:

- SS3 F1-F4 (`ESC O P` .. `ESC O S`)
- CSI `~` forms for F5-F12 (`ESC [ 15~`, `17~`, ... `24~`)
- extended CSI `~` forms up to F20 where emitted by the terminal

Compatibility limits:

- no terminfo/termcap capability probing is performed in the core
- non-VT private emulator encodings are not normalized unless they match the
  supported sequence family above
- application code should treat F1-F12 as the portable floor across terminals;
  F13-F20 support is best-effort and emulator-dependent

## 12. What belongs above the core

The following belong above the core:

- logical view trees
- focus ownership and traversal
- command routing
- menu/dialog semantics
- selection models
- application state machines
- higher-level redraw scheduling policy

A future UI runtime should consume the core contract rather than smearing these responsibilities back into it.

## 13. Practical near-term rule

When changing the core, ask:

- does this preserve the runtime/session split?
- does this preserve the shared-backing window truth?
- does this preserve staged refresh as the only presentation path?
- does this keep resize semantics explicit and destructive where needed?
- does this avoid pretending that desired state, physical cache, and backing truth are the same thing?

If the answer is unclear, the change is probably broadening semantics without writing them down.

## 14. One-line summary

A small, explicit terminal runtime where window backing state, local dirty metadata, staged desired presentation, physical output cache, and resize-driven topology rebuild are separate contracts with separate meanings.
