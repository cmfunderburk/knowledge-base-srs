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
