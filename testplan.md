# Test Plan for Shared-Backing Refresh Semantics

## 1. Core rule: root refresh is the coherent commit surface

### Test 1.1 — Child write is visible through parent refresh

**Purpose:** Verify upward dirty propagation + shared backing + root-oriented refresh.

**Setup**
- Create a root `stdscr` or a normal root window.
- Create `child = lc_subwin(root, ...)`.
- Write text through `child`.
- Refresh `root`.

**Expected**
- `root` refresh returns `0`.
- Physical cache (`lc.screen`) is updated in the corresponding absolute region.
- Text written through `child` is visible at the root positions.
- The child change does not require a separate child refresh to become visible.

**This locks in**
- Shared cells work.
- Dirty state propagates upward.
- Root refresh is coherent for child-initiated changes.

---

### Test 1.2 — Parent write is visible through root refresh in the child area

**Purpose:** Verify that root refresh is the true presentation path even for regions covered by child windows.

**Setup**
- Create root.
- Create child covering a subregion.
- Write through root in the area overlapped by child.
- Refresh root.

**Expected**
- Root refresh returns `0`.
- `lc.screen` shows the parent write in the correct physical cells.
- Child shared-cell contents match root contents after the write.

**This locks in**
- Root refresh remains coherent even when child windows exist.
- Child is not a separate presentation surface.

---

## 2. Intentional asymmetry: derived refresh is not fully coherent

These are the most important tests because they prevent future documentation drift.

### Test 2.1 — Parent write does not automatically mark child dirty

**Purpose:** Verify the real asymmetry in dirty metadata.

**Setup**
- Create root.
- Create child over part of root.
- Reset dirty flags so both are clean.
- Write through root in the child area.
- Inspect the child row dirty flags.

**Expected**
- Root row(s) are dirty.
- Child row(s) do not have to be dirty.
- Child cell contents are still updated because backing is shared.

**This locks in**
- Shared content ≠ shared dirty metadata.

This test is nearly more important than the refresh test because it explains why refresh semantics behave this way.

---

### Test 2.2 — Sibling write does not automatically mark another sibling dirty

**Purpose:** Verify that lateral dirty propagation does not exist.

**Setup**
- Create root.
- Create `a` and `b` that fully or partially overlap the same backing area.
- Reset dirty flags.
- Write through `a`.
- Inspect dirty flags in `b`.

**Expected**
- `a` is dirty.
- Root is dirty.
- `b` does not have to be dirty.
- Shared cell content in `b` still reflects the change.

**This locks in**
- No lateral invalidation.
- Therefore derived refresh cannot claim full coherence.

---

### Test 2.3 — Parent write followed by child refresh must not be assumed coherent

This should be tested carefully because you do not want a test that depends too much on internal terminal emission.

**Purpose:** Lock in the documented limitation.

**Setup**
- Create root + child.
- Perform an initial refresh so `lc.screen` and cache are synchronized.
- Reset dirty flags.
- Write through root in the child area.
- Call `lc_wrefresh(child)`.

**Expected**
- The test must not require child refresh to update the screen.
- The key verification is that child refresh cannot be used as a coherence guarantee after a parent write.
- A simple expression:
  - Child may remain non-dirty.
  - A root refresh afterward must still produce the correct final state.

Suggested name:
`test_parent_write_does_not_make_child_refresh_a_coherent_commit_path`

This is long, but crystal clear.

**Important**
- Do not make this a test that requires a specific “failed” visual result, because refresh may still appear correct in some cases for unrelated reasons.
- The test should lock the contract, not an accidental implementation artifact.

---

## 3. Resize/invalidation contract

### Test 3.1 — Refresh on invalidated child after resize fails

**Purpose:** Lock the most important topology rule.

**Setup**
- Create root.
- Create child.
- Force a resize event so `lc_check_resize()` rebuilds root and invalidates children.
- Call `lc_wrefresh(child)`.

**Expected**
- Returns `-1`.
- `child.alive == False`.
- Child must not be magically interpreted as the new root.

---

### Test 3.2 — Root refresh after resize continues to work

**Purpose:** Verify that resize fallthrough applies only to root.

**Setup**
- Create root.
- Force resize.
- Call refresh with the old root reference if still alive in the model, or with `lc.stdscr` after rebuild depending on the exact test harness.
- Alternatively, use `lc_refresh()`.

**Expected**
- Rebuilt root can be refreshed.
- Global cache is reinitialized correctly.
- No derived refs from the old topology survive.

---

## 4. Dead-window contract

### Test 4.1 — Refresh on dead window returns `-1` immediately

**Purpose:** Lock in the behavior already improved.

**Setup**
- Create window.
- Free it.
- Call `lc_wrefresh(win)`.

**Expected**
- Return `-1`.
- No exception.
- No `IndexError`.
- No mutation of `lc.cur_x`, `lc.cur_y`, `lc.cur_attr`, or `lc.screen` as a side effect.

The last point is important: fail should be a clean fail.

---

## 5. Hash/refresh optimization must not broaden semantics

### Test 5.1 — Row hash shortcut is not used for child

**Purpose:** Prevent future “smart” optimizations that would break the model.

**Setup**
- Create root + child.
- Construct a state where a child row happens to match the same content as the physical row cache.
- Refresh child.

**Expected**
- The test does not verify terminal bytes, but that `_can_use_row_hash_shortcut()` semantics are preserved:
  - Child must not be treated as a full physical row.
  - In practice, this is best tested indirectly by ensuring child refresh still follows normal cell-diff path and does not clear dirty state based on physical row hash on invalid grounds.

If you want less implementation-tight tests, this can instead be a smaller unit test directly on `_can_use_row_hash_shortcut()`.

---

### Test 5.2 — Full-width root row may use hash shortcut

**Purpose:** Preserve optimization where it is legitimate.

**Setup**
- Root with `begx == 0`, `maxx == lc.cols`.
- Row is dirty but unchanged versus hash cache.
- Not `LC_FORCEPAINT`.

**Expected**
- Row is cleared from dirty state without emission.
- Semantics apply only to full physical root rows.

---

## 6. Panel/content-subwindow follows the same rules

This is good to lock in because panel helpers can otherwise be treated as something “more official.”

### Test 6.1 — Panel content subwindow is a regular shared-backing subwindow

**Setup**
- Create root.
- Create panel.
- Create content subwindow via helper.
- Write through content subwindow.
- Refresh root.

**Expected**
- Behavior matches regular subwindow exactly.
- No extra refresh privileges or special cases.

---

### Test 6.2 — Panel content subwindow invalidates on resize like any other child

**Expected**
- Same invalidation rule.
- Same refresh failure after resize.
