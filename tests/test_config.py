from knowledge_base.config import DECKS, ENTITIES, REGIONS, URBAN_ENTITIES


def test_all_entities_have_required_fields():
    for e in ENTITIES:
        assert "name" in e
        assert "entity_type" in e, f"{e['name']} missing entity_type"
        assert e["entity_type"] in ("region", "major", "long_tail")
        if e["entity_type"] != "region":
            assert "region" in e, f"{e['name']} missing region"
            assert "iso3" in e, f"{e['name']} missing iso3"
        else:
            assert "wb_code" in e, f"{e['name']} missing wb_code"


def test_all_decks_have_required_fields():
    for key, deck in DECKS.items():
        assert "name" in deck, f"deck {key} missing name"
        assert "deck_id" in deck, f"deck {key} missing deck_id"
        assert "output" in deck, f"deck {key} missing output"
        assert "data_dir" in deck, f"deck {key} missing data_dir"
        assert "era_ranges" in deck, f"deck {key} missing era_ranges"
        assert "indicators" in deck, f"deck {key} missing indicators"


def test_all_indicators_have_required_fields():
    for key, deck in DECKS.items():
        for ind in deck["indicators"]:
            assert "id" in ind, f"deck {key}: indicator missing id"
            assert "name" in ind, f"deck {key}: {ind.get('id')} missing name"
            assert "category" in ind
            assert "unit_label" in ind
            assert "decimals" in ind, f"deck {key}: {ind['id']} missing decimals"
            assert "unit_prefix" in ind, f"deck {key}: {ind['id']} missing unit_prefix"
            if key != "urban_areas":
                assert "wb_code" in ind


def test_region_names_consistent():
    region_names = {e["name"] for e in ENTITIES if e["entity_type"] == "region"}
    for e in ENTITIES:
        if e["entity_type"] != "region" and "region" in e:
            assert e["region"] in region_names, (
                f"{e['name']}'s region '{e['region']}' not in regions"
            )


def test_entity_count():
    assert 45 <= len(ENTITIES) <= 55


def test_era_ranges_format():
    for key, deck in DECKS.items():
        for era, rng in deck["era_ranges"].items():
            assert len(rng) == 3, f"deck {key} era {era}: expected 3-tuple"
            assert rng[0] <= rng[2] <= rng[1]


def test_development_deck_exists():
    assert "development" in DECKS
    assert len(DECKS["development"]["indicators"]) == 13


def test_tech_adoption_deck_exists():
    assert "tech_adoption" in DECKS
    assert len(DECKS["tech_adoption"]["indicators"]) == 6
    eras = DECKS["tech_adoption"]["era_ranges"]
    assert "1990" in eras
    assert "2000" in eras
    assert "2010" in eras
    assert "current" in eras


def test_finance_deck_exists():
    assert "finance" in DECKS
    deck = DECKS["finance"]
    assert len(deck["indicators"]) == 8
    eras = deck["era_ranges"]
    assert "1960" in eras
    assert "1990" in eras
    assert "current" in eras
    # Verify scale_factor on absolute-value indicators
    indicators_by_id = {i["id"]: i for i in deck["indicators"]}
    assert indicators_by_id["reserves"]["scale_factor"] == 1_000_000_000
    assert indicators_by_id["remittances"]["scale_factor"] == 1_000_000_000
    # Verify categories
    categories = {i["category"] for i in deck["indicators"]}
    assert categories == {"macro", "financial_system"}


def test_conflict_security_deck_exists():
    assert "conflict_security" in DECKS
    deck = DECKS["conflict_security"]
    assert len(deck["indicators"]) == 7
    eras = deck["era_ranges"]
    assert "1960" in eras
    assert "1990" in eras
    assert "current" in eras
    # Verify scale_factor on indicators that need it
    indicators_by_id = {i["id"]: i for i in deck["indicators"]}
    assert indicators_by_id["mil_expenditure_usd"]["scale_factor"] == 1_000_000_000
    assert indicators_by_id["armed_forces"]["scale_factor"] == 1_000
    assert indicators_by_id["arms_imports"]["scale_factor"] == 1_000_000
    assert indicators_by_id["refugees_origin"]["scale_factor"] == 1_000
    assert indicators_by_id["refugees_asylum"]["scale_factor"] == 1_000


def test_urban_entities_have_required_fields():
    for e in URBAN_ENTITIES:
        if e["entity_type"] == "city":
            assert "uc_id" in e, f"{e['name']} missing uc_id"
            assert "name" in e, f"entity missing name"
            assert "country" in e, f"{e['name']} missing country"
            assert "income_group" in e, f"{e['name']} missing income_group"
            assert "tag_slug" in e, f"{e['name']} missing tag_slug"
            assert "entity_type" in e
        elif e["entity_type"] == "aggregate":
            assert "name" in e
            assert "tag_slug" in e


def test_urban_entities_count():
    cities = [e for e in URBAN_ENTITIES if e["entity_type"] == "city"]
    aggregates = [e for e in URBAN_ENTITIES if e["entity_type"] == "aggregate"]
    assert len(cities) == 50
    assert len(aggregates) >= 4


def test_urban_deck_exists():
    assert "urban_areas" in DECKS
    deck = DECKS["urban_areas"]
    assert deck["name"] == "Knowledge Base::Urban Areas"
    assert len(deck["indicators"]) == 6
    assert "entities" in deck
    assert deck["reference_entity"] == "All Cities"
    assert deck["reference_entity_type"] == "aggregate"


def test_urban_deck_eras():
    eras = DECKS["urban_areas"]["era_ranges"]
    assert set(eras.keys()) == {"1990", "2000", "2010", "2020", "2025"}
    for era, rng in eras.items():
        year = int(era)
        assert rng == (year, year, year)


def test_urban_indicators_have_ghsl_fields():
    for ind in DECKS["urban_areas"]["indicators"]:
        assert "ghsl_table" in ind, f"{ind['id']} missing ghsl_table"
        assert "ghsl_column" in ind, f"{ind['id']} missing ghsl_column"
        assert "years" in ind, f"{ind['id']} missing years"
        assert "id" in ind
        assert "name" in ind
        assert "category" in ind
        assert "unit_label" in ind
        assert "decimals" in ind
        assert "unit_prefix" in ind


def test_urban_indicators_no_wb_code():
    for ind in DECKS["urban_areas"]["indicators"]:
        assert "wb_code" not in ind
