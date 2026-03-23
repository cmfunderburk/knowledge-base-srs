from knowledge_base.config import ENTITIES, INDICATORS, REGIONS, ERA_RANGES


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


def test_all_indicators_have_required_fields():
    for ind in INDICATORS:
        assert "id" in ind
        assert "name" in ind
        assert "category" in ind
        assert "unit_label" in ind
        assert "wb_code" in ind or ind["id"] == "city_population"


def test_region_names_consistent():
    """Every non-region entity's region field must match a region entity name."""
    region_names = {e["name"] for e in ENTITIES if e["entity_type"] == "region"}
    for e in ENTITIES:
        if e["entity_type"] != "region" and "region" in e:
            assert e["region"] in region_names, (
                f"{e['name']}'s region '{e['region']}' not in regions"
            )


def test_entity_count():
    """Sanity check: ~47 entities as designed."""
    assert 45 <= len(ENTITIES) <= 55


def test_era_ranges():
    assert "1960" in ERA_RANGES
    assert "1990" in ERA_RANGES
    assert "current" in ERA_RANGES
