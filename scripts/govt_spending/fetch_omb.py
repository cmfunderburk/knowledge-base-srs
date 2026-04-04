"""Download OMB Historical Table 4.1 (Outlays by Agency).

Output: data/govt_spending/raw/hist04z1.xlsx
"""

from __future__ import annotations

from pathlib import Path

import requests

OMB_URL = "https://www.whitehouse.gov/wp-content/uploads/2026/04/hist04z1_fy2027.xlsx"

OUTPUT_DIR = Path("data/govt_spending/raw")


def fetch_omb() -> Path:
    """Download OMB Table 4.1 Excel file."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Downloading OMB Table 4.1...")
    resp = requests.get(OMB_URL)
    resp.raise_for_status()

    out_path = OUTPUT_DIR / "hist04z1.xlsx"
    out_path.write_bytes(resp.content)
    print(f"Wrote {out_path} ({len(resp.content)} bytes)")
    return out_path


if __name__ == "__main__":
    fetch_omb()
