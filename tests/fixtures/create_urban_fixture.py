"""One-shot script to create the test GeoPackage fixture."""
import sqlite3
from pathlib import Path

BOM = "\ufeff"
FIXTURE_PATH = Path(__file__).parent / "sample_urban.gpkg"


def create():
    con = sqlite3.connect(FIXTURE_PATH)

    # GHSL table (population, built-up per capita)
    con.execute(f'''CREATE TABLE GHS_UCDB_THEME_GHSL_GLOBE_R2024A (
        fid INTEGER PRIMARY KEY,
        "{BOM}ID_UC_G0" INTEGER,
        "{BOM}GH_POP_TOT_2020" REAL,
        "{BOM}GH_POP_TOT_2025" REAL,
        "{BOM}GH_BPC_TOT_2020" REAL,
        "{BOM}GH_BPC_TOT_2025" REAL
    )''')
    con.executemany(
        f'''INSERT INTO GHS_UCDB_THEME_GHSL_GLOBE_R2024A
            (fid, "{BOM}ID_UC_G0", "{BOM}GH_POP_TOT_2020", "{BOM}GH_POP_TOT_2025",
             "{BOM}GH_BPC_TOT_2020", "{BOM}GH_BPC_TOT_2025")
            VALUES (?, ?, ?, ?, ?, ?)''',
        [
            (1, 100, 10_000_000, 11_000_000, 50.0, 48.0),
            (2, 200, 5_000_000, 5_500_000, 30.0, 28.0),
            (3, 300, 2_000_000, 2_200_000, 80.0, 75.0),
        ],
    )

    # EMISSIONS table (CO2 per capita, PM2.5)
    con.execute(f'''CREATE TABLE GHS_UCDB_THEME_EMISSIONS_GLOBE_R2024A (
        fid INTEGER PRIMARY KEY,
        "{BOM}ID_UC_G0" INTEGER,
        "{BOM}EM_CO2_PEC_2020" REAL,
        "{BOM}EM_PM2_CON_2020" REAL
    )''')
    con.executemany(
        f'''INSERT INTO GHS_UCDB_THEME_EMISSIONS_GLOBE_R2024A
            (fid, "{BOM}ID_UC_G0", "{BOM}EM_CO2_PEC_2020", "{BOM}EM_PM2_CON_2020")
            VALUES (?, ?, ?, ?)''',
        [
            (1, 100, 5.5, 25.0),
            (2, 200, 2.0, 45.0),
            (3, 300, 8.0, 10.0),
        ],
    )

    # SOCIOECONOMIC table (life expectancy, HDI)
    con.execute(f'''CREATE TABLE GHS_UCDB_THEME_SOCIOECONOMIC_GLOBE_R2024A (
        fid INTEGER PRIMARY KEY,
        "{BOM}ID_UC_G0" INTEGER,
        "{BOM}SC_SEC_LET_2020" REAL,
        "{BOM}SC_SEC_HDI_2020" REAL
    )''')
    con.executemany(
        f'''INSERT INTO GHS_UCDB_THEME_SOCIOECONOMIC_GLOBE_R2024A
            (fid, "{BOM}ID_UC_G0", "{BOM}SC_SEC_LET_2020", "{BOM}SC_SEC_HDI_2020")
            VALUES (?, ?, ?, ?)''',
        [
            (1, 100, 78.5, 0.900),
            (2, 200, 72.0, 0.700),
            (3, 300, None, None),  # Missing data (like Taipei)
        ],
    )

    con.commit()
    con.close()
    print(f"Created {FIXTURE_PATH}")


if __name__ == "__main__":
    create()
