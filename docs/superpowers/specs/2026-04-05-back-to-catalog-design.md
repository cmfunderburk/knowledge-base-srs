# Back-to-Catalog via Ctrl+B

## Problem

After launching a practice session from the catalog (or CLI flags), there's no way to return to the catalog to select different material without quitting and restarting `review-gen`.

## Design

### Approach: Reset-in-place on the root app

Keep the existing architecture where practice runs on the app's root widgets. On Ctrl+B, reset all session state and push a fresh `CatalogScreen`.

### Binding

Add `Ctrl+B` as a high-priority app-level binding in `GenerationReviewApp.BINDINGS`:

```python
Binding("ctrl+b", "back_to_catalog", "Catalog", priority=True),
```

Priority ensures it fires regardless of input widget focus. Available at any point in the practice flow (typing, pass/fail prompt, session complete, empty screen).

### State reset

A `_reset_session_state()` method zeroes out all session state:

- `queue` → `[]`
- `total_reviewed` → `0`
- `total_cards` → `0`
- `_pass_counts` → `{}`
- `_awaiting_gen_grade`, `_awaiting_recall_grade`, `_awaiting_advance` → `False`
- `_pending_requeue` → `None`
- `_current_item` → `None`
- `_last_diff_markup` → `""`
- `showing_stats` → `False`
- `practice_mode` → `False`
- `ordered_practice` → `False`
- `start_level` → reset to original CLI value (stored as `_original_start_level` in `__init__`)

### Action flow

1. `action_back_to_catalog()` calls `_reset_session_state()`
2. Clears all visible widgets (card-header, question, masked-text, result, stats-display) and hides the input
3. Pushes `CatalogScreen(self.conn, self.deck_filter)` with `_on_catalog_result` as callback

This reuses the exact same catalog→practice transition path already used in `on_mount`.

### Scope

- Available from all session types: catalog-launched, CLI-flag-launched (`--practice`, `--source`, etc.), and paste mode
- Catalog always resets fresh (no preserved selections)
- No changes to `CatalogScreen` — it already works correctly for this flow

### Files changed

- `src/knowledge_base/srs/generation_tui.py` — add binding, `_reset_session_state()`, `action_back_to_catalog()`
- Tests for the new behavior
