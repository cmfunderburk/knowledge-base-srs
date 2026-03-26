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


def test_build_descriptive_stats_deck(tmp_path):
    """End-to-end: summary CSV → .apkg for descriptive stats deck."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    header = (
        "indicator_id,indicator_name,category,source_deck,unit_label,unit_prefix,"
        "decimals,scale_factor,year,n,mean,median,std,"
        "min_value,min_entity,max_value,max_entity\n"
    )
    (data_dir / "gdp_pc_ppp.csv").write_text(
        header
        + "gdp_pc_ppp,GDP per capita (PPP),development,development,"
        "in 2021 international dollars,$,0,1,2024,190,"
        "18463.0,13178.0,22147.0,878.0,Burundi,143314.0,Luxembourg\n"
    )
    (data_dir / "urban_population.csv").write_text(
        header
        + "urban_population,Population,demographics,urban_areas,"
        "millions,,1,1000000,2025,50,"
        "12895864.0,10500000.0,8000000.0,1200000.0,Luanda,38000000.0,Tokyo\n"
    )

    output_path = tmp_path / "test_desc_stats.apkg"

    _run("descriptive_stats", data_dir=data_dir, output_path=output_path)

    assert output_path.exists()
    assert output_path.stat().st_size > 0
