"""End-to-end: fixture CSVs → .apkg file."""
from pathlib import Path

from knowledge_base.build_deck import _run

FIXTURES = Path(__file__).parent / "fixtures"


def test_build_deck_from_fixtures(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    for fixture_name, csv_name in [
        ("sample_gdp.csv", "gdp_pc_ppp.csv"),
        ("sample_city_population.csv", "city_population.csv"),
    ]:
        src = FIXTURES / fixture_name
        if src.exists():
            (data_dir / csv_name).write_text(src.read_text())

    output_path = tmp_path / "test_deck.apkg"

    _run("development", data_dir=data_dir, output_path=output_path)

    assert output_path.exists()
    assert output_path.stat().st_size > 0
