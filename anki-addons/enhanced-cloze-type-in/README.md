# Enhanced Cloze Type-In

Fork of Enhanced Cloze (1990296174) that replaces clickable cloze reveals with
type-in input fields and character-level diff checking.

## Installation

Symlink this directory into your Anki addons folder:

    ln -s /path/to/brain-training/anki-addons/enhanced-cloze-type-in \
          ~/.local/share/Anki2/addons21/enhanced_cloze_type_in

Restart Anki. The "Enhanced Cloze Type-In 1.0" note type will be created
automatically.

## Usage

Create notes using the "Enhanced Cloze Type-In 1.0" note type. During review,
type your answers and press Enter to check each cloze independently.

- **Enter** — check the current input against the expected answer
- **Tab** — move to the next input field
- **N** — reveal next pseudo-cloze
- **Shift+N** — toggle all pseudo-clozes

Correct answers show in green. Incorrect answers show a character-level diff
with Expected and Got rows.
