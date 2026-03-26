"""Fetch GHS-UCDB indicator data and write per-indicator CSV files."""

from __future__ import annotations

import statistics
from pathlib import Path

import polars as pl

from knowledge_base.config import DECKS, URBAN_ENTITIES
from knowledge_base.ghsl import fetch_indicator

EXPECTED_COLUMNS = ["entity", "entity_type", "region", "era", "year", "value", "source"]
GHSL_SOURCE = "GHS-UCDB R2024A"


def _column_schema() -> dict[str, type]:
    return {
        "entity": pl.Utf8,
        "entity_type": pl.Utf8,
        "region": pl.Utf8,
        "era": pl.Utf8,
        "year": pl.Int64,
        "value": pl.Float64,
        "source": pl.Utf8,
    }


def build_urban_indicator_dataframe(rows: list[dict]) -> pl.DataFrame:
    normalised = [{col: row.get(col) for col in EXPECTED_COLUMNS} for row in rows]
    return pl.DataFrame(normalised, schema=_column_schema())


def compute_median_aggregates(city_rows: list[dict], source: str) -> list[dict]:
    """Compute All Cities and per-income-group median aggregates."""
    by_era: dict[str, list[dict]] = {}
    for row in city_rows:
        by_era.setdefault(row["era"], []).append(row)

    aggregates = []
    for era, rows in by_era.items():
        values = [r["value"] for r in rows]
        year = rows[0]["year"]

        aggregates.append({
            "entity": "All Cities",
            "entity_type": "aggregate",
            "region": "",
            "era": era,
            "year": year,
            "value": statistics.median(values),
            "source": source,
        })

        by_group: dict[str, list[float]] = {}
        for row in rows:
            by_group.setdefault(row["region"], []).append(row["value"])

        for group, group_values in by_group.items():
            aggregates.append({
                "entity": group,
                "entity_type": "aggregate",
                "region": "",
                "era": era,
                "year": year,
                "value": statistics.median(group_values),
                "source": source,
            })

    return aggregates


def _run(output_dir: Path | None = None) -> None:
    deck = DECKS["urban_areas"]
    indicators = deck["indicators"]
    gpkg_path = Path(deck["gpkg_path"])

    if output_dir is None:
        output_dir = Path(deck["data_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)

    cities = [e for e in URBAN_ENTITIES if e["entity_type"] == "city"]
    entity_by_id = {e["uc_id"]: e for e in cities}
    uc_ids = list(entity_by_id.keys())

    for indicator in indicators:
        indicator_id = indicator["id"]
        print(f"Processing {indicator_id}…")

        records = fetch_indicator(
            gpkg_path=gpkg_path,
            table_name=indicator["ghsl_table"],
            column_prefix=indicator["ghsl_column"],
            uc_ids=uc_ids,
            years=indicator["years"],
        )

        city_rows: list[dict] = []
        for record in records:
            entity = entity_by_id.get(record["uc_id"])
            if entity is None:
                continue
            city_rows.append({
                "entity": entity["name"],
                "entity_type": "city",
                "region": entity["income_group"],
                "era": str(record["year"]),
                "year": record["year"],
                "value": float(record["value"]),
                "source": GHSL_SOURCE,
            })

        aggregates = compute_median_aggregates(city_rows, GHSL_SOURCE)

        all_rows = city_rows + aggregates
        df = build_urban_indicator_dataframe(all_rows)
        out_path = output_dir / f"{indicator_id}.csv"
        df.write_csv(out_path)
        print(f"  wrote {len(df)} rows → {out_path}")

    print("Done.")


def main() -> None:
    """CLI entry point."""
    _run()


if __name__ == "__main__":
    main()
