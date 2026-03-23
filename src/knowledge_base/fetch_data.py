"""Fetch World Bank indicator data and write per-indicator CSV files."""

from __future__ import annotations

import warnings
from pathlib import Path

import polars as pl

from knowledge_base.config import ENTITIES, ERA_RANGES, INDICATORS
from knowledge_base.wb_api import fetch_indicator

# ---------------------------------------------------------------------------
# Public constants
# ---------------------------------------------------------------------------

EXPECTED_COLUMNS = ["entity", "entity_type", "region", "era", "year", "value", "source"]

WB_SOURCE = "World Bank WDI"

# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------


def select_best_year_for_era(
    records: list[dict],
    country_code: str,
    era: str,
) -> dict | None:
    """Return the best record for *country_code* within the given *era*.

    Args:
        records: List of dicts with keys ``country_code``, ``year``, ``value``.
        country_code: ISO-3 (or WB aggregate) code to filter on.
        era: One of the keys in ``ERA_RANGES`` (e.g. ``"1960"``, ``"current"``).

    Returns:
        The best matching record dict, or ``None`` if nothing falls in range.
    """
    range_start, range_end, target_year = ERA_RANGES[era]

    # Filter to this entity and the valid year window
    candidates = [
        r for r in records
        if r["country_code"] == country_code
        and range_start <= r["year"] <= range_end
    ]

    if not candidates:
        return None

    if era == "current":
        # Pick the most recent year available
        return max(candidates, key=lambda r: r["year"])

    # Historical era: pick closest to target_year; on ties prefer later year
    return min(candidates, key=lambda r: (abs(r["year"] - target_year), -r["year"]))


def build_indicator_dataframe(rows: list[dict]) -> pl.DataFrame:
    """Build a polars DataFrame from a list of row dicts.

    Each dict should have the keys defined in ``EXPECTED_COLUMNS``.
    Missing keys are filled with ``None``.
    """
    # Ensure all expected columns are present
    normalised = [
        {col: row.get(col) for col in EXPECTED_COLUMNS}
        for row in rows
    ]
    return pl.DataFrame(normalised, schema=_column_schema())


def _column_schema() -> dict[str, type]:
    """Return the polars schema for the output CSV."""
    return {
        "entity": pl.Utf8,
        "entity_type": pl.Utf8,
        "region": pl.Utf8,
        "era": pl.Utf8,
        "year": pl.Int64,
        "value": pl.Float64,
        "source": pl.Utf8,
    }


# ---------------------------------------------------------------------------
# City population (bundled CSV)
# ---------------------------------------------------------------------------

def _handle_city_population(output_dir: Path) -> None:
    """Read UN WUP city data from the bundled CSV and write output CSV."""
    resources_dir = Path(__file__).parent.parent.parent / "resources"
    csv_path = resources_dir / "un_wup_cities.csv"

    if not csv_path.exists():
        warnings.warn(
            f"City population data not found at {csv_path}; skipping city_population.",
            stacklevel=2,
        )
        return

    # Collect iso3 codes for all country entities
    entity_iso3_set = {
        e["iso3"] for e in ENTITIES if "iso3" in e
    }

    df_cities = pl.read_csv(csv_path)

    # Filter to cities whose country is in our entity list
    df_filtered = df_cities.filter(
        pl.col("country_iso3").is_in(list(entity_iso3_set))
    )

    # Build rows in the standard format
    rows: list[dict] = []
    for row in df_filtered.iter_rows(named=True):
        # Resolve entity name from iso3
        entity_name = row.get("city_name", row.get("name", ""))
        country_iso3 = row.get("country_iso3", "")

        # Find the country entity to get region / entity_type
        country_entity = next(
            (e for e in ENTITIES if e.get("iso3") == country_iso3), None
        )
        region = country_entity.get("region", "") if country_entity else ""
        entity_type = "city"

        rows.append({
            "entity": entity_name,
            "entity_type": entity_type,
            "region": region,
            "era": "current",
            "year": int(row.get("year", 0)),
            "value": float(row.get("population", row.get("value", 0))),
            "source": "UN WUP",
        })

    df_out = build_indicator_dataframe(rows)
    out_path = output_dir / "city_population.csv"
    df_out.write_csv(out_path)
    print(f"  wrote {len(df_out)} rows → {out_path}")


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------


def main(output_dir: Path = Path("data")) -> None:
    """Fetch all indicators and write per-indicator CSV files.

    Args:
        output_dir: Directory to write CSV files into (created if absent).
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Build entity lookup: code → entity dict
    entity_by_code: dict[str, dict] = {}
    for entity in ENTITIES:
        code = entity.get("iso3") or entity.get("wb_code")
        if code:
            entity_by_code[code] = entity

    for indicator in INDICATORS:
        indicator_id = indicator["id"]
        print(f"Processing {indicator_id}…")

        # City population is handled separately
        if indicator.get("current_only"):
            _handle_city_population(output_dir)
            continue

        wb_code = indicator["wb_code"]
        time_invariant = indicator.get("time_invariant", False)
        has_regional_aggregates = indicator.get("has_regional_aggregates", True)

        # Build the list of codes to request
        all_codes: list[str] = []
        for entity in ENTITIES:
            if entity["entity_type"] == "region":
                if not has_regional_aggregates:
                    continue
                all_codes.append(entity["wb_code"])
            else:
                all_codes.append(entity["iso3"])

        # Determine which eras to fetch
        eras_to_fetch = ["current"] if time_invariant else list(ERA_RANGES.keys())

        # Fetch data once for the full year range
        year_start = 1955
        year_end = 2026

        try:
            records = fetch_indicator(wb_code, all_codes, year_start, year_end)
        except Exception as exc:
            print(f"  ERROR fetching {indicator_id}: {exc}")
            continue

        rows: list[dict] = []
        for entity in ENTITIES:
            if entity["entity_type"] == "region" and not has_regional_aggregates:
                continue

            code = entity.get("iso3") or entity.get("wb_code")
            entity_name = entity["name"]
            entity_type = entity["entity_type"]
            region = entity.get("region", "")

            for era in eras_to_fetch:
                best = select_best_year_for_era(records, code, era)
                if best is None:
                    continue
                rows.append({
                    "entity": entity_name,
                    "entity_type": entity_type,
                    "region": region,
                    "era": era,
                    "year": best["year"],
                    "value": float(best["value"]),
                    "source": WB_SOURCE,
                })

        df = build_indicator_dataframe(rows)
        out_path = output_dir / f"{indicator_id}.csv"
        df.write_csv(out_path)
        print(f"  wrote {len(df)} rows → {out_path}")

    print("Done.")


if __name__ == "__main__":
    main()
