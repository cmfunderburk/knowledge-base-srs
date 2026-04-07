# CFA Reading 1 Anki Deck Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate a `CFA::Reading 1` Anki deck (.apkg) with 40 notes (16 Enhanced Cloze + 24 Basic Q&A) covering Learning Module 1 "Rates and Returns."

**Architecture:** Single standalone export script following the `scripts/govt_spending/export_apkg.py` pattern. Two genanki models (Enhanced Cloze 2.1 v2 and Basic), hardcoded card data, stable GUIDs for safe re-import. No tests — matches existing export script pattern; verification is manual Anki import.

**Tech Stack:** Python 3.12+, genanki

**Spec:** `docs/superpowers/specs/2026-04-07-cfa-reading1-anki-deck-design.md`

---

### File Map

- **Create:** `scripts/cfa_reading1/export_apkg.py` — models, card data, export function

**Existing model IDs to avoid collisions with:**
- `2026040481` (german_vocab model)
- `2026040482` (german_vocab deck)
- `1775162181082` (govt_spending model)
- `2010040401` (govt_spending deck by nation)
- `2010040402` (govt_spending deck by category)

---

### Task 1: Create export script with models and helpers

**Files:**
- Create: `scripts/cfa_reading1/export_apkg.py`

- [ ] **Step 1: Create directory**

```bash
mkdir -p scripts/cfa_reading1
```

- [ ] **Step 2: Write the script skeleton with models and helper**

Create `scripts/cfa_reading1/export_apkg.py`:

```python
"""Export CFA Reading 1 flashcards to an Anki .apkg package.

Writes: scripts/cfa_reading1/cfa_reading1.apkg

Two note types:
- Enhanced Cloze 2.1 v2 (cloze deletion, matches installed addon)
- Basic (standard Q&A)
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import genanki

# --- Stable IDs (must not collide with other export scripts) -----------

CLOZE_MODEL_ID = 2026040701
BASIC_MODEL_ID = 2026040702
DECK_ID = 2026040703

OUT_DIR = Path(__file__).parent

# --- Models ------------------------------------------------------------

cloze_model = genanki.Model(
    CLOZE_MODEL_ID,
    "Enhanced Cloze 2.1 v2",
    fields=[
        {"name": "Content"},
        {"name": "Note"},
        {"name": "Mnemonics"},
        {"name": "Extra"},
        {"name": "Cloze99"},
    ],
    templates=[
        {
            "name": "Enhanced Cloze",
            "qfmt": "{{cloze:Content}}",
            "afmt": "{{cloze:Content}}<br>{{Note}}",
        },
    ],
    model_type=genanki.Model.CLOZE,
)

basic_model = genanki.Model(
    BASIC_MODEL_ID,
    "Basic",
    fields=[
        {"name": "Front"},
        {"name": "Back"},
    ],
    templates=[
        {
            "name": "Card 1",
            "qfmt": "{{Front}}",
            "afmt": "{{FrontSide}}<hr id=answer>{{Back}}",
        },
    ],
)


def stable_guid(card_id: str) -> str:
    """Generate a stable GUID from card_id for safe re-import."""
    h = hashlib.sha256(card_id.encode()).hexdigest()
    return h[:10]
```

- [ ] **Step 3: Verify the skeleton imports cleanly**

```bash
cd /home/cmf/Dropbox/Apps/knowledge-base && python -c "import scripts.cfa_reading1.export_apkg" 2>&1 || python scripts/cfa_reading1/export_apkg.py
```

Expected: no output, no errors (no `__main__` block yet).

- [ ] **Step 4: Commit skeleton**

```bash
git add scripts/cfa_reading1/export_apkg.py
git commit -m "feat(cfa): add export script skeleton with models and GUID helper"
```

---

### Task 2: Add all card data

**Files:**
- Modify: `scripts/cfa_reading1/export_apkg.py`

- [ ] **Step 1: Add cloze card data**

Append after the `stable_guid` function:

```python
# --- Card Data ---------------------------------------------------------
# Each cloze: (card_id, content, tags)
# Each QA:    (card_id, front, back, tags)

CLOZE_CARDS: list[tuple[str, str, list[str]]] = [
    # Section 1.2 — Interest Rates
    (
        "cfa_r1_cloze_01",
        r"Interest rate \(r\): {{c1::required rate of return}}, {{c2::discount rate}}, or {{c3::opportunity cost}}.",
        ["CFA::R1::1.2"],
    ),
    (
        "cfa_r1_cloze_02",
        r"\(r =\) {{c1::real risk-free rate}} + {{c2::inflation premium}} + {{c3::default risk premium}} + {{c4::liquidity premium}} + {{c5::maturity premium}}",
        ["CFA::R1::1.2"],
    ),
    (
        "cfa_r1_cloze_03",
        r"Nominal risk-free rate \(\approx\) {{c1::real risk-free rate}} + {{c2::inflation premium}}",
        ["CFA::R1::1.2"],
    ),
    (
        "cfa_r1_cloze_04",
        r"Exact: \((1 + r_{nominal\ RF}) = (1 +\) {{c1::\(r_{real\ RF}\)}})\((1 +\) {{c2::inflation premium}}\()\)",
        ["CFA::R1::1.2"],
    ),
    # Section 1.3 — Rates of Return
    (
        "cfa_r1_cloze_10",
        "Total return = {{c1::income yield}} + {{c2::capital gain/loss}}",
        ["CFA::R1::1.3"],
    ),
    (
        "cfa_r1_cloze_11",
        r"\(R = \frac{ {{c1::P_1}} - {{c2::P_0}} + {{c3::I_1}} }{ {{c4::P_0}} }\)",
        ["CFA::R1::1.3"],
    ),
    (
        "cfa_r1_cloze_12",
        r"Multi-period HPR: \(R = \prod_{t=1}^{T}(1 + R_t) -\) {{c1::\(1\)}}",
        ["CFA::R1::1.3"],
    ),
    (
        "cfa_r1_cloze_13",
        r"Harmonic mean: \(\bar{X}_H = \frac{ {{c1::n}} }{ {{c2::\sum_{i=1}^{n}(1/X_i)}} }\)",
        ["CFA::R1::1.3"],
    ),
    (
        "cfa_r1_cloze_14",
        r"Ordering: {{c1::\(\bar{X}_H\)}} \(\leq\) {{c2::\(\bar{X}_G\)}} \(\leq\) {{c3::\(\bar{X}_A\)}}. Equal only when {{c4::all observations are the same}}.",
        ["CFA::R1::1.3"],
    ),
    (
        "cfa_r1_cloze_15",
        r"\(\bar{X}_A \times \bar{X}_H =\) {{c1::\((\bar{X}_G)^2\)}}",
        ["CFA::R1::1.3"],
    ),
    # Section 1.4 — Money-Weighted and Time-Weighted Return
    (
        "cfa_r1_cloze_21",
        r"Money-weighted return = {{c1::IRR}}: \(\displaystyle\sum_{t=0}^{T} \frac{CF_t}{(1 + IRR)^t} =\) {{c2::\(0\)}}",
        ["CFA::R1::1.4"],
    ),
    (
        "cfa_r1_cloze_22",
        "Three steps for time-weighted return: (1) {{c1::price portfolio before each cash flow}}, (2) {{c2::calculate HPR for each subperiod}}, (3) {{c3::link (compound) subperiod returns}}",
        ["CFA::R1::1.4"],
    ),
    # Section 1.5 — Annualized Return
    (
        "cfa_r1_cloze_26",
        r"\(R_{annual} = (1 +\) {{c1::\(R_{period}\)}}\()^{c} -\) {{c2::\(1\)}}, where \(c =\) {{c3::number of periods in a year}}",
        ["CFA::R1::1.5"],
    ),
    (
        "cfa_r1_cloze_27",
        r"For holding periods longer than one year, \(c\) is a {{c1::fraction}} (e.g., 18 months \(\rightarrow c =\) {{c2::\(2/3\)}})",
        ["CFA::R1::1.5"],
    ),
    (
        "cfa_r1_cloze_28",
        r"\(r_{cc} =\) {{c1::\(\ln(1 + R)\)}} \(=\) {{c2::\(\ln(P_T / P_0)\)}}",
        ["CFA::R1::1.5"],
    ),
    (
        "cfa_r1_cloze_29",
        r"CC returns are {{c1::additive}}: \(r_{0,T} = r_{0,1} + r_{1,2} + \cdots + r_{T-1,T}\)",
        ["CFA::R1::1.5"],
    ),
]
```

- [ ] **Step 2: Add Q&A card data and remaining cloze cards for section 1.6**

Continue appending:

```python
# Section 1.6 cloze cards (added separately since they follow the QA-heavy section)
CLOZE_CARDS.extend([
    (
        "cfa_r1_cloze_33",
        r"After-tax nominal return = total return \(-\) taxes on {{c1::dividends}}, {{c2::interest}}, and {{c3::realized gains}}",
        ["CFA::R1::1.6"],
    ),
    (
        "cfa_r1_cloze_34",
        r"\((1 + r_{real}) = \frac{(1 +\) {{c1::\(r_{real\ RF}\)}})\((1 +\) {{c2::risk premium}}\()}{1 +\) {{c3::inflation premium}}\(}\)",
        ["CFA::R1::1.6"],
    ),
    (
        "cfa_r1_cloze_35",
        r"\(R_L = R_P + \frac{ {{c1::V_B}} }{ {{c2::V_E}} }(\) {{c3::\(R_P - r_D\)}} \()\)",
        ["CFA::R1::1.6"],
    ),
])

QA_CARDS: list[tuple[str, str, str, list[str]]] = [
    # Section 1.2 — Interest Rates
    (
        "cfa_r1_qa_05",
        "What does the real risk-free rate reflect in economic theory?",
        "The time preference of individuals for current versus future real consumption. It is the single-period rate for a completely risk-free security if no inflation were expected.",
        ["CFA::R1::1.2"],
    ),
    (
        "cfa_r1_qa_06",
        "What does the inflation premium compensate for?",
        "Expected inflation over the maturity of the debt — the expected loss of purchasing power.",
        ["CFA::R1::1.2"],
    ),
    (
        "cfa_r1_qa_07",
        "What does the default risk premium compensate for?",
        "The possibility that the borrower will fail to make a promised payment at the contracted time and in the contracted amount.",
        ["CFA::R1::1.2"],
    ),
    (
        "cfa_r1_qa_08",
        "What does the liquidity premium compensate for?",
        "The risk of loss relative to an investment's fair value if it needs to be converted to cash quickly. T-bills bear no liquidity premium; bonds from small, infrequently traded issuers do.",
        ["CFA::R1::1.2"],
    ),
    (
        "cfa_r1_qa_09",
        "What does the maturity premium compensate for?",
        "The increased sensitivity of market value to changes in interest rates as maturity extends.",
        ["CFA::R1::1.2"],
    ),
    # Section 1.3 — Rates of Return
    (
        "cfa_r1_qa_16",
        "When should you use the arithmetic mean for return measurement?",
        "When estimating the average return over a single period — it is the simple average of one-period returns and has known statistical properties.",
        ["CFA::R1::1.3"],
    ),
    (
        "cfa_r1_qa_17",
        "When should you use the geometric mean for return measurement?",
        "When estimating compound growth over multiple periods. It captures how total returns are linked over time and gives the rate you would have to earn each period to match actual cumulative performance.",
        ["CFA::R1::1.3"],
    ),
    (
        "cfa_r1_qa_18",
        "Why is the arithmetic mean biased upward for multi-period returns?",
        "It assumes the amount invested at the beginning of each period is the same, ignoring compounding. The bias is particularly severe when returns mix positive and negative values.",
        ["CFA::R1::1.3"],
    ),
    (
        "cfa_r1_qa_19",
        "When is the harmonic mean the appropriate measure, and what is a common finance application?",
        "When averaging rates or ratios (amount per unit) applied repeatedly to a fixed quantity yielding a variable number of units. Key application: cost averaging — periodic investment of a fixed dollar amount; the average cost per share equals the harmonic mean of purchase prices.",
        ["CFA::R1::1.3"],
    ),
    (
        "cfa_r1_qa_20",
        "What is the difference between a trimmed mean and a winsorized mean?",
        "Trimmed: removes a defined percentage of the largest and smallest values, then averages the rest. Winsorized: replaces extreme values at both ends with the nearest non-extreme observations, then averages. Both reduce the impact of outliers.",
        ["CFA::R1::1.3"],
    ),
    # Section 1.4 — Money-Weighted and Time-Weighted Return
    (
        "cfa_r1_qa_23",
        "What does money-weighted return account for?",
        "The timing and size of actual cash flows. It reflects the actual return earned on the money invested and is calculated as the IRR of all cash inflows and outflows.",
        ["CFA::R1::1.4"],
    ),
    (
        "cfa_r1_qa_24",
        "Why is time-weighted return preferred for evaluating portfolio managers?",
        "It measures compound growth of one unit of currency, insensitive to cash flow timing. Cash additions/withdrawals are outside the manager's control — if a client adds funds at a bad time, MWR is depressed; TWR removes this effect.",
        ["CFA::R1::1.4"],
    ),
    (
        "cfa_r1_qa_25",
        "What is the key limitation of money-weighted return for comparison purposes?",
        "Two investors in the same fund with the same portfolio can have different money-weighted returns because they invested different amounts at different times. It does not allow return comparison across individuals or investment opportunities.",
        ["CFA::R1::1.4"],
    ),
    # Section 1.5 — Annualized Return
    (
        "cfa_r1_qa_30",
        "Why annualize returns?",
        "To enable comparison across investments held for different time periods. All returns are put on a common annual scale.",
        ["CFA::R1::1.5"],
    ),
    (
        "cfa_r1_qa_31",
        "What is the key limitation of annualizing short-term returns?",
        "It implicitly assumes returns can be repeated — that the periodic return can be earned every period for a full year. A 5% weekly return annualized to 1,164% is unrealistic.",
        ["CFA::R1::1.5"],
    ),
    (
        "cfa_r1_qa_32",
        r"Why are continuously compounded returns used throughout quantitative finance?",
        r"Because they are additive across time (just sum sub-period CC returns), while holding period returns require multiplying \((1+R)\) terms. This simplifies multi-period calculations.",
        ["CFA::R1::1.5"],
    ),
    # Section 1.6 — Other Major Return Measures
    (
        "cfa_r1_qa_36",
        "What is gross return and how does it treat trading expenses?",
        "Return before deduction of management/admin expenses. Trading expenses (commissions) ARE deducted because they are directly related to return generation. Used to compare asset managers' skill.",
        ["CFA::R1::1.6"],
    ),
    (
        "cfa_r1_qa_37",
        "What is net return?",
        "Gross return less managerial and administrative expenses. Measures what the investor actually earned.",
        ["CFA::R1::1.6"],
    ),
    (
        "cfa_r1_qa_38",
        "Why are real returns useful for cross-period comparison?",
        "Because inflation rates vary over time. Also useful for cross-country comparison when returns are in local currencies with different inflation rates.",
        ["CFA::R1::1.6"],
    ),
    (
        "cfa_r1_qa_39",
        r"When does leverage increase vs decrease portfolio returns?",
        r"Leverage increases returns when \(R_P > r_D\) (portfolio return exceeds borrowing cost). When \(R_P < r_D\), leverage decreases returns. It amplifies both gains and losses.",
        ["CFA::R1::1.6"],
    ),
    (
        "cfa_r1_qa_40",
        "Why is after-tax real return considered the investor's true benchmark, yet rarely calculated by asset managers?",
        "It represents the actual compensation for postponing consumption and bearing risk, after all deductions. But managers can't calculate a universal value because the tax component depends on each investor's marginal rate, holding period, and account type.",
        ["CFA::R1::1.6"],
    ),
]
```

- [ ] **Step 3: Verify data counts**

```bash
cd /home/cmf/Dropbox/Apps/knowledge-base && python -c "
from scripts.cfa_reading1.export_apkg import CLOZE_CARDS, QA_CARDS
print(f'Cloze: {len(CLOZE_CARDS)}, QA: {len(QA_CARDS)}, Total: {len(CLOZE_CARDS) + len(QA_CARDS)}')
assert len(CLOZE_CARDS) == 16, f'Expected 16 cloze, got {len(CLOZE_CARDS)}'
# 1.6 cloze cards are added via .extend()
assert len(QA_CARDS) == 24, f'Expected 24 QA, got {len(QA_CARDS)}'
print('Counts OK')
"
```

Expected: `Cloze: 16, QA: 24, Total: 40` then `Counts OK`.

Note: if the script can't be imported as a module due to the `scripts` directory lacking `__init__.py`, run it differently:

```bash
cd /home/cmf/Dropbox/Apps/knowledge-base && python -c "
import importlib.util, sys
spec = importlib.util.spec_from_file_location('export', 'scripts/cfa_reading1/export_apkg.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
print(f'Cloze: {len(mod.CLOZE_CARDS)}, QA: {len(mod.QA_CARDS)}, Total: {len(mod.CLOZE_CARDS) + len(mod.QA_CARDS)}')
assert len(mod.CLOZE_CARDS) == 16
assert len(mod.QA_CARDS) == 24
print('Counts OK')
"
```

- [ ] **Step 4: Commit card data**

```bash
git add scripts/cfa_reading1/export_apkg.py
git commit -m "feat(cfa): add all 40 card definitions for Reading 1"
```

---

### Task 3: Add export function and generate .apkg

**Files:**
- Modify: `scripts/cfa_reading1/export_apkg.py`

- [ ] **Step 1: Add the export function and main block**

Append to end of file:

```python
# --- Export -------------------------------------------------------------


def export_apkg() -> Path:
    """Build deck and write .apkg."""
    deck = genanki.Deck(DECK_ID, "CFA::Reading 1")

    for card_id, content, tags in CLOZE_CARDS:
        note = genanki.Note(
            model=cloze_model,
            fields=[content, "", "", "", ""],
            tags=tags,
            guid=stable_guid(card_id),
        )
        deck.add_note(note)

    for card_id, front, back, tags in QA_CARDS:
        note = genanki.Note(
            model=basic_model,
            fields=[front, back],
            tags=tags,
            guid=stable_guid(card_id),
        )
        deck.add_note(note)

    out_path = OUT_DIR / "cfa_reading1.apkg"
    genanki.Package([deck]).write_to_file(str(out_path))
    print(f"Wrote {out_path}: {len(CLOZE_CARDS)} cloze + {len(QA_CARDS)} QA = {len(CLOZE_CARDS) + len(QA_CARDS)} notes")
    return out_path


if __name__ == "__main__":
    export_apkg()
```

- [ ] **Step 2: Run the export**

```bash
cd /home/cmf/Dropbox/Apps/knowledge-base && python scripts/cfa_reading1/export_apkg.py
```

Expected output: `Wrote scripts/cfa_reading1/cfa_reading1.apkg: 16 cloze + 24 QA = 40 notes`

- [ ] **Step 3: Verify the .apkg file exists and has reasonable size**

```bash
ls -lh scripts/cfa_reading1/cfa_reading1.apkg
```

Expected: file exists, roughly 5–20 KB.

- [ ] **Step 4: Commit**

```bash
git add scripts/cfa_reading1/export_apkg.py
git commit -m "feat(cfa): add export function, generate Reading 1 .apkg

16 Enhanced Cloze notes + 24 Basic Q&A notes = 40 notes total.
Covers LM1 Rates and Returns from 2025 CFA L1 Quantitative Methods."
```

- [ ] **Step 5: Gitignore the .apkg output**

The .apkg is a generated artifact. Add to `.gitignore`:

```
scripts/cfa_reading1/*.apkg
```

```bash
git add .gitignore
git commit -m "chore: gitignore generated .apkg for CFA Reading 1"
```

---

### Task 4: Manual verification in Anki

This is not a code task — it's a manual QA step for the user.

- [ ] **Step 1: Import into Anki**

Open Anki → File → Import → select `scripts/cfa_reading1/cfa_reading1.apkg`.

- [ ] **Step 2: Verify deck structure**

Check that `CFA::Reading 1` appears as a subdeck under `CFA`.

- [ ] **Step 3: Spot-check cards**

Browse the deck. Verify:
- Cloze cards render with MathJax (LaTeX formulas display correctly)
- Cloze deletions work (blanks appear, reveal on click)
- Q&A cards show question on front, answer on back
- Tags are present (`CFA::R1::1.2` through `CFA::R1::1.6`)

- [ ] **Step 4: If LaTeX/cloze interaction issues found**

Some cards mix `{{c1::...}}` with `\(...\)` delimiters. If MathJax doesn't render inside cloze deletions, the fix is to ensure the LaTeX delimiters are inside the cloze brackets, not wrapping them. Adjust the card content in the script and re-export.
