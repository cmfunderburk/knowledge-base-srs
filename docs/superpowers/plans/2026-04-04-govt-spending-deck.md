# G7 Government Spending Anki Deck Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a direct-to-Anki deck of 72 cards drilling G7 government spending composition (by nation and by COFOG category) with SVG visualizations.

**Architecture:** Two-stage pipeline — Stage 1 fetches OECD COFOG API data and OMB Excel data, parses into curated CSVs. Stage 2 reads CSVs, generates cloze text + SVG charts, and exports `.apkg` via genanki. CSV intermediary provides an edit seam between stages.

**Tech Stack:** Python 3.12+, requests (OECD API), openpyxl (OMB Excel), matplotlib (SVG charts), genanki (Anki export)

---

## Data Source Details

### OECD COFOG API

- **Dataflow**: `OECD.SDD.NAD,DSD_NAAG_VI@DF_NAAG_OTEF`
- **Base URL**: `https://sdmx.oecd.org/public/rest/data/OECD.SDD.NAD,DSD_NAAG_VI@DF_NAAG_OTEF,/{key}?startPeriod={start}&endPeriod={end}&dimensionAtObservation=AllDimensions`
- **Key format**: `{FREQ}.{REF_AREA}.{MEASURE}.{EXPENDITURE}.{UNIT_MEASURE}.{CHAPTER}` (6 dimensions)
- **Request header**: `Accept: text/csv`
- **No auth required**

Key dimension values:
- `FREQ=A` (annual)
- `REF_AREA`: `USA`, `GBR`, `FRA`, `DEU`, `ITA`, `JPN` (Canada NOT available in this dataset)
- `EXPENDITURE`: `GF01`–`GF10` (COFOG L1 divisions), `_T` (total)
- `UNIT_MEASURE=PT_B1GQ` (% of GDP, pre-computed)
- % of total spending: computed as `division_value / total_value * 100`

COFOG division codes:
| Code | Name |
|------|------|
| GF01 | General Public Services |
| GF02 | Defence |
| GF03 | Public Order & Safety |
| GF04 | Economic Affairs |
| GF05 | Environmental Protection |
| GF06 | Housing & Community Amenities |
| GF07 | Health |
| GF08 | Recreation, Culture & Religion |
| GF09 | Education |
| GF10 | Social Protection |

**Data availability**: 2015–2023 as of April 2026. No 2024/2025 data yet. Canada is absent from this dataset entirely.

### OMB Table 4.1

- **URL**: `https://www.whitehouse.gov/wp-content/uploads/2026/04/hist04z1_fy2027.xlsx`
- **Format**: Excel, agencies as rows, fiscal years as columns, values in millions USD
- **Contains**: All fiscal years in a single file (actuals + estimates)

### Anki Model

- **Note type**: Enhanced Cloze Type-In 1.0
- **Model ID**: `1775162181082`
- **Fields** (in order): Content, Note, Mnemonics, Extra, Cloze99

---

## Adjusted Card Counts

Since OECD COFOG data goes through 2023 (not 2025), and Canada is missing:

**By Nation (COFOG)**: 6 countries × 4 years (2015, 2020, 2023, and nearest available to 2025) = 24 cards (not 28)
**By Nation (US Agency)**: 4 years (2015, 2020, 2023, 2025) = 4 cards
**By Category**: 10 divisions × 4 years = 40 cards (with 6 countries per card instead of 7)

**Total: ~68 cards** (exact count depends on data availability for the 4th year snapshot)

If 2024 COFOG data becomes available during implementation, use it as the 4th snapshot. Otherwise use 2022 to have 4 distinct snapshots.

---

### Task 1: Add dependencies to pyproject.toml

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add requests, openpyxl, matplotlib as project dependencies**

```toml
dependencies = [
    "genanki>=0.13",
    "textual>=3.0",
    "requests>=2.31",
    "openpyxl>=3.1",
    "matplotlib>=3.8",
]
```

Edit `pyproject.toml` to add `requests`, `openpyxl`, and `matplotlib` to the `dependencies` list. `genanki` is already present.

- [ ] **Step 2: Run uv sync**

Run: `uv sync`
Expected: All dependencies installed successfully

- [ ] **Step 3: Add data/govt_spending/ to .gitignore**

Append to `.gitignore`:
```
data/govt_spending/
```

- [ ] **Step 4: Create the scripts directory**

Run: `mkdir -p scripts/govt_spending`

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml .gitignore
git commit -m "chore: add dependencies for govt spending deck pipeline"
```

---

### Task 2: Build OECD COFOG data fetcher

**Files:**
- Create: `scripts/govt_spending/fetch_cofog.py`
- Test: Run script and verify CSV output

- [ ] **Step 1: Write fetch_cofog.py**

```python
"""Fetch OECD COFOG government expenditure data for G7 nations.

Downloads annual COFOG Level 1 spending data (% of GDP) from the OECD
SDMX API for USA, GBR, FRA, DEU, ITA, JPN. Canada is not available
in this dataset.

Output: data/govt_spending/raw/cofog_raw.csv
"""

from __future__ import annotations

import csv
from pathlib import Path

import requests

BASE_URL = (
    "https://sdmx.oecd.org/public/rest/data/"
    "OECD.SDD.NAD,DSD_NAAG_VI@DF_NAAG_OTEF,"
)

# Canada (CAN) is absent from the OECD COFOG NAAG dataset
COUNTRIES = ["USA", "GBR", "FRA", "DEU", "ITA", "JPN"]

COFOG_CODES = {
    "GF01": "General Public Services",
    "GF02": "Defence",
    "GF03": "Public Order & Safety",
    "GF04": "Economic Affairs",
    "GF05": "Environmental Protection",
    "GF06": "Housing & Community Amenities",
    "GF07": "Health",
    "GF08": "Recreation, Culture & Religion",
    "GF09": "Education",
    "GF10": "Social Protection",
}

TARGET_YEARS = [2015, 2020, 2022, 2023]

OUTPUT_DIR = Path("data/govt_spending/raw")


def fetch_cofog() -> Path:
    """Fetch COFOG data from OECD API and write raw CSV."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    countries_str = "+".join(COUNTRIES)
    expenditures = "+".join(list(COFOG_CODES.keys()) + ["_T"])
    key = f"/A.{countries_str}..{expenditures}.PT_B1GQ."

    url = BASE_URL + key
    params = {
        "startPeriod": str(min(TARGET_YEARS)),
        "endPeriod": str(max(TARGET_YEARS)),
        "dimensionAtObservation": "AllDimensions",
    }

    print(f"Fetching COFOG data from OECD API...")
    resp = requests.get(url, params=params, headers={"Accept": "text/csv"})
    resp.raise_for_status()

    out_path = OUTPUT_DIR / "cofog_raw.csv"
    out_path.write_text(resp.text, encoding="utf-8")
    print(f"Wrote {out_path} ({len(resp.text)} bytes)")
    return out_path


if __name__ == "__main__":
    fetch_cofog()
```

- [ ] **Step 2: Run the fetcher**

Run: `cd /home/cmf/Dropbox/Apps/knowledge-base && uv run python scripts/govt_spending/fetch_cofog.py`
Expected: `data/govt_spending/raw/cofog_raw.csv` created with CSV data containing columns DATAFLOW, FREQ, REF_AREA, MEASURE, EXPENDITURE, UNIT_MEASURE, CHAPTER, TIME_PERIOD, OBS_VALUE

- [ ] **Step 3: Verify output**

Run: `head -5 data/govt_spending/raw/cofog_raw.csv && echo "---" && wc -l data/govt_spending/raw/cofog_raw.csv`
Expected: CSV with header row + data rows. Should have ~264 data rows (6 countries × 11 expenditure codes × 4 years).

- [ ] **Step 4: Commit**

```bash
git add scripts/govt_spending/fetch_cofog.py
git commit -m "feat: add OECD COFOG data fetcher for G7 spending"
```

---

### Task 3: Build COFOG parser

**Files:**
- Create: `scripts/govt_spending/parse_cofog.py`

- [ ] **Step 1: Write parse_cofog.py**

```python
"""Parse raw OECD COFOG CSV into curated per-view CSVs.

Reads: data/govt_spending/raw/cofog_raw.csv
Writes:
  - data/govt_spending/cofog_by_nation.csv  (% of total spending, per country)
  - data/govt_spending/cofog_by_category.csv (% of GDP, per division)
"""

from __future__ import annotations

import csv
from pathlib import Path

COFOG_NAMES = {
    "GF01": "General Public Services",
    "GF02": "Defence",
    "GF03": "Public Order & Safety",
    "GF04": "Economic Affairs",
    "GF05": "Environmental Protection",
    "GF06": "Housing & Community Amenities",
    "GF07": "Health",
    "GF08": "Recreation, Culture & Religion",
    "GF09": "Education",
    "GF10": "Social Protection",
}

COUNTRY_NAMES = {
    "USA": "USA",
    "GBR": "UK",
    "FRA": "France",
    "DEU": "Germany",
    "ITA": "Italy",
    "JPN": "Japan",
}

TARGET_YEARS = {"2015", "2020", "2022", "2023"}

RAW_PATH = Path("data/govt_spending/raw/cofog_raw.csv")
OUTPUT_DIR = Path("data/govt_spending")


def parse_cofog() -> tuple[Path, Path]:
    """Parse raw COFOG CSV into by-nation and by-category CSVs."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Read raw data into a dict keyed by (country, year, expenditure_code)
    data: dict[tuple[str, str, str], float] = {}
    with open(RAW_PATH, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            country = row["REF_AREA"]
            year = row["TIME_PERIOD"]
            code = row["EXPENDITURE"]
            value = float(row["OBS_VALUE"])
            if year in TARGET_YEARS and country in COUNTRY_NAMES:
                data[(country, year, code)] = value

    # --- By Nation CSV: % of total spending ---
    by_nation_path = OUTPUT_DIR / "cofog_by_nation.csv"
    with open(by_nation_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["year", "country", "country_name", "rank",
                         "cofog_code", "cofog_name", "pct_of_gdp", "pct_of_total"])

        for country in COUNTRY_NAMES:
            for year in sorted(TARGET_YEARS):
                total = data.get((country, year, "_T"), 0.0)
                if total == 0:
                    continue

                divisions = []
                for code in COFOG_NAMES:
                    val = data.get((country, year, code), 0.0)
                    pct_total = val / total * 100 if total else 0.0
                    divisions.append((code, val, pct_total))

                divisions.sort(key=lambda x: -x[2])

                for rank, (code, pct_gdp, pct_total) in enumerate(divisions, 1):
                    writer.writerow([
                        year, country, COUNTRY_NAMES[country], rank,
                        code, COFOG_NAMES[code],
                        round(pct_gdp, 2), round(pct_total, 1),
                    ])

    print(f"Wrote {by_nation_path}")

    # --- By Category CSV: % of GDP ---
    by_category_path = OUTPUT_DIR / "cofog_by_category.csv"
    with open(by_category_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["year", "cofog_code", "cofog_name", "rank",
                         "country", "country_name", "pct_of_gdp"])

        for code, name in COFOG_NAMES.items():
            for year in sorted(TARGET_YEARS):
                countries_data = []
                for country in COUNTRY_NAMES:
                    val = data.get((country, year, code), 0.0)
                    countries_data.append((country, val))

                countries_data.sort(key=lambda x: -x[1])

                for rank, (country, pct_gdp) in enumerate(countries_data, 1):
                    writer.writerow([
                        year, code, name, rank,
                        country, COUNTRY_NAMES[country],
                        round(pct_gdp, 1),
                    ])

    print(f"Wrote {by_category_path}")
    return by_nation_path, by_category_path


if __name__ == "__main__":
    parse_cofog()
```

- [ ] **Step 2: Run the parser**

Run: `cd /home/cmf/Dropbox/Apps/knowledge-base && uv run python scripts/govt_spending/parse_cofog.py`
Expected: Two files created:
- `data/govt_spending/cofog_by_nation.csv` — 240 rows (6 countries × 4 years × 10 divisions)
- `data/govt_spending/cofog_by_category.csv` — 240 rows (10 divisions × 4 years × 6 countries)

- [ ] **Step 3: Spot-check the output**

Run: `head -15 data/govt_spending/cofog_by_nation.csv && echo "---" && head -10 data/govt_spending/cofog_by_category.csv`
Expected: By-nation rows sorted by pct_of_total descending within each country/year. By-category rows sorted by pct_of_gdp descending within each division/year.

- [ ] **Step 4: Commit**

```bash
git add scripts/govt_spending/parse_cofog.py
git commit -m "feat: add COFOG parser producing by-nation and by-category CSVs"
```

---

### Task 4: Build OMB agency data fetcher and parser

**Files:**
- Create: `scripts/govt_spending/fetch_omb.py`
- Create: `scripts/govt_spending/parse_omb_agency.py`

- [ ] **Step 1: Write fetch_omb.py**

```python
"""Download OMB Historical Table 4.1 (Outlays by Agency).

Output: data/govt_spending/raw/hist04z1.xlsx
"""

from __future__ import annotations

from pathlib import Path

import requests

OMB_URL = "https://www.whitehouse.gov/wp-content/uploads/2026/04/hist04z1_fy2027.xlsx"

OUTPUT_DIR = Path("data/govt_spending/raw")


def fetch_omb() -> Path:
    """Download OMB Table 4.1 Excel file."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Downloading OMB Table 4.1...")
    resp = requests.get(OMB_URL)
    resp.raise_for_status()

    out_path = OUTPUT_DIR / "hist04z1.xlsx"
    out_path.write_bytes(resp.content)
    print(f"Wrote {out_path} ({len(resp.content)} bytes)")
    return out_path


if __name__ == "__main__":
    fetch_omb()
```

- [ ] **Step 2: Run the fetcher**

Run: `cd /home/cmf/Dropbox/Apps/knowledge-base && uv run python scripts/govt_spending/fetch_omb.py`
Expected: `data/govt_spending/raw/hist04z1.xlsx` created

- [ ] **Step 3: Explore the Excel structure**

Run the following to understand the OMB Excel layout before writing the parser:

```bash
cd /home/cmf/Dropbox/Apps/knowledge-base && uv run python -c "
from openpyxl import load_workbook
wb = load_workbook('data/govt_spending/raw/hist04z1.xlsx', data_only=True)
ws = wb.active
print(f'Sheet: {ws.title}, Rows: {ws.max_row}, Cols: {ws.max_column}')
print()
# Print first 10 rows to see header structure
for row in ws.iter_rows(min_row=1, max_row=10, values_only=False):
    vals = [(c.column, c.value) for c in row if c.value is not None]
    print(vals[:6])
print()
# Find column headers (fiscal years)
for row in ws.iter_rows(min_row=1, max_row=5, values_only=False):
    for c in row:
        if c.value and '2023' in str(c.value):
            print(f'Found 2023 at row={c.row}, col={c.column}')
            break
"
```

This will reveal the exact row/column layout. The parser in the next step will need to be adjusted based on this output. OMB Excel files typically have:
- A few header rows with table title and column labels
- Agency names in column A (or B)
- Fiscal year columns across the top
- Values in millions of dollars
- Subtotal/total rows interspersed

- [ ] **Step 4: Write parse_omb_agency.py**

```python
"""Parse OMB Table 4.1 into a curated agency spending CSV.

Reads: data/govt_spending/raw/hist04z1.xlsx
Writes: data/govt_spending/us_agency.csv

The parser must handle OMB's Excel layout:
- Header rows at top (skip until reaching fiscal year column headers)
- Agency names in the leftmost data column
- Fiscal years across columns, values in millions USD
- Skip subtotal rows (e.g., "Total", "Undistributed offsetting receipts")
- Extract top 10 agencies by dollar amount for each target year
"""

from __future__ import annotations

import csv
from pathlib import Path

from openpyxl import load_workbook

TARGET_YEARS = [2015, 2020, 2023, 2025]

RAW_PATH = Path("data/govt_spending/raw/hist04z1.xlsx")
OUTPUT_DIR = Path("data/govt_spending")

# Rows to skip (totals, subtotals, offsets) — identified by substring match
SKIP_PATTERNS = [
    "total",
    "undistributed",
    "on-budget",
    "off-budget",
]


def parse_omb_agency() -> Path:
    """Parse OMB Table 4.1 and write agency spending CSV."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    wb = load_workbook(RAW_PATH, data_only=True)
    ws = wb.active

    # --- Find the header row with fiscal year columns ---
    header_row = None
    year_cols: dict[int, int] = {}  # fiscal_year -> column index

    for row in ws.iter_rows(min_row=1, max_row=10):
        for cell in row:
            val = cell.value
            if val is None:
                continue
            # OMB uses various formats: "2023", "2023 estimate", just the year
            val_str = str(val).strip()
            for fy in TARGET_YEARS:
                if val_str == str(fy) or val_str.startswith(str(fy)):
                    year_cols[fy] = cell.column
                    header_row = cell.row

    if not year_cols:
        raise ValueError("Could not find fiscal year columns in OMB Excel file. "
                         "The file layout may have changed — inspect manually.")

    print(f"Found fiscal year columns: {year_cols} at header row {header_row}")

    # --- Find the agency name column (leftmost non-empty column in data rows) ---
    # Usually column 1 or 2
    name_col = 1
    for row in ws.iter_rows(min_row=header_row + 1, max_row=header_row + 3):
        for cell in row:
            if cell.value and isinstance(cell.value, str) and cell.value.strip():
                name_col = cell.column
                break
        break

    # --- Extract agency data ---
    agencies: dict[int, list[tuple[str, float]]] = {fy: [] for fy in TARGET_YEARS}

    for row in ws.iter_rows(min_row=header_row + 1):
        name_cell = row[name_col - 1]  # 0-indexed
        if not name_cell.value or not isinstance(name_cell.value, str):
            continue

        name = name_cell.value.strip()
        name_lower = name.lower()

        # Skip totals and subtotals
        if any(pat in name_lower for pat in SKIP_PATTERNS):
            continue

        # Skip indented sub-agencies (OMB indents with spaces)
        # Top-level agencies are not indented or have minimal indentation
        # This heuristic may need adjustment based on actual file structure
        if name_cell.alignment and name_cell.alignment.indent and name_cell.alignment.indent > 1:
            continue

        for fy, col in year_cols.items():
            val = row[col - 1].value  # 0-indexed
            if val is not None and isinstance(val, (int, float)):
                agencies[fy].append((name, float(val)))

    # --- Compute top 10 + percentages ---
    out_path = OUTPUT_DIR / "us_agency.csv"
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["fiscal_year", "rank", "agency", "amount_millions",
                         "amount_billions", "pct_of_total"])

        for fy in TARGET_YEARS:
            if not agencies[fy]:
                print(f"Warning: No data found for FY{fy}")
                continue

            # Sort by absolute value (some agencies have negative values for receipts)
            sorted_agencies = sorted(agencies[fy], key=lambda x: -abs(x[1]))
            total = sum(v for _, v in agencies[fy] if v > 0)

            for rank, (name, amount) in enumerate(sorted_agencies[:10], 1):
                writer.writerow([
                    fy, rank, name,
                    round(amount),
                    round(amount / 1000, 1),
                    round(amount / total * 100, 1) if total else 0,
                ])

    print(f"Wrote {out_path}")
    wb.close()
    return out_path


if __name__ == "__main__":
    parse_omb_agency()
```

- [ ] **Step 5: Run the parser**

Run: `cd /home/cmf/Dropbox/Apps/knowledge-base && uv run python scripts/govt_spending/parse_omb_agency.py`
Expected: `data/govt_spending/us_agency.csv` created with 40 rows (4 years × 10 agencies)

- [ ] **Step 6: Spot-check the output**

Run: `cat data/govt_spending/us_agency.csv`
Expected: Agencies ranked by amount, percentages summing to ~70-85% of total (top 10 agencies). Verify names look like real federal agencies (e.g., "Department of Defense", "Social Security Administration", "Department of Health and Human Services").

**Important**: The Excel layout heuristics (header row detection, sub-agency indentation, skip patterns) may need manual adjustment after inspecting Step 3's output. If the parser produces incorrect results, inspect the Excel file and fix the row/column indices.

- [ ] **Step 7: Commit**

```bash
git add scripts/govt_spending/fetch_omb.py scripts/govt_spending/parse_omb_agency.py
git commit -m "feat: add OMB Table 4.1 fetcher and agency parser"
```

---

### Task 5: Build card generator

**Files:**
- Create: `scripts/govt_spending/build_cards.py`

- [ ] **Step 1: Write build_cards.py**

```python
"""Generate Anki card CSV from parsed COFOG and OMB agency data.

Reads:
  - data/govt_spending/cofog_by_nation.csv
  - data/govt_spending/cofog_by_category.csv
  - data/govt_spending/us_agency.csv

Writes:
  - data/govt_spending/cards.csv

Each row in cards.csv is one Anki card with columns:
  card_id, deck, content (cloze text), note (SVG chart), tags
"""

from __future__ import annotations

import csv
import io
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

DATA_DIR = Path("data/govt_spending")

# Consistent color palette for COFOG divisions across all cards
COFOG_COLORS = {
    "General Public Services": "#1f77b4",
    "Defence": "#ff7f0e",
    "Public Order & Safety": "#2ca02c",
    "Economic Affairs": "#d62728",
    "Environmental Protection": "#9467bd",
    "Housing & Community Amenities": "#8c564b",
    "Health": "#e377c2",
    "Recreation, Culture & Religion": "#7f7f7f",
    "Education": "#bcbd22",
    "Social Protection": "#17becf",
}

OTHER_COLOR = "#cccccc"


def svg_from_fig(fig: plt.Figure) -> str:
    """Render a matplotlib figure to an SVG string."""
    buf = io.StringIO()
    fig.savefig(buf, format="svg", bbox_inches="tight")
    plt.close(fig)
    svg = buf.getvalue()
    # Strip XML declaration and DOCTYPE for embedding in HTML
    lines = svg.split("\n")
    svg_lines = [l for l in lines if not l.startswith("<?xml") and not l.startswith("<!DOCTYPE")]
    return "\n".join(svg_lines)


def make_pie_chart(labels: list[str], values: list[float],
                   colors: list[str]) -> str:
    """Generate an SVG pie chart."""
    fig, ax = plt.subplots(figsize=(5, 4))

    def label_func(pct: float) -> str:
        return f"{pct:.0f}%" if pct >= 2 else ""

    wedges, texts, autotexts = ax.pie(
        values, labels=None, autopct=label_func,
        colors=colors, startangle=90, counterclock=False,
        pctdistance=0.8, textprops={"fontsize": 8},
    )

    ax.legend(
        wedges, [f"{l} ({v:.0f}%)" for l, v in zip(labels, values)],
        loc="center left", bbox_to_anchor=(1, 0.5), fontsize=7,
        frameon=False,
    )

    return svg_from_fig(fig)


def make_bar_chart(labels: list[str], values: list[float],
                   color: str) -> str:
    """Generate an SVG horizontal bar chart."""
    fig, ax = plt.subplots(figsize=(5, 3))

    bars = ax.barh(range(len(labels)), values, color=color, height=0.6)
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=9)
    ax.invert_yaxis()
    ax.set_xlabel("% of GDP", fontsize=9)
    ax.tick_params(axis="x", labelsize=8)

    for bar, val in zip(bars, values):
        ax.text(bar.get_width() + 0.1, bar.get_y() + bar.get_height() / 2,
                f"{val:.1f}%", va="center", fontsize=8)

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    return svg_from_fig(fig)


def build_by_nation_cofog_cards(writer: csv.writer) -> int:
    """Build per-country COFOG breakdown cards."""
    path = DATA_DIR / "cofog_by_nation.csv"
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    # Group by (country, year)
    groups: dict[tuple[str, str], list[dict]] = {}
    for row in rows:
        key = (row["country"], row["year"])
        groups.setdefault(key, []).append(row)

    count = 0
    for (country, year), items in sorted(groups.items()):
        country_name = items[0]["country_name"]

        # Build cloze content
        lines = [f"{year} {country_name} Government Spending by Category (% of total):<br>"]
        for item in items:
            rank = item["rank"]
            name = item["cofog_name"]
            pct = round(float(item["pct_of_total"]))
            lines.append(f"{rank}. {{{{c1::{name} - {pct}%}}}}<br>")

        content = "\n".join(lines)

        # Build pie chart
        labels = [item["cofog_name"] for item in items]
        values = [float(item["pct_of_total"]) for item in items]
        colors = [COFOG_COLORS.get(name, OTHER_COLOR) for name in labels]
        svg = make_pie_chart(labels, values, colors)

        card_id = f"by_nation_{country.lower()}_{year}"
        tags = f"govt_spending by_nation {country.lower()} {year}"

        writer.writerow([card_id, "by_nation", content, svg, tags])
        count += 1

    return count


def build_us_agency_cards(writer: csv.writer) -> int:
    """Build US agency breakdown cards from OMB data."""
    path = DATA_DIR / "us_agency.csv"
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    # Group by fiscal_year
    groups: dict[str, list[dict]] = {}
    for row in rows:
        groups.setdefault(row["fiscal_year"], []).append(row)

    count = 0
    for year, items in sorted(groups.items()):
        lines = [f"FY{year} US Federal Spending by Agency (% of total):<br>"]
        for item in items:
            rank = item["rank"]
            name = item["agency"]
            pct = round(float(item["pct_of_total"]))
            lines.append(f"{rank}. {{{{c1::{name} - {pct}%}}}}<br>")

        content = "\n".join(lines)

        # Pie chart with "Other" slice
        labels = [item["agency"] for item in items]
        values = [float(item["pct_of_total"]) for item in items]
        other_pct = 100 - sum(values)
        if other_pct > 0.5:
            labels.append("Other")
            values.append(other_pct)

        tab10 = plt.cm.tab10.colors
        colors = [tab10[i % 10] for i in range(len(labels))]
        if other_pct > 0.5:
            colors[-1] = OTHER_COLOR

        svg = make_pie_chart(labels, values, colors)

        card_id = f"by_agency_usa_{year}"
        tags = f"govt_spending by_nation by_agency usa {year}"

        writer.writerow([card_id, "by_nation", content, svg, tags])
        count += 1

    return count


def build_by_category_cards(writer: csv.writer) -> int:
    """Build cross-country comparison cards per COFOG division."""
    path = DATA_DIR / "cofog_by_category.csv"
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    # Group by (cofog_code, year)
    groups: dict[tuple[str, str], list[dict]] = {}
    for row in rows:
        key = (row["cofog_code"], row["year"])
        groups.setdefault(key, []).append(row)

    count = 0
    for (code, year), items in sorted(groups.items()):
        cofog_name = items[0]["cofog_name"]

        lines = [f"{year} G7 {cofog_name} Spending (% of GDP):<br>"]
        for item in items:
            rank = item["rank"]
            country_name = item["country_name"]
            pct = float(item["pct_of_gdp"])
            lines.append(f"{rank}. {{{{c1::{country_name} - {pct:.1f}%}}}}<br>")

        content = "\n".join(lines)

        # Horizontal bar chart
        labels = [item["country_name"] for item in items]
        values = [float(item["pct_of_gdp"]) for item in items]
        color = COFOG_COLORS.get(cofog_name, "#1f77b4")
        svg = make_bar_chart(labels, values, color)

        card_id = f"by_category_{code.lower()}_{year}"
        tags = f"govt_spending by_category {code.lower()} {year}"

        writer.writerow([card_id, "by_category", content, svg, tags])
        count += 1

    return count


def build_cards() -> Path:
    """Build all cards and write to cards.csv."""
    out_path = DATA_DIR / "cards.csv"

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["card_id", "deck", "content", "note", "tags"])

        n1 = build_by_nation_cofog_cards(writer)
        n2 = build_us_agency_cards(writer)
        n3 = build_by_category_cards(writer)

    total = n1 + n2 + n3
    print(f"Wrote {out_path}: {total} cards ({n1} by-nation COFOG, {n2} US agency, {n3} by-category)")
    return out_path


if __name__ == "__main__":
    build_cards()
```

- [ ] **Step 2: Run the card builder**

Run: `cd /home/cmf/Dropbox/Apps/knowledge-base && uv run python scripts/govt_spending/build_cards.py`
Expected: `data/govt_spending/cards.csv` created. Output should report card counts matching expectations (~24 by-nation COFOG + 4 US agency + 40 by-category = ~68 cards).

- [ ] **Step 3: Spot-check cards.csv**

Run: `cd /home/cmf/Dropbox/Apps/knowledge-base && uv run python -c "
import csv
with open('data/govt_spending/cards.csv') as f:
    reader = csv.DictReader(f)
    for i, row in enumerate(reader):
        if i < 3 or 'by_agency' in row['card_id'] or 'by_category_gf02' in row['card_id']:
            print(f\"{row['card_id']}: {row['content'][:80]}...\")
            print(f'  SVG length: {len(row[\"note\"])} chars')
            print()
        if i > 50:
            break
"`
Expected: Card content has proper cloze formatting (`{{c1::...}}`), SVG strings are non-empty (several KB each).

- [ ] **Step 4: Commit**

```bash
git add scripts/govt_spending/build_cards.py
git commit -m "feat: add card builder with cloze text and SVG charts"
```

---

### Task 6: Build Anki exporter

**Files:**
- Create: `scripts/govt_spending/export_apkg.py`

- [ ] **Step 1: Write export_apkg.py**

```python
"""Export cards.csv to an Anki .apkg package.

Reads: data/govt_spending/cards.csv
Writes: data/govt_spending/govt_spending.apkg

Uses the Enhanced Cloze Type-In 1.0 note type (model ID 1775162181082).
"""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path

import genanki

# Must match the installed Enhanced Cloze Type-In 1.0 note type
MODEL_ID = 1775162181082

# Stable deck IDs (random large integers, consistent across re-exports)
DECK_BY_NATION_ID = 2010040401
DECK_BY_CATEGORY_ID = 2010040402

DATA_DIR = Path("data/govt_spending")

# genanki model mirroring Enhanced Cloze Type-In 1.0 fields.
# Templates are placeholders — on import, Anki will use the templates
# from the existing note type if the model name matches.
model = genanki.Model(
    MODEL_ID,
    "Enhanced Cloze Type-In 1.0",
    fields=[
        {"name": "Content"},
        {"name": "Note"},
        {"name": "Mnemonics"},
        {"name": "Extra"},
        {"name": "Cloze99"},
    ],
    templates=[
        {
            "name": "Enhanced Cloze Type-In",
            "qfmt": "{{cloze:Content}}",
            "afmt": "{{cloze:Content}}<br>{{Note}}",
        },
    ],
    model_type=genanki.Model.CLOZE,
)


def stable_guid(card_id: str) -> str:
    """Generate a stable GUID from card_id for safe re-import."""
    h = hashlib.sha256(card_id.encode()).hexdigest()
    # genanki expects a string; use first 10 hex chars
    return h[:10]


def export_apkg() -> Path:
    """Read cards.csv and export .apkg."""
    deck_by_nation = genanki.Deck(DECK_BY_NATION_ID, "Government Spending::By Nation")
    deck_by_category = genanki.Deck(DECK_BY_CATEGORY_ID, "Government Spending::By Category")

    cards_path = DATA_DIR / "cards.csv"
    count = 0

    with open(cards_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            note = genanki.Note(
                model=model,
                fields=[
                    row["content"],   # Content
                    row["note"],      # Note (SVG chart)
                    "",               # Mnemonics
                    "",               # Extra
                    "",               # Cloze99
                ],
                tags=row["tags"].split(),
                guid=stable_guid(row["card_id"]),
            )

            if row["deck"] == "by_nation":
                deck_by_nation.add_note(note)
            else:
                deck_by_category.add_note(note)

            count += 1

    out_path = DATA_DIR / "govt_spending.apkg"
    genanki.Package([deck_by_nation, deck_by_category]).write_to_file(str(out_path))
    print(f"Wrote {out_path}: {count} cards")
    return out_path


if __name__ == "__main__":
    export_apkg()
```

- [ ] **Step 2: Run the exporter**

Run: `cd /home/cmf/Dropbox/Apps/knowledge-base && uv run python scripts/govt_spending/export_apkg.py`
Expected: `data/govt_spending/govt_spending.apkg` created, reports ~68 cards

- [ ] **Step 3: Verify the .apkg**

Run: `cd /home/cmf/Dropbox/Apps/knowledge-base && uv run python -c "
import zipfile, sqlite3, tempfile, shutil
from pathlib import Path

apkg = Path('data/govt_spending/govt_spending.apkg')
tmp = Path(tempfile.mkdtemp())
with zipfile.ZipFile(apkg) as z:
    z.extractall(tmp)
db = tmp / 'collection.anki2'
conn = sqlite3.connect(db)
notes = conn.execute('SELECT count(*) FROM notes').fetchone()[0]
cards = conn.execute('SELECT count(*) FROM cards').fetchone()[0]
# Check a sample note
flds = conn.execute('SELECT flds FROM notes LIMIT 1').fetchone()[0]
print(f'Notes: {notes}, Cards: {cards}')
print(f'Sample fields (first 200 chars): {flds[:200]}')
conn.close()
shutil.rmtree(tmp)
"
`
Expected: Note count matches card count (~68). Sample fields contain cloze markup and SVG content.

- [ ] **Step 4: Commit**

```bash
git add scripts/govt_spending/export_apkg.py
git commit -m "feat: add Anki .apkg exporter for govt spending deck"
```

---

### Task 7: End-to-end run and manual review

**Files:** No new files — run the full pipeline and review output

- [ ] **Step 1: Run the full pipeline**

```bash
cd /home/cmf/Dropbox/Apps/knowledge-base
uv run python scripts/govt_spending/fetch_cofog.py
uv run python scripts/govt_spending/fetch_omb.py
uv run python scripts/govt_spending/parse_cofog.py
uv run python scripts/govt_spending/parse_omb_agency.py
uv run python scripts/govt_spending/build_cards.py
uv run python scripts/govt_spending/export_apkg.py
```

Expected: All steps complete without errors.

- [ ] **Step 2: Review the curated CSVs**

Open and inspect:
- `data/govt_spending/cofog_by_nation.csv` — verify country names, rankings, percentages look reasonable
- `data/govt_spending/cofog_by_category.csv` — verify cross-country rankings make sense (e.g., USA should lead in Defence spending)
- `data/govt_spending/us_agency.csv` — verify agency names are clean, top agencies are recognizable

- [ ] **Step 3: Review cards.csv**

Open `data/govt_spending/cards.csv` and verify:
- Cloze formatting is correct (`{{c1::...}}`)
- Percentage rounding is sensible
- SVG strings are present and non-empty
- Card IDs are unique

Make any hand-edits needed (this is the edit seam).

- [ ] **Step 4: Re-export if edits were made**

If `cards.csv` was edited:
```bash
uv run python scripts/govt_spending/export_apkg.py
```

- [ ] **Step 5: Import into Anki and verify**

Import `data/govt_spending/govt_spending.apkg` into Anki. Verify:
- Cards appear in `Government Spending::By Nation` and `Government Spending::By Category` decks
- Cloze type-in fields work (type answer, press Enter, see diff)
- SVG pie/bar charts render correctly on the back side
- Tags are present

- [ ] **Step 6: Final commit**

```bash
git add scripts/govt_spending/
git commit -m "feat: complete govt spending Anki deck pipeline"
```
