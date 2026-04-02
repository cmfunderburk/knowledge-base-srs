# Enhanced Cloze Type-In Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fork the Enhanced Cloze Anki addon to create a new note type where genuine clozes are type-in input fields with character-level diff checking, instead of clickable reveal spans.

**Architecture:** Full copy of the Enhanced Cloze addon (1990296174) with a new note type name ("Enhanced Cloze Type-In 1.0"). The Python layer is nearly identical (model registration, cloze validation patches, editor hooks). The key change is in the front-side HTML/JS template: genuine clozes render as `<input>` elements; pressing Enter on each field runs a character-level diff and displays inline feedback. Pseudo-clozes remain clickable reveal spans.

**Tech Stack:** Python (Anki addon API, PyQt), HTML/JS/CSS (card templates), jQuery (already bundled)

---

## File Structure

```
anki-addons/enhanced-cloze-type-in/
├── __init__.py                  # Entry point — hooks into Anki on profile load
├── manifest.json                # Addon metadata
├── config.json                  # Default config values
├── config.py                    # Config management (simplified, no UI)
├── constants.py                 # MODEL_NAME, paths, version info
├── compat.py                    # Backwards compatibility aliases
├── model.py                     # Note type creation/update logic
├── patches.py                   # Cloze validation suppression
├── editor.py                    # Cloze99 fill/remove, cloze shortcut
├── setup_jquery.py              # jQuery injection into media folder
├── menu.py                      # Tools menu entries
├── ankiaddonconfig/             # Copied from original (config UI library)
├── lib/                         # Copied from original (packaging library)
├── resources/
│   └── _jquery.min.js           # Copied from original
└── note_type/
    ├── __init__.py              # Empty module init
    ├── model.py                 # Note type dict definition
    ├── Enhanced_Cloze_TypeIn_Front_Side.html   # Modified: type-in + diff
    ├── Enhanced_Cloze_TypeIn_Back_Side.html     # Minor tweaks from original
    └── Enhanced_Cloze_TypeIn_CSS.css            # Extended with input/diff styles
```

---

### Task 1: Scaffold the addon directory with copied boilerplate

Copy the original addon's Python files, vendored libraries, and resources. Rename identifiers to use the new model name. This task produces the full Python layer — everything except the templates.

**Files:**
- Create: `anki-addons/enhanced-cloze-type-in/` (entire directory tree)
- Source: `/home/cmf/.local/share/Anki2/addons21/1990296174/` (original addon)

- [ ] **Step 1: Copy vendored dependencies and resources verbatim**

```bash
mkdir -p anki-addons/enhanced-cloze-type-in/note_type
mkdir -p anki-addons/enhanced-cloze-type-in/resources

# Copy vendored libraries (no changes needed)
cp -r /home/cmf/.local/share/Anki2/addons21/1990296174/ankiaddonconfig \
      anki-addons/enhanced-cloze-type-in/ankiaddonconfig
cp -r /home/cmf/.local/share/Anki2/addons21/1990296174/lib \
      anki-addons/enhanced-cloze-type-in/lib

# Copy jQuery
cp /home/cmf/.local/share/Anki2/addons21/1990296174/resources/_jquery.min.js \
   anki-addons/enhanced-cloze-type-in/resources/_jquery.min.js

# Copy LICENSE
cp /home/cmf/.local/share/Anki2/addons21/1990296174/LICENSE \
   anki-addons/enhanced-cloze-type-in/LICENSE 2>/dev/null || true
```

- [ ] **Step 2: Create `manifest.json`**

```json
{
    "name": "Enhanced Cloze Type-In",
    "package": "enhanced_cloze_type_in",
    "author": "cmf (forked from RisingOrange)",
    "version": "1.0.0",
    "homepage": "",
    "conflicts": []
}
```

- [ ] **Step 3: Create `config.json`**

```json
{
    "scrollToClozeOnToggle": true,
    "animateScroll": true,
    "showHintsForPseudoClozes": true,
    "underlineRevealedPseudoClozes": false,
    "revealPseudoClozesByDefault": false,
    "revealNextPseudoClozeShortcut": "N",
    "revealAllPseudoClozesShortcut": "Shift+N",
    "swapLeftAndRightBorderActions": false
}
```

Note: no genuine cloze reveal shortcuts (those are type-in fields now).

- [ ] **Step 4: Create `constants.py`**

```python
from pathlib import Path

from anki.buildinfo import version as anki_version
from .lib.packaging.version import Version  # type: ignore

MODEL_NAME = "Enhanced Cloze Type-In 1.0"
ANKI_VERSION = Version(anki_version)
NOTE_TYPE_DIR = Path(__file__).parent / "note_type"
```

- [ ] **Step 5: Create `compat.py`**

Copy verbatim from original — no changes needed.

```python
import aqt
from anki import notes


def add_compatibility_aliases() -> None:
    add_compatibility_alias(
        notes.Note,
        "note_type",
        "model",
    )
    add_compatibility_alias(aqt.mw.col.models, "by_name", "byName")
    add_compatibility_alias(aqt.mw.col.models, "field_names", "fieldNames")
    add_compatibility_alias(aqt.mw.col.models, "field_map", "fieldMap")
    add_compatibility_alias(aqt.editor.Editor, "call_after_note_saved", "saveNow")
    add_compatibility_alias(aqt.mw.col, "get_note", "getNote")
    add_compatibility_alias(aqt.mw.col, "find_notes", "findNotes")


def add_compatibility_alias(namespace, new_name: str, old_name: str) -> bool:
    if new_name not in dir(namespace):
        setattr(namespace, new_name, getattr(namespace, old_name))
        return True

    return False
```

- [ ] **Step 6: Create `setup_jquery.py`**

Copy verbatim from original — no changes needed.

```python
import shutil

from aqt.gui_hooks import profile_did_open

from pathlib import Path
import aqt

JQUERY_FILE_NAME = "_jquery.min.js"
JQUERY_PATH = Path(__file__).parent / "resources" / JQUERY_FILE_NAME


def setup_maybe_add_jquery_to_media_folder() -> None:
    profile_did_open.append(_maybe_add_jquery_to_media_folder)


def _maybe_add_jquery_to_media_folder() -> None:
    media_folder = Path(aqt.mw.col.media.dir())
    media_folder_jquery_path = media_folder / JQUERY_FILE_NAME
    if not media_folder_jquery_path.exists():
        shutil.copy(JQUERY_PATH, media_folder_jquery_path)
```

- [ ] **Step 7: Create `editor.py`**

Copy from original, update `MODEL_NAME` import source (already handled by the import from `.constants`).

```python
import re
from typing import Callable, List, Tuple

from anki.hooks import note_will_flush
from anki.notes import Note
from aqt.editor import Editor
from aqt.gui_hooks import editor_did_init_shortcuts
from aqt.qt import Qt

from .constants import ANKI_VERSION, MODEL_NAME
from .lib.packaging.version import Version  # type: ignore


def maybe_fill_in_or_remove_cloze99(note: Note) -> None:
    def in_use_clozes():
        cloze_start_regex = r"{{c\d+::"
        cloze_start_matches = re.findall(cloze_start_regex, note["Content"])
        return [int(re.sub(r"\D", "", x)) for x in set(cloze_start_matches)]

    if note and note.note_type()["name"] == MODEL_NAME:
        if in_use_clozes():
            note["Cloze99"] = ""
        else:
            note["Cloze99"] = "{{c1::.}}"


def make_cloze_shortcut_start_at_cloze1(shortcuts: List[Tuple], editor: Editor) -> None:
    original_onCloze = Editor.onCloze

    def myOnCloze(self) -> None:
        if self.note.note_type()["name"] == MODEL_NAME:
            self.call_after_note_saved(lambda: _myOnCloze(editor), keepFocus=True)
        else:
            original_onCloze(self)

    def _myOnCloze(self) -> None:
        highest = 0
        val = self.note["Content"]
        m = re.findall(r"\{\{c(\d+)::", val)
        if m:
            highest = max(highest, sorted([int(x) for x in m])[-1])
        if not self.mw.app.keyboardModifiers() & Qt.KeyboardModifier.AltModifier:
            highest += 1
        highest = max(1, highest)
        self.web.eval("wrap('{{c%d::', '}}');" % highest)

    replace_shortcut(shortcuts, "Ctrl+Shift+C", lambda: myOnCloze(editor))
    replace_shortcut(shortcuts, "Ctrl+Shift+Alt+C", lambda: myOnCloze(editor))


def replace_shortcut(
    shortcuts: List[Tuple],
    key_combination: str,
    func: Callable[[], None],
) -> None:
    existing = next((x for x in shortcuts if x[0] == key_combination), None)
    if existing is not None:
        shortcuts.remove(existing)
    shortcuts.append((key_combination, func))


def setup_editor() -> None:
    note_will_flush.append(maybe_fill_in_or_remove_cloze99)
    if ANKI_VERSION < Version("2.1.50"):
        editor_did_init_shortcuts.append(make_cloze_shortcut_start_at_cloze1)
```

- [ ] **Step 8: Create `patches.py`**

Copy from original — only change is the `MODEL_NAME` import which already comes from `.constants`.

```python
from anki.notes import Note
from aqt import mw
from aqt.editor import Editor
from aqt.gui_hooks import add_cards_will_add_note
from aqt.utils import tr

from .constants import ANKI_VERSION, MODEL_NAME
from .lib.packaging.version import Version  # type: ignore


def setup_prevent_warnings_about_clozes() -> None:
    if ANKI_VERSION == Version("2.1.26"):
        from anki.models import ModelManager

        original_availableClozeOrds = (
            ModelManager._availClozeOrds
        )

        def new_availClozeOrds(self, m, flds: str, allowEmpty: bool = True):
            if m["name"] != MODEL_NAME:
                return original_availableClozeOrds(self, m, flds, allowEmpty)
            return [0]

        ModelManager._availClozeOrds = new_availClozeOrds
    elif ANKI_VERSION < Version("2.1.45"):
        original_cloze_numbers_in_fields = Note.cloze_numbers_in_fields

        def new_cloze_numbers_in_fields(self):
            if self.note_type()["name"] != MODEL_NAME:
                return original_cloze_numbers_in_fields(self)
            return [0]

        Note.cloze_numbers_in_fields = new_cloze_numbers_in_fields
    else:
        from anki.notes import NoteFieldsCheckResult

        original_update_duplicate_display = (
            Editor._update_duplicate_display
        )

        def _update_duplicate_display_ignore_cloze_problems_for_enh_clozes(
            self, result
        ) -> None:
            if self.note.note_type()["name"] == MODEL_NAME:
                if result == NoteFieldsCheckResult.NOTETYPE_NOT_CLOZE:
                    result = NoteFieldsCheckResult.NORMAL
                if result == NoteFieldsCheckResult.FIELD_NOT_CLOZE:
                    result = NoteFieldsCheckResult.NORMAL
            original_update_duplicate_display(self, result)

        Editor._update_duplicate_display = (
            _update_duplicate_display_ignore_cloze_problems_for_enh_clozes
        )

        def ignore_some_cloze_problems_for_enh_clozes(problem, note):
            if note.note_type()["name"] != MODEL_NAME:
                return problem
            if problem == tr.adding_cloze_outside_cloze_notetype():
                return None
            elif problem == tr.adding_cloze_outside_cloze_field():
                return None
            else:
                return problem

        add_cards_will_add_note.append(ignore_some_cloze_problems_for_enh_clozes)

        original_fields_check = Note.fields_check

        def new_fields_check(self):
            result = original_fields_check(self)
            if mw.col.models.get(self.mid)["name"] != MODEL_NAME:
                return result
            if result == NoteFieldsCheckResult.MISSING_CLOZE:
                return None
            else:
                return result

        Note.fields_check = new_fields_check
```

- [ ] **Step 9: Create `note_type/__init__.py`**

```python
# Note type definitions for Enhanced Cloze Type-In addon
```

- [ ] **Step 10: Create `note_type/model.py`**

```python
enhancedModel = {
    "vers": [],
    "name": "Enhanced Cloze Type-In 1.0",
    "tags": [],
    "did": 1,
    "usn": -1,
    "flds": [
        {
            "name": "Content",
            "media": [],
            "sticky": False,
            "rtl": False,
            "ord": 0,
            "font": "Arial",
            "size": 20,
        },
        {
            "name": "Note",
            "media": [],
            "sticky": False,
            "rtl": False,
            "ord": 1,
            "font": "Arial",
            "size": 20,
        },
        {
            "name": "Mnemonics",
            "media": [],
            "sticky": False,
            "rtl": False,
            "ord": 2,
            "font": "Arial",
            "size": 20,
        },
        {
            "name": "Extra",
            "media": [],
            "sticky": False,
            "rtl": False,
            "ord": 3,
            "font": "Arial",
            "size": 20,
        },
        {
            "name": "Cloze99",
            "media": [],
            "sticky": True,
            "rtl": False,
            "ord": 4,
            "font": "Arial",
            "size": 1,
        },
    ],
    "sortf": 0,
    "tmpls": [
        {
            "name": "Enhanced Cloze Type-In",
            "qfmt": "",
            "did": None,
            "bafmt": "",
            "afmt": "",
            "ord": 0,
            "bqfmt": "",
        }
    ],
    "mod": 1560146886,
    "latexPost": "\\end{document}",
    "type": 1,
    "id": 0,
    "css": "",
    "latexPre": """\\documentclass[12pt]{article}
\\special{papersize=3in,5in}
\\usepackage[utf8]{inputenc}
\\usepackage{amssymb,amsmath}
\\pagestyle{empty}
\\setlength{\\parindent}{0in}
\\begin{document}
""",
}
```

- [ ] **Step 11: Create `config.py`**

Simplified version — no config UI, just the ConfigManager.

```python
from .ankiaddonconfig import ConfigManager

conf = ConfigManager()


def setup_config():
    pass
```

- [ ] **Step 12: Create `model.py`**

Adapted from original — updated template file paths, simplified update logic (no named-version migration since this is v1), removed config option migration helpers.

```python
import re
from copy import deepcopy
from typing import Optional, Tuple

from aqt import mw
from aqt.gui_hooks import profile_did_open, sync_did_finish

from .constants import MODEL_NAME, NOTE_TYPE_DIR
from .note_type.model import enhancedModel
from .compat import add_compatibility_aliases

try:
    from aqt.models import NotetypeDict
except Exception:
    pass


def setup_maybe_update_model_on_startup() -> None:
    def on_profile_did_open():
        add_compatibility_aliases()

        if not mw.can_auto_sync():
            add_or_update_model()
        else:
            def fn():
                add_or_update_model()
                sync_did_finish.remove(fn)

            sync_did_finish.append(fn)

    profile_did_open.append(on_profile_did_open)


def _new_version_available() -> bool:
    return current_version() is None or current_version() < incoming_version()


def current_version() -> Optional[Tuple[int, ...]]:
    return version(mw.col.models.by_name(MODEL_NAME))


def incoming_version() -> Optional[Tuple[int, ...]]:
    return version(enhanced_cloze())


def version(note_type: "NotetypeDict") -> Optional[Tuple[int, ...]]:
    front = note_type["tmpls"][0]["qfmt"]
    m = re.match("<!-- VERSION (.+?) -->", front)
    if not m:
        return None
    return tuple(map(int, m.group(1).split(".")))


def set_version(front: str, ver: Tuple[int, ...]) -> str:
    return re.sub(
        "<!-- VERSION (.+?) -->",
        f"<!-- VERSION {'.'.join(map(str, ver))} -->",
        front,
    )


def add_or_update_model() -> None:
    model = mw.col.models.by_name(MODEL_NAME)
    if not model:
        mw.col.models.add(enhanced_cloze())
        return

    if not _new_version_available():
        return

    seperator = "<!-- ENHANCED_CLOZE_TYPE_IN -->"
    cur_front = model["tmpls"][0]["qfmt"]
    incoming_front = enhanced_cloze()["tmpls"][0]["qfmt"]

    cur_sep_m = re.search(seperator, cur_front)
    if not cur_sep_m:
        model["tmpls"][0]["qfmt"] = incoming_front
    else:
        incoming_sep_m = re.search(seperator, incoming_front)
        cur_before_sep = cur_front[: cur_sep_m.start()]
        incoming_after_sep = incoming_front[incoming_sep_m.end():]
        new_front = f"{cur_before_sep}{seperator}{incoming_after_sep}"
        new_front = set_version(new_front, incoming_version())
        model["tmpls"][0]["qfmt"] = new_front

    model["tmpls"][0]["afmt"] = enhanced_cloze()["tmpls"][0]["afmt"]
    mw.col.models.update_dict(model)


def enhanced_cloze() -> "NotetypeDict":
    result = deepcopy(enhancedModel)
    load_enhanced_cloze(result)
    return result


def load_enhanced_cloze(note_type: "NotetypeDict") -> None:
    front_path = NOTE_TYPE_DIR / "Enhanced_Cloze_TypeIn_Front_Side.html"
    css_path = NOTE_TYPE_DIR / "Enhanced_Cloze_TypeIn_CSS.css"
    back_path = NOTE_TYPE_DIR / "Enhanced_Cloze_TypeIn_Back_Side.html"

    with open(front_path) as f:
        front = f.read()
    with open(back_path) as f:
        back = f.read()
    with open(css_path) as f:
        styling = f.read()

    note_type["tmpls"][0]["qfmt"] = front
    note_type["tmpls"][0]["afmt"] = back
    note_type["css"] = styling


def update_model_options_with_config_values() -> None:
    from .config import conf

    conf_lines = []
    for key in conf:
        value = conf[key]
        if isinstance(value, str):
            value = f'"{value}"'
        elif isinstance(value, bool):
            value = "true" if value else "false"
        conf_lines.append(f"var {key}={value}")
    conf_str = "\n".join(conf_lines)

    model = mw.col.models.by_name(MODEL_NAME)
    front = model["tmpls"][0]["qfmt"]
    front = re.sub(
        r"<script>[\w\W]*?</script>(?=\n<!-- CONFIG END -->)",
        f"<script>\n{conf_str}\n</script>",
        front,
    )
    assert conf_str in front, "Could not update note type options"
    model["tmpls"][0]["qfmt"] = front
    mw.col.models.update_dict(model)
```

- [ ] **Step 13: Create `menu.py`**

```python
from aqt import mw
from aqt.gui_hooks import main_window_did_init
from aqt.qt import QMenu
from aqt.utils import askUser, qconnect, tooltip

from .constants import MODEL_NAME
from .model import add_or_update_model, enhanced_cloze


def setup_enhanced_cloze_menu() -> None:
    def on_main_window_did_init():
        menu: QMenu = mw.form.menuTools
        submenu = menu.addMenu("Enhanced Cloze Type-In")
        add_reset_notetype_action_to_menu(submenu)
        add_reset_css_action_to_menu(submenu)

    main_window_did_init.append(on_main_window_did_init)


def add_reset_notetype_action_to_menu(menu: QMenu) -> None:
    action = menu.addAction("Reset note type")

    def on_triggered():
        if not askUser(
            "This will reset the Enhanced Cloze Type-In note type to its default version.\n\n"
            "Note: After doing this the next time you synchronize Anki will require a full sync to AnkiWeb.\n\n"
            "Continue?",
        ):
            return

        current_model = mw.col.models.by_name(MODEL_NAME)
        if not current_model:
            add_or_update_model()
            return

        default_model = enhanced_cloze()
        default_model["id"] = current_model["id"]
        default_model["usn"] = -1
        mw.col.models.update_dict(default_model)
        tooltip("Successfully reset Enhanced Cloze Type-In note type.")

    qconnect(action.triggered, on_triggered)


def add_reset_css_action_to_menu(menu: QMenu) -> None:
    action = menu.addAction("Reset note type styling (css)")

    def on_triggered() -> None:
        if not askUser(
            "This will reset the styling (css) of the Enhanced Cloze Type-In note type to its default version.\n\nContinue?"
        ):
            return

        current_model = mw.col.models.by_name(MODEL_NAME)
        if not current_model:
            add_or_update_model()
            return

        current_model["css"] = enhanced_cloze()["css"]
        mw.col.models.update_dict(current_model)
        tooltip("Successfully reset Enhanced Cloze Type-In note type styling.")

    qconnect(action.triggered, on_triggered)
```

- [ ] **Step 14: Create `__init__.py`**

```python
from aqt.gui_hooks import profile_did_open

from .compat import add_compatibility_aliases
from .config import setup_config
from .editor import setup_editor
from .setup_jquery import setup_maybe_add_jquery_to_media_folder
from .menu import setup_enhanced_cloze_menu
from .model import setup_maybe_update_model_on_startup
from .patches import setup_prevent_warnings_about_clozes

profile_did_open.append(add_compatibility_aliases)

setup_config()
setup_maybe_add_jquery_to_media_folder()
setup_maybe_update_model_on_startup()
setup_editor()
setup_enhanced_cloze_menu()
setup_prevent_warnings_about_clozes()
```

- [ ] **Step 15: Commit the scaffold**

```bash
git add anki-addons/enhanced-cloze-type-in/
git commit -m "feat: scaffold Enhanced Cloze Type-In addon with Python layer"
```

---

### Task 2: Create the CSS template

Add styling for input fields, diff feedback, and type-in-specific states, building on the original Enhanced Cloze CSS.

**Files:**
- Create: `anki-addons/enhanced-cloze-type-in/note_type/Enhanced_Cloze_TypeIn_CSS.css`

- [ ] **Step 1: Write the CSS file**

This extends the original CSS with styles for type-in inputs and diff results.

```css
#card-body {
    font: 17px/1.65em 'Avenir Next';
    text-align: justify;
    margin-top: 50px;
    margin-bottom: 60px;
}

.content {
    padding-left: 0.5em;
    border-left: 4px solid transparent;
}

.header {
    font: bold 17px/1.5em;
    padding-left: 0.5em;
}

.header-red {
    border-left: 4px solid #db4437;
    color: #db4437;
}

.header-green {
    border-left: 4px solid #0f9d58;
    color: #0f9d58;
}

.header-blue {
    border-left: 4px solid #4285f4;
    color: #4285f4;
}

.header-yellow {
    border-left: 4px solid #f4b400;
    color: #f4b400;
}

/* Pseudo clozes — unchanged from original */
.pseudo-cloze[show-state="hint"] {
    border-bottom: 2px solid #4285f4;
    background-color: #87b1ff;
}

/* Type-in input fields for genuine clozes */
.cloze-input {
    font: inherit;
    font-size: 0.95em;
    color: inherit;
    background-color: rgba(255, 150, 175, 0.15);
    border: 1px solid #ff5c82;
    border-radius: 3px;
    padding: 2px 6px;
    min-width: 120px;
    max-width: 400px;
    outline: none;
    box-sizing: border-box;
}

.cloze-input:focus {
    border-color: #ff5c82;
    box-shadow: 0 0 0 2px rgba(255, 92, 130, 0.25);
}

.cloze-input::placeholder {
    color: rgba(255, 92, 130, 0.5);
    font-style: italic;
}

/* Diff result container — replaces input after checking */
.cloze-diff {
    display: inline;
}

.cloze-diff-correct {
    color: #0f9d58;
    font-weight: bold;
}

.cloze-diff-row {
    display: block;
    margin: 1px 0;
}

.cloze-diff-row .diff-label {
    font-size: 0.75em;
    color: #888;
    margin-right: 4px;
}

.diff-good {
    color: #0f9d58;
}

.diff-bad {
    color: #db4437;
    text-decoration: line-through;
}

.diff-missing {
    color: #db4437;
    text-decoration: underline;
}

/* Border click zones */
#show-one-cloze-left,
#show-one-cloze-right,
#no-more-cloze {
    height: 100%;
    width: 30px;
    position: fixed;
    z-index: 9;
    top: 0;
    background-color: transparent;
}

#show-one-cloze-left {
    left: 0;
}

#show-one-cloze-right {
    right: 0;
}

#no-more-cloze {
    width: 10px;
    background-color: #db4437;
    left: 0;
    display: none;
}

.mobile ol,
.mobile ul,
.mobile li {
    margin-left: -0.5em;
}

.mobile li {
    margin: 0.1em, inherit;
}

table {
    border-collapse: collapse;
    margin: 0.5em;
}

thead tr,
tfoot tr {
    border-top: 2px solid #0f9d58;
    border-bottom: 2px solid #0f9d58;
}

td,
th {
    border: 1px solid #0f9d58;
    padding: 0.3em 0.5em;
}

hr {
    border-top: 1px solid #aaaaaa;
    width: 100%;
    margin: 0;
    padding: 0;
}

pre {
    border-left: 2px solid #0f9d58;
    padding-left: 10px;
}

code,
kbd,
var,
samp,
tt {
    background-color: #fdf3d6;
}

.disable-select {
    -webkit-touch-callout: none;
    user-select: none;
}
```

- [ ] **Step 2: Commit**

```bash
git add anki-addons/enhanced-cloze-type-in/note_type/Enhanced_Cloze_TypeIn_CSS.css
git commit -m "feat: add CSS template with type-in input and diff styles"
```

---

### Task 3: Create the back-side template

The back side is nearly identical to the original — it shows `{{FrontSide}}` and reveals all genuine clozes. The only difference is that on the back side, genuine clozes that haven't been checked yet should show their answers directly (not as input fields).

**Files:**
- Create: `anki-addons/enhanced-cloze-type-in/note_type/Enhanced_Cloze_TypeIn_Back_Side.html`

- [ ] **Step 1: Write the back-side template**

```html
{{FrontSide}}

<span style="display:none">{{cloze:Content}}</span>
<script>
    $(function () {
        $('#note').show(0)
        $('#info').show(0)
        $('#mnemonics').show(0)
        $('#extra').show(0)

        setTimeout(function () {
            // Replace any remaining input fields with their answers
            $('.cloze-input').each(function () {
                var index = $(this).attr('data-index');
                var answer = enhancedClozesData["answers"][index];
                var span = $('<span class="cloze-diff-correct"></span>');
                span.html(answer);
                $(this).replaceWith(span);
            });

            // Reveal any genuine clozes that are still in hint state
            // (this handles the case where the front side had clickable
            // genuine clozes from the original code path)
            $('.genuine-cloze').each(function (index, elem) {
                toggleCloze(elem, 'answer')
            });

            // Reveal pseudo-clozes
            $('.pseudo-cloze').each(function (index, elem) {
                toggleCloze(elem, 'answer')
            });
        }, 0)
    })
</script>
```

- [ ] **Step 2: Commit**

```bash
git add anki-addons/enhanced-cloze-type-in/note_type/Enhanced_Cloze_TypeIn_Back_Side.html
git commit -m "feat: add back-side template"
```

---

### Task 4: Create the front-side template with type-in and diff logic

This is the core task. The front-side template is based on the original Enhanced Cloze but modifies `prepareEnhancedClozesHTML()` to render genuine clozes as `<input>` elements, adds a `charDiff()` function for character-level diffing, and adds `checkClozeInput()` to handle Enter key submission and inline diff display.

**Files:**
- Create: `anki-addons/enhanced-cloze-type-in/note_type/Enhanced_Cloze_TypeIn_Front_Side.html`

- [ ] **Step 1: Write the front-side template**

The template preserves the original structure (config block, card body HTML, ENHANCED_CLOZE_TYPE_IN separator, script). Key changes from the original are marked with comments.

```html
<!-- VERSION 1.0 -->
<script>
    var scrollToClozeOnToggle = true
    var animateScroll = true
    var showHintsForPseudoClozes = true
    var underlineRevealedPseudoClozes = false
    var revealPseudoClozesByDefault = false
    var swapLeftAndRightBorderActions = false
    var revealNextPseudoClozeShortcut = "N"
    var revealAllPseudoClozesShortcut = "Shift+N"
</script>
<!-- CONFIG END -->

<div id="card-body">
    <div id="main-section" class="content">
        <span id="enhanced-clozes"></span>
    </div>
    <br>
    <br>
    <hr>
    <br>
    <p class="" style="margin: 5.5px;"></p>
    <div>
        {{#Note}}
        <div id="note-section">
            <div id="note-header" class="header header-red" onclick="showNextElement(this)">
                Note
            </div>
            <div id="note" class="content" style="display:none">
                {{edit:Note}}
            </div>
        </div>
        <br>
        <p class="" style="margin: 5.5px;"></p>
        {{/Note}}

        {{#Mnemonics}}
        <div id="mnemonics-section">
            <div id="mnemonics-header" class="header header-green" onclick="showNextElement(this)">
                Mnemonics
            </div>
            <div id="mnemonics" class="content" style="display:none">
                {{edit:Mnemonics}}
            </div>
        </div>
        <br>
        <p class="" style="margin: 5.5px;"></p>
        {{/Mnemonics}}

        {{#Extra}}
        <div id="extra-section">
            <div id="extra-header" class="header header-yellow" onclick="showNextElement(this)">
                Extra
            </div>
            <div id="extra" class="content" style="display:none">
                {{edit:Extra}}
            </div>
        </div>
        <br>
        <p class="" style="margin: 5.5px;"></p>
        {{/Extra}}

        <div id="info-section">
            <div id="info-header" class="header header-blue" onclick="showNextElement(this)">
                Information
            </div>
            <div id="info" class="content" style="display:none">
                <div>
                    <b>Deck</b>: <br><i>{{Deck}}</i>
                </div>
                <br>
                {{#Tags}}
                <div id="tags">
                    <b>Tags</b>: <br><i>{{Tags}}</i>
                </div>
                {{/Tags}}
            </div>
        </div>
        <br>

        <div id="functional-elements">
            <div id="show-one-cloze-left"></div>
            <div id="show-one-cloze-right"></div>
            <div id="no-more-cloze"></div>
        </div>
    </div>
</div>

<!-- ENHANCED_CLOZE_TYPE_IN -->
<span id="enhanced-cloze-content" style="display:none">{{Content}}</span>
<span style="display:none;" id="edit-clozes">{{edit:cloze:Content}}</span>

<span style="display:none">{{cloze:Content}}</span>
<span style="display:none">{{cloze:Cloze99}}</span>

<script>
    var enhancedClozesData = {
        "clozeId": [],
        "answers": [],
        "hints": [],
    }

    // Track which genuine cloze inputs have been checked
    var checkedClozes = {}

    async function enhancedClozesMain() {

        const clozeRegex = /{(?:){c(\d+)::([\W\w]*?)(?:::([\W\w]*?))?}}/g

        await maybeInjectJquery()
        defineEnhancedClozeAddEventListener()
        prepareEnhancedClozesData()
        prepareEnhancedClozesHTML()
        maybeScrollToFirstInput()
        setupPseudoClozeEvents()
        setupTypeInEvents()
        insertStyling()

        function prepareEnhancedClozesData() {
            var content = document.getElementById("enhanced-cloze-content").innerHTML
            var match = clozeRegex.exec(content);
            while (match != null) {
                enhancedClozesData["clozeId"].push(match[1])
                enhancedClozesData["answers"].push(match[2])
                enhancedClozesData["hints"].push(match[3] !== undefined ? match[3] : "")
                match = clozeRegex.exec(content);
            }
        }

        function prepareEnhancedClozesHTML() {
            var ord =
                `{{#c1}}1{{/c1}}{{#c2}}2{{/c2}}{{#c3}}3{{/c3}}{{#c4}}4{{/c4}}{{#c5}}5{{/c5}}{{#c6}}6{{/c6}}{{#c7}}7{{/c7}}{{#c8}}8{{/c8}}{{#c9}}9{{/c9}}{{#c10}}10{{/c10}}{{#c11}}11{{/c11}}{{#c12}}12{{/c12}}{{#c13}}13{{/c13}}{{#c14}}14{{/c14}}{{#c15}}15{{/c15}}{{#c16}}16{{/c16}}{{#c17}}17{{/c17}}{{#c18}}18{{/c18}}{{#c19}}19{{/c19}}{{#c20}}20{{/c20}}{{#c21}}21{{/c21}}{{#c22}}22{{/c22}}{{#c23}}23{{/c23}}{{#c24}}24{{/c24}}{{#c25}}25{{/c25}}{{#c26}}26{{/c26}}{{#c27}}27{{/c27}}{{#c28}}28{{/c28}}{{#c29}}29{{/c29}}{{#c30}}30{{/c30}}{{#c31}}31{{/c31}}{{#c32}}32{{/c32}}{{#c33}}33{{/c33}}{{#c34}}34{{/c34}}{{#c35}}35{{/c35}}{{#c36}}36{{/c36}}{{#c37}}37{{/c37}}{{#c38}}38{{/c38}}{{#c39}}39{{/c39}}{{#c40}}40{{/c40}}{{#c41}}41{{/c41}}{{#c42}}42{{/c42}}{{#c43}}43{{/c43}}{{#c44}}44{{/c44}}{{#c45}}45{{/c45}}{{#c46}}46{{/c46}}{{#c47}}47{{/c47}}{{#c48}}48{{/c48}}{{#c49}}49{{/c49}}{{#c50}}50{{/c50}}`
            ord = ord.trim()

            var content = document.getElementById("enhanced-cloze-content").innerHTML
            var html = ""
            var ctr = 0
            var prevLastIndex = 0
            match = clozeRegex.exec(content);
            while (match !== null) {
                var startIdx = clozeRegex.lastIndex - match[0].length
                html += content.slice(prevLastIndex, startIdx)

                var isGenuine = ord == enhancedClozesData["clozeId"][ctr]

                if (isGenuine) {
                    // TYPE-IN: render as input field
                    var hint = enhancedClozesData["hints"][ctr]
                    var placeholder = hint ? hint : ""
                    html += `<input type="text" class="cloze-input" data-index="${ctr}" `
                    html += `data-cid="${enhancedClozesData["clozeId"][ctr]}" `
                    html += `placeholder="${placeholder}" autocomplete="off" autocorrect="off" `
                    html += `autocapitalize="off" spellcheck="false">`
                } else {
                    // PSEUDO-CLOZE: render as clickable span (unchanged)
                    html +=
                        `<span class="pseudo-cloze" show-state="hint" cid="${enhancedClozesData["clozeId"][ctr]}" index="${ctr}">${enhancedClozesData["hints"][ctr]}</span>`
                }

                prevLastIndex = clozeRegex.lastIndex
                match = clozeRegex.exec(content);
                ctr += 1
            }
            html += content.slice(prevLastIndex)

            var enhDiv = document.getElementById("enhanced-clozes")
            enhDiv.innerHTML = html

            // Initialize pseudo-cloze display
            $('.pseudo-cloze').each(function (index, elem) {
                toggleCloze(elem, 'hint')
            });

            $('.pseudo-cloze').css('cursor', 'pointer')
            $('.pseudo-cloze').addClass('disable-select')
            $('#show-one-cloze-left').css('cursor', 'pointer')
            $('#show-one-cloze-right').css('cursor', 'pointer')
            $('#show-one-cloze-left').addClass('disable-select')
            $('#show-one-cloze-right').addClass('disable-select')
        }

        function maybeScrollToFirstInput() {
            var firstInput = $('.cloze-input').first()
            if (firstInput.length) {
                if (scrollToClozeOnToggle) {
                    $('html, body').animate({
                        scrollTop: firstInput.offset().top - 60
                    }, animateScroll ? 500 : 0);
                }
                // Focus first input field
                setTimeout(function () {
                    firstInput.focus()
                }, 100)
            }
        }

        function setupPseudoClozeEvents() {
            if (typeof firstTimeLoadingEnhancedCloze === 'undefined') {
                firstTimeLoadingEnhancedCloze = false

                $(document).on('click', '.pseudo-cloze', function (event) {
                    toggleCloze(event.target, 'toggle');
                });

                $(document).on('click', '#show-one-cloze-left', function (event) {
                    revealOneClozeOfAType(swapLeftAndRightBorderActions ? "pseudo" : "pseudo");
                });

                $(document).on('click', '#show-one-cloze-right', function (event) {
                    revealOneClozeOfAType(swapLeftAndRightBorderActions ? "pseudo" : "pseudo");
                });
            }

            setupPseudoClozeKeyEvents()
        }

        function setupPseudoClozeKeyEvents() {
            window.enhancedClozeAddEventListener("keydown", (event) => {
                // Only process shortcuts when not focused on an input
                if (document.activeElement && document.activeElement.classList.contains('cloze-input')) {
                    return
                }
                if (shortcutMatcher(revealNextPseudoClozeShortcut)(event)) {
                    revealOneClozeOfAType("pseudo");
                }
                if (shortcutMatcher(revealAllPseudoClozesShortcut)(event)) {
                    toggleAllClozesOfAType("pseudo");
                }
            })
        }

        function setupTypeInEvents() {
            // Enter key checks the focused input
            $(document).on('keydown', '.cloze-input', function (event) {
                if (event.key === 'Enter') {
                    event.preventDefault()
                    checkClozeInput(this)
                }
            });

            // Tab to next unchecked input
            $(document).on('keydown', '.cloze-input', function (event) {
                if (event.key === 'Tab') {
                    event.preventDefault()
                    var nextInput = $(this).nextAll('.cloze-input').first()
                    if (nextInput.length === 0) {
                        // Wrap around to the first unchecked input
                        nextInput = $('.cloze-input').first()
                    }
                    if (nextInput.length) {
                        nextInput.focus()
                    }
                }
            });
        }


        function insertStyling() {
            if (document.getElementById("enhanced-clozes-style")) return;

            mainSection = document.getElementById("main-section")
            style = document.createElement("style")
            style.id = "enhanced-clozes-style"
            style.innerHTML = `
                .disable-select {
                    -webkit-touch-callout: none;
                    user-select: none;
                }
            `

            if (underlineRevealedPseudoClozes) {
                style.innerHTML += `
                .pseudo-cloze {
                    border-bottom: 1px solid #4285f4;
                    padding-bottom: 1px;
                }`
            }
            mainSection.insertBefore(style, mainSection.children[0])
        }

        function revealOneClozeOfAType(clozeType) {
            if (!$(`.${clozeType}-cloze[show-state="hint"]`).length) {
                $('#no-more-cloze').animate({
                    display: "toggle",
                }, 500);
                return
            }

            var hiddenClozes = $(`.${clozeType}-cloze[show-state="hint"]`)
            if (hiddenClozes.length != 0) {
                revealCloze(hiddenClozes[0]);
            }
        }

        function toggleAllClozesOfAType(clozeType) {
            var allRevealed = !$(`.${clozeType}-cloze[show-state="hint"`).length
            $(`.${clozeType}-cloze`).each(function (index, elem) {
                toggleCloze(elem, allRevealed ? "hint" : "answer");
            })
        }

        function revealCloze(elem) {
            if (!isVisible(elem)) {
                maybeScrollToCloze(elem);
            } else {
                toggleCloze(elem, 'answer');
                if (!isVisible(elem)) {
                    maybeScrollToCloze(elem);
                }
                $(elem).hide(0);
                $(elem).fadeIn(500);
            }
        }

        function isVisible(elm) {
            var rect = elm.getBoundingClientRect();
            var viewHeight = Math.max(document.documentElement.clientHeight, window.innerHeight);
            return !(rect.bottom < 0 || rect.top - viewHeight >= 0);
        }

        function maybeScrollToCloze(elem) {
            if (!scrollToClozeOnToggle) return
            $('html, body').animate({
                scrollTop: $(elem).offset().top - 60
            }, animateScroll ? 500 : 0);
        }

        function defineEnhancedClozeAddEventListener() {
            if (typeof window.enhancedClozeEventListener != "undefined") {
                for (const listener of window.enhancedClozeEventListener) {
                    const type = listener[0]
                    const handler = listener[1]
                    document.removeEventListener(type, handler)
                }
            }
            window.enhancedClozeEventListener = []

            window.enhancedClozeAddEventListener = function (type, handler) {
                document.addEventListener(type, handler)
                window.enhancedClozeEventListener.push([type, handler])
            }
        }

        var specialCharCodes = {
            "-": "minus",
            "=": "equal",
            "[": "bracketleft",
            "]": "bracketright",
            ";": "semicolon",
            "'": "quote",
            "`": "backquote",
            "\\": "backslash",
            ",": "comma",
            ".": "period",
            "/": "slash",
        };

        function shortcutMatcher(shortcut) {
            var shortcutKeys = shortcut.toLowerCase().split(/[+]/).map(key => key.trim())
            var mainKey = shortcutKeys[shortcutKeys.length - 1]
            if (mainKey.length === 1) {
                if (/\d/.test(mainKey)) {
                    mainKey = "digit" + mainKey
                } else if (/[a-zA-Z]/.test(mainKey)) {
                    mainKey = "key" + mainKey
                } else {
                    var code = specialCharCodes[mainKey];
                    if (code) {
                        mainKey = code
                    }
                }
            }
            var ctrl = shortcutKeys.includes("ctrl")
            var shift = shortcutKeys.includes("shift")
            var alt = shortcutKeys.includes("alt")

            var matchShortcut = function (ctrl, shift, alt, mainKey, event) {
                if (event.originalEvent !== undefined) {
                    event = event.originalEvent
                }
                if (mainKey !== event.code.toLowerCase()) return false
                if (ctrl !== (event.ctrlKey || event.metaKey)) return false
                if (shift !== event.shiftKey) return false
                if (alt !== event.altKey) return false
                return true
            }.bind(window, ctrl, shift, alt, mainKey)

            return matchShortcut
        }

        function showNextElement(elem) {
            $(elem).next().show(0);
        };

        async function maybeInjectJquery() {
            if (typeof jQuery === "undefined") {
                await injectScript("_jquery.min.js");
            }
        }

        async function injectScript(src) {
            return new Promise((resolve, reject) => {
                const script = document.createElement('script');
                script.src = src;
                script.async = true;
                script.onload = resolve;
                script.onerror = (event) => {
                    reject(new Error(`Script load error for source: ${src}`));
                };
                document.head.appendChild(script);
            });
        };

    }

    // === Functions defined outside enhancedClozesMain (shared with back side) ===

    function toggleCloze(elem, displayOption) {
        if (elem == null) return

        if (elem.classList.contains("pseudo-cloze"))
            cloze = elem
        else {
            cloze = $(elem).closest(".pseudo-cloze")
            if (cloze == null || cloze.length === 0) return
        }

        var index = $(cloze).attr('index');
        var answer = enhancedClozesData["answers"][index]
        var hint = enhancedClozesData["hints"][index]

        if (!showHintsForPseudoClozes && cloze.classList.contains('pseudo-cloze')) {
            hint = ""
        }

        if (revealPseudoClozesByDefault || answer.startsWith('#')) {
            if (answer.startsWith('#')) {
                answer = answer.slice(1)
            }
            if ($(cloze).attr('class') == 'pseudo-cloze') {
                $(cloze).attr('show-state', 'answer');
                $(cloze).html(answer);
                return
            }
        }

        if (displayOption == 'answer' || (displayOption == 'toggle' && $(cloze).attr('show-state') == 'hint')) {
            $(cloze).attr('show-state', 'answer');
            $(cloze).html(answer);
        } else if (displayOption == 'hint' || (displayOption == 'toggle' && $(cloze).attr('show-state') == 'answer')) {
            $(cloze).attr('show-state', 'hint');
            hint = '&nbsp;&nbsp;[&nbsp;&nbsp;' + hint + '&nbsp;&nbsp;]&nbsp;&nbsp;';
            $(cloze).html(hint);
        }

        try {
            MathJax.Hub.Queue(["Typeset", MathJax.Hub]);
        } catch { }
        try {
            MathJax.typesetPromise()
        } catch { }
    }

    /**
     * Check a cloze input field: compare typed answer to expected,
     * replace input with inline diff feedback.
     */
    function checkClozeInput(inputElem) {
        var $input = $(inputElem)
        var index = $input.attr('data-index')
        var typed = $input.val()
        var expected = enhancedClozesData["answers"][index]

        // Strip HTML tags from expected answer for comparison
        var tmp = document.createElement("div")
        tmp.innerHTML = expected
        var expectedText = tmp.textContent || tmp.innerText || ""

        // Normalize: trim and collapse whitespace
        typed = typed.trim().replace(/\s+/g, ' ')
        expectedText = expectedText.trim().replace(/\s+/g, ' ')

        var diffHtml
        if (typed === expectedText) {
            // Exact match — show in green
            diffHtml = '<span class="cloze-diff"><span class="cloze-diff-correct">' +
                escapeHtml(expectedText) + '</span></span>'
        } else {
            // Show character-level diff
            var diff = charDiff(expectedText, typed)
            diffHtml = '<span class="cloze-diff">'
            diffHtml += '<span class="cloze-diff-row"><span class="diff-label">Expected:</span>' +
                renderDiffExpected(diff) + '</span>'
            diffHtml += '<span class="cloze-diff-row"><span class="diff-label">Got:</span>' +
                renderDiffGot(diff) + '</span>'
            diffHtml += '</span>'
        }

        $input.replaceWith(diffHtml)
        checkedClozes[index] = true
    }

    /**
     * Character-level diff using longest common subsequence.
     * Returns array of operations: {type: 'equal'|'delete'|'insert', text: string}
     * 'delete' = in expected but not typed, 'insert' = in typed but not expected
     */
    function charDiff(expected, typed) {
        var m = expected.length
        var n = typed.length

        // Build LCS table
        var dp = []
        for (var i = 0; i <= m; i++) {
            dp[i] = []
            for (var j = 0; j <= n; j++) {
                if (i === 0 || j === 0) {
                    dp[i][j] = 0
                } else if (expected[i - 1] === typed[j - 1]) {
                    dp[i][j] = dp[i - 1][j - 1] + 1
                } else {
                    dp[i][j] = Math.max(dp[i - 1][j], dp[i][j - 1])
                }
            }
        }

        // Backtrack to get diff operations
        var ops = []
        var i = m, j = n
        while (i > 0 || j > 0) {
            if (i > 0 && j > 0 && expected[i - 1] === typed[j - 1]) {
                ops.unshift({ type: 'equal', text: expected[i - 1] })
                i--
                j--
            } else if (j > 0 && (i === 0 || dp[i][j - 1] >= dp[i - 1][j])) {
                ops.unshift({ type: 'insert', text: typed[j - 1] })
                j--
            } else {
                ops.unshift({ type: 'delete', text: expected[i - 1] })
                i--
            }
        }

        // Merge consecutive operations of the same type
        var merged = []
        for (var k = 0; k < ops.length; k++) {
            if (merged.length > 0 && merged[merged.length - 1].type === ops[k].type) {
                merged[merged.length - 1].text += ops[k].text
            } else {
                merged.push({ type: ops[k].type, text: ops[k].text })
            }
        }

        return merged
    }

    /**
     * Render the "Expected" row of the diff.
     * Equal parts in green, deleted (missing from typed) parts in red underline.
     */
    function renderDiffExpected(ops) {
        var html = ''
        for (var i = 0; i < ops.length; i++) {
            var op = ops[i]
            var escaped = escapeHtml(op.text)
            if (op.type === 'equal') {
                html += '<span class="diff-good">' + escaped + '</span>'
            } else if (op.type === 'delete') {
                html += '<span class="diff-missing">' + escaped + '</span>'
            }
            // 'insert' ops are not part of expected
        }
        return html
    }

    /**
     * Render the "Got" row of the diff.
     * Equal parts in green, inserted (wrong/extra) parts in red strikethrough.
     */
    function renderDiffGot(ops) {
        var html = ''
        for (var i = 0; i < ops.length; i++) {
            var op = ops[i]
            var escaped = escapeHtml(op.text)
            if (op.type === 'equal') {
                html += '<span class="diff-good">' + escaped + '</span>'
            } else if (op.type === 'insert') {
                html += '<span class="diff-bad">' + escaped + '</span>'
            }
            // 'delete' ops are not part of typed
        }
        return html
    }

    function escapeHtml(text) {
        var div = document.createElement('div')
        div.appendChild(document.createTextNode(text))
        return div.innerHTML
    }

    enhancedClozesMain()
</script>
```

- [ ] **Step 2: Commit**

```bash
git add anki-addons/enhanced-cloze-type-in/note_type/Enhanced_Cloze_TypeIn_Front_Side.html
git commit -m "feat: add front-side template with type-in inputs and character-level diff"
```

---

### Task 5: Create symlink and manual testing

Create a symlink from the Anki addons directory to the repo, then manually verify the addon loads and the type-in behavior works.

**Files:**
- No new files — this is a verification step

- [ ] **Step 1: Create symlink**

```bash
ln -s /home/cmf/Dropbox/Apps/brain-training/anki-addons/enhanced-cloze-type-in \
      /home/cmf/.local/share/Anki2/addons21/enhanced_cloze_type_in
```

- [ ] **Step 2: Manual test checklist**

Open Anki and verify:

1. The "Enhanced Cloze Type-In 1.0" note type appears in Tools > Manage Note Types
2. Create a test note with the new note type:
   - Content: `The capital of France is {{c1::Paris}} and Germany's is {{c1::Berlin}}`
3. Review the card:
   - Two input fields appear where the clozes are
   - Hint text shows as placeholder if a hint was provided
   - Pressing Enter in a field shows diff feedback
   - Typing the correct answer shows green text
   - Typing a wrong answer shows Expected/Got diff
   - Tab moves to the next input
   - Pseudo-clozes (if testing with c1/c2 mix) show as blue clickable spans
4. Back side shows all answers revealed
5. Tools > Enhanced Cloze Type-In menu appears

- [ ] **Step 3: Commit any fixes from testing**

```bash
git add -u anki-addons/enhanced-cloze-type-in/
git commit -m "fix: adjustments from manual testing"
```

---

### Task 6: Final cleanup and documentation

- [ ] **Step 1: Add a brief README for the addon directory**

Create `anki-addons/enhanced-cloze-type-in/README.md`:

```markdown
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
```

- [ ] **Step 2: Commit**

```bash
git add anki-addons/enhanced-cloze-type-in/README.md
git commit -m "docs: add README for Enhanced Cloze Type-In addon"
```
