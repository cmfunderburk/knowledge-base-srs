# Enhanced Cloze Type-In: Design Spec

## Overview

A fork of the Enhanced Cloze Anki addon (1990296174) that replaces clickable
cloze reveals with inline type-in input fields. Each genuine cloze becomes a
text input; on Enter, a character-level diff comparison shows what was correct
and what was wrong. The user still self-grades with Anki's answer buttons.

## Requirements

- Separate note type ("Enhanced Cloze Type-In 1.0") coexisting with the
  original Enhanced Cloze
- Genuine clozes render as inline input fields instead of clickable pink spans
- Each input checks independently on Enter, showing a character-level diff
- Pseudo-clozes remain as clickable blue reveal spans (unchanged from original)
- Desktop Anki support only (mobile deferred)

## Project Structure

Lives at `anki-addons/enhanced-cloze-type-in/` in the brain-training repo.
Installed via symlink into Anki's addons directory.

```
anki-addons/enhanced-cloze-type-in/
├── __init__.py              # Entry point, hooks
├── manifest.json            # Addon metadata (new package ID)
├── config.py                # Config management
├── config.json              # Default settings
├── model.py                 # Note type creation/update
├── patches.py               # Cloze validation suppression
├── editor.py                # Editor hooks (Cloze99, shortcuts)
├── constants.py             # Model name, version, paths
├── compat.py                # Backwards compatibility
├── setup_jquery.py          # jQuery injection
├── note_type/
│   ├── Enhanced_Cloze_TypeIn_Front_Side.html
│   ├── Enhanced_Cloze_TypeIn_Back_Side.html
│   └── Enhanced_Cloze_TypeIn_CSS.css
└── resources/
    └── _jquery.min.js
```

## Note Type

**Name:** "Enhanced Cloze Type-In 1.0"

**Fields (5, same as original):**
1. Content (ord=0) — main field with cloze deletions
2. Note (ord=1, optional) — custom notes
3. Mnemonics (ord=2, optional) — memory aids
4. Extra (ord=3, optional) — additional info
5. Cloze99 (ord=4, sticky, hidden) — prevents "no cloze" warnings

**Template:** Single template with front and back sides.

## Front Template: Type-In Behavior

### Cloze Rendering

`prepareEnhancedClozesHTML()` is modified so that genuine clozes render as
inline `<input>` elements instead of clickable spans:

- Input fields are styled to fit inline with surrounding text (matching font
  size, subtle border/background)
- Width has a reasonable min/max range (120px-400px) so it doesn't give away
  answer length precisely
- Pseudo-clozes render as clickable blue spans, unchanged from the original

### Interaction Per Cloze

Each genuine cloze input field operates independently:

1. **Unchecked state:** Input field is editable with a subtle
   border/background indicating it's active
2. **Press Enter:** The cloze is checked — the input is replaced inline with
   a character-level diff comparison
3. **All checked:** Once every genuine cloze has been submitted, the card is
   effectively answered and ready for grading

### Keyboard Navigation

- **Enter:** Check the current field
- **Tab:** Move to the next unchecked input field

### Diff Comparison

After submitting a cloze input:

- **Normalization:** Trim whitespace, collapse multiple spaces before
  comparing. Otherwise the raw strings are compared (case and punctuation
  matter).
- **Algorithm:** Character-level diff, matching Anki's built-in type-answer
  behavior.
- **Display:**
  - If exactly correct: show the answer in green, inline
  - If incorrect: show expected answer with green (matching) and red
    (missing/different) highlighting; show your answer with green (matching)
    and red (wrong/extra) highlighting
  - The diff replaces the input inline — no popouts or extra vertical space

### Back Side

Shows the full content with all cloze answers revealed, same as original
Enhanced Cloze back side behavior. Diff feedback is front-side only.

## Python Layer

Copied from the original Enhanced Cloze with renamed identifiers:

- **`constants.py`:** Model name "Enhanced Cloze Type-In 1.0", new version
  string, updated template paths
- **`model.py`:** Same 5 fields, same Cloze99 mechanism. Points to new
  templates. Created on profile load, auto-updated on version bump.
- **`patches.py`:** Identical cloze validation suppression (custom Content
  field needs same patches)
- **`editor.py`:** Identical Cloze99 fill/remove logic and c1-start shortcut
- **`config.json`:** Keep scroll behavior and pseudo-cloze reveal settings.
  Remove genuine cloze reveal shortcuts (now type-in, not clickable). Add
  `typeInCaseSensitive: false` placeholder (not wired up initially).
- **`__init__.py`:** Same hook registration with renamed imports

No new Anki hooks or patches needed. Type-in behavior is entirely in the JS
template.

## Configuration

Defaults in `config.json`:

```json
{
    "scrollToClozeOnToggle": true,
    "animateScroll": true,
    "showHintsForPseudoClozes": true,
    "underlineRevealedPseudoClozes": false,
    "revealPseudoClozesByDefault": false,
    "revealNextPseudoClozeShortcut": "N",
    "revealAllPseudoClozesShortcut": "Shift+N",
    "swapLeftAndRightBorderActions": false,
    "typeInCaseSensitive": false
}
```

No config UI — edit `config.json` directly for now.

## Non-Goals (Deferred)

- Mobile/AnkiDroid/AnkiMobile support
- Fuzzy matching / case-insensitive toggle (placeholder config exists)
- Config UI with tabs/dialogs
- Auto-scoring integration (auto-pass/fail based on correctness)
- MathJax support in type-in fields
