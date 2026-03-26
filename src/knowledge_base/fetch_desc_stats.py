"""Fetch descriptive statistics for all indicators across Knowledge Base decks."""

from __future__ import annotations

from pathlib import Path

import polars as pl

from knowledge_base.config import DECKS
from knowledge_base.desc_stats import compute_desc_stats
from knowledge_base.wb_api import fetch_indicator

# ---------------------------------------------------------------------------
# Public constants
# ---------------------------------------------------------------------------

STATS_COLUMNS = [
    "indicator_id", "indicator_name", "category", "source_deck", "unit_label",
    "unit_prefix", "decimals", "scale_factor", "year", "n", "mean",
    "median", "std", "min_value", "min_entity", "max_value", "max_entity",
]

WB_SOURCE_DECKS = ["development", "tech_adoption", "conflict_security", "finance"]

# ---------------------------------------------------------------------------
# World Bank helpers
# ---------------------------------------------------------------------------


def _fetch_all_country_codes() -> tuple[list[str], dict[str, str]]:
    """Return (list of all WB country ISO3 codes, {iso3: name} mapping).

    Uses the World Bank API country list endpoint.
    """
    import httpx
    from knowledge_base.wb_api import WB_API_BASE

    url = f"{WB_API_BASE}/country"
    params = {"format": "json", "per_page": 500}
    resp = httpx.get(url, params=params)
    resp.raise_for_status()
    data = resp.json()

    codes = []
    names = {}
    for entry in data[1]:
        # Skip aggregates (region, lending type, etc.)
        if entry["region"]["id"] == "NA":
            continue
        iso3 = entry["id"]
        codes.append(iso3)
        names[iso3] = entry["name"]
    return codes, names


def compute_wb_indicator_stats(
    records: list[dict],
    country_names: dict[str, str],
) -> dict:
    """Compute descriptive stats from raw WB API records.

    Picks the most recent year per country, then computes stats.
    Returns dict with keys: n, mean, median, std, min_value, min_entity,
    max_value, max_entity, year.
    """
    # Pick most recent record per country
    best: dict[str, dict] = {}
    for r in records:
        code = r["country_code"]
        if code not in best or r["year"] > best[code]["year"]:
            best[code] = r

    if not best:
        return None

    # Build DataFrame for compute_desc_stats
    rows = []
    years = []
    for code, rec in best.items():
        name = country_names.get(code, code)
        rows.append({"entity": name, "value": float(rec["value"])})
        years.append(rec["year"])

    df = pl.DataFrame(rows)
    stats = compute_desc_stats(df)
    # Use the most common year as the representative year
    stats["year"] = max(set(years), key=years.count)
    return stats


def build_stats_dataframe(row: dict) -> pl.DataFrame:
    """Build a single-row polars DataFrame from a stats dict."""
    return pl.DataFrame(
        [{col: row.get(col) for col in STATS_COLUMNS}],
        schema={
            "indicator_id": pl.Utf8,
            "indicator_name": pl.Utf8,
            "category": pl.Utf8,
            "source_deck": pl.Utf8,
            "unit_label": pl.Utf8,
            "unit_prefix": pl.Utf8,
            "decimals": pl.Int64,
            "scale_factor": pl.Int64,
            "year": pl.Int64,
            "n": pl.Int64,
            "mean": pl.Float64,
            "median": pl.Float64,
            "std": pl.Float64,
            "min_value": pl.Float64,
            "min_entity": pl.Utf8,
            "max_value": pl.Float64,
            "max_entity": pl.Utf8,
        },
    )


# ---------------------------------------------------------------------------
# WB fetch orchestrator
# ---------------------------------------------------------------------------


def fetch_wb_stats(output_dir: Path) -> None:
    """Fetch full cross-section stats for all WB indicators and write CSVs."""
    output_dir.mkdir(parents=True, exist_ok=True)

    all_codes, country_names = _fetch_all_country_codes()

    for deck_key in WB_SOURCE_DECKS:
        deck = DECKS[deck_key]
        era_ranges = deck["era_ranges"]
        year_start, year_end, _ = era_ranges["current"]

        for indicator in deck["indicators"]:
            indicator_id = indicator["id"]
            print(f"  [{deck_key}] {indicator_id}...")

            try:
                records = fetch_indicator(
                    indicator["wb_code"], all_codes, year_start, year_end
                )
            except Exception as exc:
                print(f"    ERROR fetching {indicator_id}: {exc}")
                continue

            stats = compute_wb_indicator_stats(records, country_names)
            if stats is None:
                print(f"    No data for {indicator_id}")
                continue

            row = {
                **stats,
                "indicator_id": indicator_id,
                "indicator_name": indicator["name"],
                "category": indicator["category"],
                "source_deck": deck_key,
                "unit_label": indicator["unit_label"],
                "unit_prefix": indicator.get("unit_prefix", ""),
                "decimals": indicator.get("decimals", 1),
                "scale_factor": indicator.get("scale_factor", 1),
            }
            df = build_stats_dataframe(row)
            out_path = output_dir / f"{indicator_id}.csv"
            df.write_csv(out_path)
            print(f"    wrote {out_path}")
