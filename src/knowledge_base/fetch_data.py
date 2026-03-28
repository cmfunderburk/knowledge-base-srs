"""Fetch World Bank indicator data and write per-indicator CSV files."""

from __future__ import annotations

from pathlib import Path

import polars as pl

from knowledge_base.config import DECKS, ENTITIES
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
    era_ranges: dict,
) -> dict | None:
    """Return the best record for *country_code* within the given *era*.

    Args:
        records: List of dicts with keys ``country_code``, ``year``, ``value``.
        country_code: ISO-3 (or WB aggregate) code to filter on.
        era: One of the keys in ``era_ranges`` (e.g. ``"1960"``, ``"current"``).
        era_ranges: Mapping of era name to (range_start, range_end, target_year).

    Returns:
        The best matching record dict, or ``None`` if nothing falls in range.
    """
    range_start, range_end, target_year = era_ranges[era]

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
# Core orchestrator
# ---------------------------------------------------------------------------


def _run(deck_key: str, output_dir: Path | None = None) -> None:
    """Fetch all indicators for *deck_key* and write per-indicator CSV files.

    Args:
        deck_key: Key into ``DECKS`` (e.g. ``"development"``).
        output_dir: Directory to write CSV files into (overrides deck data_dir).
    """
    deck = DECKS[deck_key]
    indicators = deck["indicators"]
    era_ranges = deck["era_ranges"]

    if output_dir is None:
        output_dir = Path(deck["data_dir"])

    output_dir.mkdir(parents=True, exist_ok=True)

    # Derive year range from era_ranges
    year_start = min(start for start, _, _ in era_ranges.values())
    year_end = max(end for _, end, _ in era_ranges.values())

    # Build entity lookup: code → entity dict
    entity_by_code: dict[str, dict] = {}
    for entity in ENTITIES:
        code = entity.get("iso3") or entity.get("wb_code")
        if code:
            entity_by_code[code] = entity

    for indicator in indicators:
        indicator_id = indicator["id"]
        print(f"Processing {indicator_id}…")

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
        eras_to_fetch = ["current"] if time_invariant else list(era_ranges.keys())

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
                best = select_best_year_for_era(records, code, era, era_ranges)
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


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI entry point."""
    import sys
    if len(sys.argv) < 2:
        print(f"Usage: fetch-data <deck_key>")
        print(f"Available decks: {', '.join(DECKS)}")
        raise SystemExit(1)
    _run(sys.argv[1])


if __name__ == "__main__":
    main()
