"""End-to-end: fixture CSVs → .apkg file."""
from pathlib import Path

from knowledge_base.build_deck import _run

FIXTURES = Path(__file__).parent / "fixtures"


def test_build_deck_from_fixtures(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    for fixture_name, csv_name in [
        ("sample_gdp.csv", "gdp_pc_ppp.csv"),
    ]:
        src = FIXTURES / fixture_name
        if src.exists():
            (data_dir / csv_name).write_text(src.read_text())

    output_path = tmp_path / "test_deck.apkg"

    _run("development", data_dir=data_dir, output_path=output_path)

    assert output_path.exists()
    assert output_path.stat().st_size > 0


def test_build_urban_deck_from_fixtures(tmp_path):
    """End-to-end: fixture CSV → .apkg for urban areas deck."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    csv_content = (
        "entity,entity_type,region,era,year,value,source\n"
        "All Cities,aggregate,,2020,2020,15000000,GHS-UCDB R2024A\n"
        "High income,aggregate,,2020,2020,20000000,GHS-UCDB R2024A\n"
        "Tokyo,city,High income,2020,2020,33000000,GHS-UCDB R2024A\n"
        "Jakarta,city,Upper Middle,2020,2020,38000000,GHS-UCDB R2024A\n"
    )
    (data_dir / "population.csv").write_text(csv_content)

    output_path = tmp_path / "test_urban.apkg"

    _run("urban_areas", data_dir=data_dir, output_path=output_path)

    assert output_path.exists()
    assert output_path.stat().st_size > 0
