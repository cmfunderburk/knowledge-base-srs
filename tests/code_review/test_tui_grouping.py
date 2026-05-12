from knowledge_base.code_review.tui import category_of, group_by_category


def test_category_of_nested():
    assert category_of({"path": "quantecon/python-programming/quantecon-3-1"}) == (
        "quantecon/python-programming"
    )


def test_category_of_root_level():
    assert category_of({"path": "flat-ex"}) == ""


def test_category_of_empty_path_falls_back_to_root():
    assert category_of({"path": ""}) == ""


def test_group_by_category_orders_alphabetically_root_first():
    exercises = [
        {"path": "quantecon/intermediate/foo", "slug": "foo"},
        {"path": "quantecon/python-programming/bar", "slug": "bar"},
        {"path": "quantecon/python-programming/aaa", "slug": "aaa"},
        {"path": "loose", "slug": "loose"},
    ]
    grouped = group_by_category(exercises)
    assert [cat for cat, _ in grouped] == [
        "",
        "quantecon/intermediate",
        "quantecon/python-programming",
    ]
    aaa_bar = [e["slug"] for e in grouped[2][1]]
    assert aaa_bar == ["aaa", "bar"]  # slug-sorted within group
