# Build Anki Deck from Source Material

Build an Anki .apkg deck from source material (textbook chapter, article, PDF, notes) using genanki. Two note types: Enhanced Cloze (interactive reveal) and Basic (Q&A).

## Inputs

The user provides:
- Source material (file path, pasted text, or URL)
- Deck name (Anki `::` hierarchy, e.g., `CFA::Reading 1`)
- Optionally: existing notes/summaries to start from

## Phase 1: Extract and Classify

Read the source material thoroughly. Identify card-worthy knowledge — facts, formulas, definitions, reasoning, distinctions. Classify each piece:

**Enhanced Cloze** — when testing recall of components within a structure:
- Formulas and equations
- Decompositions (X = A + B + C)
- Enumerations and lists
- Definitions with key terms to blank

**Basic Q&A** — when the knowledge is a reasoning link:
- "Why X?" / "When to use Y?" / "What distinguishes A from B?"
- Conceptual explanations where the question framing matters
- Comparisons and trade-offs

**Heuristic:** nouns/components → cloze, verbs/reasoning → Q&A.

Present the full card set to the user organized by section, with cloze content showing `{{c1::...}}` markers and Q&A showing Q/A pairs. Get approval before building.

## Phase 2: Card Content Rules

### Enhanced Cloze constraints
- **All clozes use `{{c1::}}`** — not c1/c2/c3. Enhanced Cloze handles multiple c1 blanks per card, revealing them one at a time interactively.
- **LaTeX/MathJax constraint:** Each `{{c1::...}}` that contains LaTeX MUST hold a complete `\(...\)` expression. You CANNOT put cloze deletions inside a LaTeX formula — the addon replaces clozes with HTML elements which breaks MathJax parsing.
  - WRONG: `\(R = \frac{ {{c1::P_1}} - {{c1::P_0}} }{ {{c1::P_0}} }\)`
  - RIGHT: `Holding period return: {{c1::\(R = \frac{P_1 - P_0 + I_1}{P_0}\)}}`
  - RIGHT: `\(r =\) {{c1::real risk-free rate}} + {{c1::inflation premium}}` (LaTeX is a complete standalone expression outside clozes)
- When a formula has multiple terms worth testing individually, but they can't be separated without breaking LaTeX, wrap the whole formula as a single cloze. Add a text label prefix (e.g., "Holding period return:") so the card has visible context when the formula is hidden.

### LaTeX formatting
- Use `\(...\)` delimiters (MathJax inline math)
- **Never use `\text{...}` inside a cloze** — the closing `}` collides with the cloze `}}`, breaking Anki's parser. Use escaped spaces instead: `inflation\ premium` not `\text{inflation premium}`.
- `\text{...}` is fine in LaTeX that is NOT inside a cloze deletion.
- Anki renders via MathJax — standard LaTeX math commands work

### Compression principles
- Every word costs time across hundreds of reps — be telegraphic
- Merge redundant bullets from the source
- Kill vague "choice depends on..." bullets — make them concrete Q&A cards instead
- Add text labels to formula clozes for context

## Phase 3: Build Export Script

Create a standalone script at `scripts/<deck_name>/export_apkg.py` following the established pattern.

### Critical: Model IDs must match installed Anki note types

The genanki model IDs MUST match the IDs Anki assigned to the installed note types. Using arbitrary IDs creates duplicate note types (e.g., "Enhanced Cloze 2.1 v2+") and cards won't render correctly.

To find the real IDs, read from the Anki collection database (Anki must be closed):

```python
import sqlite3
db = sqlite3.connect(Path.home() / ".local/share/Anki2/User 1/collection.anki2")
rows = db.execute("SELECT id, name FROM notetypes").fetchall()
for r in rows:
    print(f"ID: {r[0]}, Name: {r[1]}")
```

Current known IDs (verify these still match before using):
- Enhanced Cloze 2.1 v2: `1775602039195`
- Basic: `1691317181386`

### Enhanced Cloze templates must come from the addon

The export script must read the actual front/back/CSS templates from the installed Enhanced Cloze addon directory. Placeholder templates will override the addon's rich HTML/CSS/JS on import, breaking interactive cloze behavior.

```python
ADDON_NOTE_TYPE_DIR = Path.home() / ".local/share/Anki2/addons21/1990296174/note_type"

def _read_addon_templates():
    front = (ADDON_NOTE_TYPE_DIR / "Enhanced_Cloze_Front_Side.html").read_text()
    back = (ADDON_NOTE_TYPE_DIR / "Enhanced_Cloze_Back_Side.html").read_text()
    css = (ADDON_NOTE_TYPE_DIR / "Enhanced_Cloze_CSS.css").read_text()
    return front, back, css
```

### Script structure

```python
# Models
cloze_model = genanki.Model(
    CLOZE_MODEL_ID,                    # from Anki DB
    "Enhanced Cloze 2.1 v2",           # must match installed name
    fields=[Content, Note, Mnemonics, Extra, Cloze99],
    templates=[{"name": "Enhanced Cloze", "qfmt": front_html, "afmt": back_html}],
    css=css,
    model_type=genanki.Model.CLOZE,
)

basic_model = genanki.Model(
    BASIC_MODEL_ID,                    # from Anki DB
    "Basic",                           # must match installed name
    fields=[Front, Back],
    templates=[{"name": "Card 1", "qfmt": "{{Front}}", "afmt": "{{FrontSide}}<hr id=answer>{{Back}}"}],
)

# Card data — hardcoded tuples
CLOZE_CARDS = [("card_id", "content with {{c1::...}}", ["tag"]), ...]
QA_CARDS = [("card_id", "front", "back", ["tag"]), ...]

# Stable GUIDs via SHA-256 for safe re-import
def stable_guid(card_id): return hashlib.sha256(card_id.encode()).hexdigest()[:10]
```

### Tags
Use hierarchical tags: `DeckPrefix::ReadingOrChapter::Section` (e.g., `CFA::R1::1.2`).

### Output
- Script: `scripts/<name>/export_apkg.py`
- Output: `scripts/<name>/<name>.apkg` (gitignored)
- Run: `uv run python scripts/<name>/export_apkg.py`

## Phase 4: Verify

After generating the .apkg, ask the user to:
1. Close Anki (if model IDs need checking)
2. Import the .apkg
3. Spot-check: Enhanced Cloze styling (colored brackets, interactive reveal), MathJax rendering, Q&A front/back, tags

If cards don't render correctly, the most common issues are:
- Wrong model ID → duplicate note types created
- Placeholder templates → no Enhanced Cloze styling
- Cloze inside LaTeX → MathJax broken

## Reference: Existing export scripts

Pattern examples in this repo:
- `scripts/cfa_reading1/export_apkg.py` — Enhanced Cloze + Basic, LaTeX
- `scripts/govt_spending/export_apkg.py` — Enhanced Cloze Type-In, SVG charts
- `scripts/german_vocab/export_apkg.py` — custom bidirectional model
