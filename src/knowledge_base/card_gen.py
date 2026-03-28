"""
Card generation helpers: pure functions that map entity + indicator + year → strings.

These are shared between build_deck.py (Anki card generation) and any downstream
consumers (e.g. an SRS importer that populates an SQLite database).
"""

from __future__ import annotations


def format_answer(value: float, indicator: dict) -> str:
    """Round and format a numerical answer for the card."""
    scale_factor = indicator.get("scale_factor", 1)
    decimals = indicator.get("decimals", 1)
    scaled = value / scale_factor
    rounded = round(scaled, decimals)
    if decimals == 0:
        return str(int(rounded))
    return f"{rounded:.{decimals}f}"


def generate_question(
    entity: str,
    indicator_name: str,
    year: int,
    unit_label: str,
    era: str,
) -> str:
    """Produce the Front field for an Anki card.

    Uses "What is...as of {year}" for current era,
    "What was...in {year}" for historical eras.
    """
    if era == "current":
        return (
            f"What is {entity}'s {indicator_name} as of {year}, {unit_label}?"
        )
    else:
        return (
            f"What was {entity}'s {indicator_name} in {year}, {unit_label}?"
        )


def _format_number(
    value: float | int, prefix: str = "", decimals: int = 0
) -> str:
    """Format a number with commas and an optional prefix."""
    if decimals == 0:
        return f"{prefix}{value:,.0f}"
    return f"{prefix}{value:,.{decimals}f}"


def generate_notes(
    source: str,
    world_avg: float | None,
    regional_avg: float | None,
    unit_prefix: str = "",
    decimals: int = 0,
) -> str:
    """Produce the Notes field with source and reference comparisons.

    Includes world average and (if available) regional average,
    formatted with commas and the unit prefix.
    """
    parts = [f"Source: {source}"]
    if world_avg is not None:
        formatted_world = _format_number(world_avg, unit_prefix, decimals)
        if regional_avg is not None:
            formatted_regional = _format_number(
                regional_avg, unit_prefix, decimals
            )
            parts.append(
                f"World avg: {formatted_world}, regional avg: {formatted_regional}"
            )
        else:
            parts.append(f"World avg: {formatted_world}")
    return " | ".join(parts)


def generate_notes_land_area(
    source: str,
    reference_total: int | float,
) -> str:
    """Produce the Notes field for land area cards."""
    formatted_total = f"{reference_total:,.0f}"
    return f"Source: {source} | Reference total: {formatted_total} km\u00b2"


def build_tags(
    category: str,
    indicator_id: str,
    entity_slug: str,
    entity_type: str,
    era: str,
) -> list[str]:
    """Return a list of tag strings for an Anki note."""
    return [
        f"category::{category}",
        f"indicator::{indicator_id}",
        f"entity::{entity_slug}",
        f"entity_type::{entity_type}",
        f"era::{era}",
    ]
