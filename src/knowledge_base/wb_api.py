"""Thin client for the World Bank Indicators API v2."""

import httpx

WB_API_BASE = "https://api.worldbank.org/v2"


def fetch_indicator(
    indicator_code: str,
    country_codes: list[str],
    year_start: int,
    year_end: int,
) -> list[dict]:
    """Fetch indicator data for given countries and year range.

    Returns list of dicts with keys: country_code, year, value.
    Null values are excluded.
    """
    countries = ";".join(country_codes)
    url = f"{WB_API_BASE}/country/{countries}/indicator/{indicator_code}"
    params = {
        "date": f"{year_start}:{year_end}",
        "format": "json",
        "per_page": 10000,
    }

    resp = httpx.get(url, params=params)
    resp.raise_for_status()
    data = resp.json()

    if len(data) < 2 or data[1] is None:
        return []

    # Guard against silent pagination truncation
    if data[0]["pages"] > 1:
        raise RuntimeError(
            f"Response has {data[0]['pages']} pages — increase per_page or paginate"
        )

    results = []
    for record in data[1]:
        if record["value"] is not None:
            results.append({
                "country_code": record["countryiso3code"],
                "year": int(record["date"]),
                "value": record["value"],
            })

    return results
