from knowledge_base.config import DECKS, ENTITIES, REGIONS


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
            assert "wb_code" in ind or ind["id"] == "city_population"


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
    assert len(DECKS["development"]["indicators"]) == 14


def test_tech_adoption_deck_exists():
    assert "tech_adoption" in DECKS
    assert len(DECKS["tech_adoption"]["indicators"]) == 6
    eras = DECKS["tech_adoption"]["era_ranges"]
    assert "1990" in eras
    assert "2000" in eras
    assert "2010" in eras
    assert "current" in eras
