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
