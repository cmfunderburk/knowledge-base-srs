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


# Decks that use interval/point prediction cards (not cloze)
IMPORTABLE_DECKS = [k for k in DECKS if k != "descriptive_stats"]

DEFAULT_DESC_STATS_DIR = Path("data/descriptive_stats")


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

    Returns dict with keys "mean" and "std", or None if file is missing or empty.
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


def _desc_stats_prefix_for_deck(deck_key: str) -> str:
    """Return the desc stats filename prefix for a deck."""
    if deck_key == "urban_areas":
        return "urban_"
    return ""


# ---------------------------------------------------------------------------
# Deck import (interval/point prediction cards)
# ---------------------------------------------------------------------------


def import_deck(
    conn,
    deck_key: str,
    data_dir: Path | None = None,
    desc_stats_dir: Path | None = None,
    desc_stats_prefix: str | None = None,
) -> int:
    """Import cards from CSV data files into the SRS database.

    Reads CSVs matching indicator ids for the given deck, generates card
    content, and upserts each non-region/non-aggregate row.

    Returns count of cards upserted.
    """
    if deck_key not in DECKS:
        raise KeyError(f"Unknown deck key: {deck_key!r}. Available: {list(DECKS)}")

    deck_cfg = DECKS[deck_key]
    entities = deck_cfg.get("entities", ENTITIES)
    ref_entity = deck_cfg.get("reference_entity", "World")
    ref_entity_type = deck_cfg.get("reference_entity_type", "region")
    indicator_by_id = {ind["id"]: ind for ind in deck_cfg["indicators"]}
    resolved_data_dir = data_dir or Path(deck_cfg["data_dir"])
    resolved_stats_dir = desc_stats_dir or DEFAULT_DESC_STATS_DIR
    resolved_prefix = desc_stats_prefix if desc_stats_prefix is not None else _desc_stats_prefix_for_deck(deck_key)

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
        raw_stats = _load_desc_stats(resolved_stats_dir, indicator_id, resolved_prefix)
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

            question = generate_question(
                entity=entity_name,
                indicator_name=indicator["name"],
                year=year,
                unit_label=indicator["unit_label"],
                era=era,
            )

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

            tags = build_tags(
                category=indicator["category"],
                indicator_id=indicator_id,
                entity_slug=entity_slug,
                entity_type=entity_type,
                era=era,
            )

            display_answer = value / scale_factor

            upsert_card(conn, {
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
            })
            count += 1

    return count


# ---------------------------------------------------------------------------
# Descriptive stats import (mean/median/SD as separate point-prediction cards)
# ---------------------------------------------------------------------------


def _generate_stat_question(
    stat_label: str,
    indicator_name: str,
    year: int,
    unit_label: str,
    n: int,
    source_deck: str,
) -> str:
    """Generate a question for a descriptive statistic card."""
    scope = "cities" if source_deck == "urban_areas" else "countries"
    return (
        f"What is the {stat_label} {indicator_name} across {n} {scope} "
        f"as of {year}, {unit_label}?"
    )


def import_desc_stats(
    conn,
    desc_stats_dir: Path | None = None,
) -> int:
    """Import descriptive statistics as point-prediction cards.

    Creates separate cards for mean, median, and SD of each indicator.
    Uses the indicator's own mean/std for scoring context.

    Returns count of cards upserted.
    """
    resolved_dir = desc_stats_dir or DEFAULT_DESC_STATS_DIR
    csv_files = sorted(resolved_dir.glob("*.csv"))

    count = 0
    for csv_path in csv_files:
        df = pl.read_csv(csv_path)
        if len(df) == 0:
            continue

        row = df.row(0, named=True)

        indicator_id = row["indicator_id"]
        indicator_name = row["indicator_name"]
        category = row["category"]
        source_deck = row["source_deck"]
        unit_label = row["unit_label"]
        unit_prefix = row.get("unit_prefix", "")
        decimals = int(row.get("decimals", 0))
        scale_factor = int(row.get("scale_factor", 1))
        year = int(row["year"])
        n = int(row["n"])

        raw_mean = float(row["mean"])
        raw_median = float(row["median"])
        raw_std = float(row["std"])

        # Convert to display units
        disp_mean = raw_mean / scale_factor
        disp_median = raw_median / scale_factor
        disp_std = raw_std / scale_factor

        # Notes: provide the other stats as context
        notes = (
            f"Source: {source_deck} descriptive stats ({year}) | "
            f"n={n}, min={row['min_entity']}, max={row['max_entity']}"
        )

        stats_to_import = [
            ("mean", disp_mean),
            ("median", disp_median),
            ("standard deviation", disp_std),
        ]

        for stat_label, stat_value in stats_to_import:
            question = _generate_stat_question(
                stat_label=stat_label,
                indicator_name=indicator_name,
                year=year,
                unit_label=unit_label,
                n=n,
                source_deck=source_deck,
            )

            tags = [
                f"category::{category}",
                f"indicator::{indicator_id}",
                f"stat::{stat_label.replace(' ', '_')}",
                f"source_deck::{source_deck}",
            ]

            upsert_card(conn, {
                "deck": "descriptive_stats",
                "indicator_id": f"{indicator_id}__{stat_label.replace(' ', '_')}",
                "entity": f"all_{source_deck}",
                "era": str(year),
                "question": question,
                "answer": stat_value,
                "unit_prefix": unit_prefix,
                "unit_label": unit_label,
                "notes": notes,
                "tags": json.dumps(tags),
                "indicator_mean": disp_mean,
                "indicator_std": disp_std if disp_std > 0 else None,
                "scale_factor": scale_factor,
                "decimals": decimals,
            })
            count += 1

    return count


# ---------------------------------------------------------------------------
# Bulk import
# ---------------------------------------------------------------------------


def import_all(conn, desc_stats_dir: Path | None = None) -> dict[str, int]:
    """Import all decks plus descriptive stats cards.

    Returns dict mapping deck_key → card count.
    """
    results = {}
    for deck_key in IMPORTABLE_DECKS:
        results[deck_key] = import_deck(conn, deck_key, desc_stats_dir=desc_stats_dir)
    results["descriptive_stats"] = import_desc_stats(conn, desc_stats_dir=desc_stats_dir)
    return results


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI entry point: import decks into data/srs.db."""
    import argparse

    parser = argparse.ArgumentParser(description="Import Knowledge Base decks into SRS")
    parser.add_argument(
        "deck", nargs="?", default=None,
        help=f"Deck to import (omit for all). Choices: {', '.join(IMPORTABLE_DECKS)}, descriptive_stats, --all",
    )
    parser.add_argument("--all", action="store_true", help="Import all decks")
    parser.add_argument("--db", default="data/srs.db", help="Database path (default: data/srs.db)")
    args = parser.parse_args()

    db_path = Path(args.db)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = init_db(db_path)

    if args.all or args.deck is None:
        results = import_all(conn)
        total = sum(results.values())
        for dk, n in results.items():
            print(f"  {dk}: {n} cards")
        print(f"Total: {total} cards imported into {db_path}")
    elif args.deck == "descriptive_stats":
        n = import_desc_stats(conn)
        print(f"Imported {n} descriptive stats cards into {db_path}")
    else:
        n = import_deck(conn, args.deck)
        print(f"Imported {n} cards for '{args.deck}' into {db_path}")
