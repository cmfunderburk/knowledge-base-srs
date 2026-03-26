import polars as pl
import pytest
from knowledge_base.desc_stats import compute_desc_stats


def test_compute_desc_stats_basic():
    df = pl.DataFrame({
        "entity": ["A", "B", "C", "D", "E"],
        "value": [10.0, 20.0, 30.0, 40.0, 50.0],
    })
    stats = compute_desc_stats(df)
    assert stats["n"] == 5
    assert stats["mean"] == pytest.approx(30.0)
    assert stats["median"] == pytest.approx(30.0)
    assert stats["std"] == pytest.approx(14.1421, rel=1e-3)
    assert stats["min_value"] == pytest.approx(10.0)
    assert stats["min_entity"] == "A"
    assert stats["max_value"] == pytest.approx(50.0)
    assert stats["max_entity"] == "E"


def test_compute_desc_stats_single_row():
    df = pl.DataFrame({
        "entity": ["A"],
        "value": [42.0],
    })
    stats = compute_desc_stats(df)
    assert stats["n"] == 1
    assert stats["mean"] == pytest.approx(42.0)
    assert stats["median"] == pytest.approx(42.0)
    assert stats["std"] == pytest.approx(0.0)
    assert stats["min_entity"] == "A"
    assert stats["max_entity"] == "A"


def test_compute_desc_stats_two_rows():
    df = pl.DataFrame({
        "entity": ["A", "B"],
        "value": [100.0, 200.0],
    })
    stats = compute_desc_stats(df)
    assert stats["n"] == 2
    assert stats["mean"] == pytest.approx(150.0)
    assert stats["median"] == pytest.approx(150.0)
    assert stats["min_value"] == pytest.approx(100.0)
    assert stats["max_value"] == pytest.approx(200.0)
