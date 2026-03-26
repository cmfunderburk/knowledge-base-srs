"""Thin reader for the GHS-UCDB GeoPackage (sqlite3-based)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

BOM = "\ufeff"

_TABLE_PREFIX = "GHS_UCDB_THEME_"
_TABLE_SUFFIX = "_GLOBE_R2024A"


def fetch_indicator(
    gpkg_path: Path,
    table_name: str,
    column_prefix: str,
    uc_ids: list[int],
    years: list[int],
) -> list[dict]:
    """Extract indicator values from the GeoPackage.

    Args:
        gpkg_path: Path to the .gpkg file.
        table_name: Theme keyword (e.g., "GHSL", "EMISSIONS").
        column_prefix: Column prefix without year (e.g., "GH_POP_TOT").
        uc_ids: List of urban centre IDs to extract.
        years: List of years to extract.

    Returns:
        List of {"uc_id": int, "year": int, "value": float} dicts.
        Rows with NULL values are excluded.
    """
    full_table = f"{_TABLE_PREFIX}{table_name}{_TABLE_SUFFIX}"
    id_col = f"{BOM}ID_UC_G0"

    con = sqlite3.connect(gpkg_path)
    try:
        existing_cols = {
            c[1] for c in con.execute(f'PRAGMA table_info("{full_table}")').fetchall()
        }

        year_cols = []
        for year in years:
            col = f"{BOM}{column_prefix}_{year}"
            if col in existing_cols:
                year_cols.append((year, col))

        if not year_cols:
            return []

        col_exprs = ", ".join(f'"{col}"' for _, col in year_cols)
        placeholders = ",".join("?" for _ in uc_ids)
        sql = f'SELECT "{id_col}", {col_exprs} FROM "{full_table}" WHERE "{id_col}" IN ({placeholders})'

        rows = con.execute(sql, uc_ids).fetchall()
    finally:
        con.close()

    results = []
    for row in rows:
        uc_id = row[0]
        for i, (year, _) in enumerate(year_cols):
            value = row[i + 1]
            if value is not None:
                results.append({"uc_id": uc_id, "year": year, "value": float(value)})

    return results
