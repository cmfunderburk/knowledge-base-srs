"""Importer: reads CSV data files and populates the SRS SQLite database.

Follows the same card-generation pipeline as build_deck.py, but writes
to SQLite via upsert_card instead of genanki.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import polars as pl

from knowledge_base.card_gen import (
    build_tags,
    format_answer,
    generate_notes,
    generate_notes_land_area,
    generate_question,
)
from knowledge_base.build_deck import compute_reference_averages
from knowledge_base.config import DECKS, ENTITIES
from knowledge_base.srs.db import init_db, upsert_card


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _find_entity_config(entity_name: str, entities: list[dict]) -> dict | None:
    """Find entity config by name from the given entity list."""
    for e in entities:
        if e["name"] == entity_name:
            return e
    return None


def _load_desc_stats(
    desc_stats_dir: Path, indicator_id: str, prefix: str = ""
) -> dict | None:
    """Load mean and std from a descriptive stats CSV for an indicator.

    Parameters
    ----------
    desc_stats_dir:
        Directory containing desc stats CSV files.
    indicator_id:
        Indicator id used to construct the filename.
    prefix:
        Optional filename prefix (e.g. "urban_" for the urban deck).

    Returns
    -------
    dict with keys "mean" and "std", or None if file is missing or empty.
    """
    filename = f"{prefix}{indicator_id}.csv"
    csv_path = desc_stats_dir / filename
    if not csv_path.exists():
        return None
    df = pl.read_csv(csv_path)
    if len(df) == 0:
        return None
    row = df.row(0, named=True)
    return {"mean": float(row["mean"]), "std": float(row["std"])}


# ---------------------------------------------------------------------------
# Main import function
# ---------------------------------------------------------------------------


def import_deck(
    conn,
    deck_key: str,
    data_dir: Path | None = None,
    desc_stats_dir: Path | None = None,
    desc_stats_prefix: str = "",
) -> int:
    """Import cards from CSV data files into the SRS database.

    Reads CSVs matching indicator ids for the given deck, generates card
    content, and upserts each non-region/non-aggregate row.

    Parameters
    ----------
    conn:
        Open sqlite3 connection (from init_db).
    deck_key:
        Key into the DECKS registry.
    data_dir:
        Override for the deck's data directory.
    desc_stats_dir:
        Directory containing descriptive stats CSVs. If None, desc stats
        are not attached to cards.
    desc_stats_prefix:
        Filename prefix for desc stats files (e.g. "urban_").

    Returns
    -------
    int
        Count of cards upserted.
    """
    if deck_key not in DECKS:
        raise KeyError(f"Unknown deck key: {deck_key!r}. Available: {list(DECKS)}")

    deck_cfg = DECKS[deck_key]
    entities = deck_cfg.get("entities", ENTITIES)
    ref_entity = deck_cfg.get("reference_entity", "World")
    ref_entity_type = deck_cfg.get("reference_entity_type", "region")
    indicator_by_id = {ind["id"]: ind for ind in deck_cfg["indicators"]}
    resolved_data_dir = data_dir or Path(deck_cfg["data_dir"])

    count = 0
    csv_files = sorted(resolved_data_dir.glob("*.csv"))

    for csv_path in csv_files:
        indicator_id = csv_path.stem
        indicator = indicator_by_id.get(indicator_id)
        if indicator is None:
            continue

        df = pl.read_csv(csv_path)
        if len(df) == 0:
            continue

        scale_factor = indicator.get("scale_factor", 1)
        unit_prefix = indicator.get("unit_prefix", "")
        decimals = indicator.get("decimals", 0)
        is_land_area = indicator_id == "land_area"

        # Load descriptive stats (values are in raw units; divide by scale_factor)
        raw_stats = None
        if desc_stats_dir is not None:
            raw_stats = _load_desc_stats(desc_stats_dir, indicator_id, desc_stats_prefix)
        indicator_mean = raw_stats["mean"] / scale_factor if raw_stats else None
        indicator_std = raw_stats["std"] / scale_factor if raw_stats else None

        # Compute reference averages per era
        eras = df["era"].unique().to_list()
        ref_by_era: dict[str, tuple[float | None, dict[str, float]]] = {}
        for era in eras:
            ref_by_era[era] = compute_reference_averages(
                df, era,
                reference_entity=ref_entity,
                reference_entity_type=ref_entity_type,
            )

        # Filter to non-region/non-aggregate rows
        card_rows = df.filter(
            ~pl.col("entity_type").is_in(["region", "aggregate"])
        )

        for row in card_rows.iter_rows(named=True):
            entity_name = row["entity"]
            entity_cfg = _find_entity_config(entity_name, entities)
            if entity_cfg is None:
                continue

            era = row["era"]
            year = row["year"]
            value = row["value"]
            source = row["source"]
            entity_slug = entity_cfg["tag_slug"]
            entity_type = entity_cfg["entity_type"]

            # Question
            question = generate_question(
                entity=entity_name,
                indicator_name=indicator["name"],
                year=year,
                unit_label=indicator["unit_label"],
                era=era,
            )

            # Notes
            world_avg, region_avgs = ref_by_era.get(era, (None, {}))
            if is_land_area:
                region_name = entity_cfg.get("region", "")
                reference_total = region_avgs.get(region_name, world_avg or 0)
                notes = generate_notes_land_area(
                    source=source,
                    reference_total=reference_total,
                )
            else:
                region_name = entity_cfg.get("region", "")
                regional_avg = region_avgs.get(region_name)
                scaled_world = world_avg / scale_factor if world_avg is not None else None
                scaled_regional = regional_avg / scale_factor if regional_avg is not None else None
                notes = generate_notes(
                    source=source,
                    world_avg=scaled_world,
                    regional_avg=scaled_regional,
                    unit_prefix=unit_prefix,
                    decimals=decimals,
                )

            # Tags
            tags = build_tags(
                category=indicator["category"],
                indicator_id=indicator_id,
                entity_slug=entity_slug,
                entity_type=entity_type,
                era=era,
            )

            # Display answer (in display units)
            display_answer = value / scale_factor

            card = {
                "deck": deck_key,
                "indicator_id": indicator_id,
                "entity": entity_name,
                "era": era,
                "question": question,
                "answer": display_answer,
                "unit_prefix": unit_prefix,
                "unit_label": indicator["unit_label"],
                "notes": notes,
                "tags": json.dumps(tags),
                "indicator_mean": indicator_mean,
                "indicator_std": indicator_std,
                "scale_factor": scale_factor,
                "decimals": decimals,
            }

            upsert_card(conn, card)
            count += 1

    return count


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI entry point: import a deck by key into data/srs.db."""
    if len(sys.argv) < 2:
        print("Usage: import-deck <deck_key>")
        print(f"Available decks: {', '.join(DECKS)}")
        raise SystemExit(1)

    deck_key = sys.argv[1]
    db_path = Path("data/srs.db")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = init_db(db_path)
    n = import_deck(conn, deck_key)
    print(f"Imported {n} cards for deck '{deck_key}' into {db_path}")
