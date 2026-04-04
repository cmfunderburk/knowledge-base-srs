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
