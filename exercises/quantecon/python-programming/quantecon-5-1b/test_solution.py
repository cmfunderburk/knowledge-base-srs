import sys

import pytest


@pytest.fixture
def sub():
    sys.modules.pop("submission", None)
    import submission as s
    yield s
    sys.modules.pop("submission", None)


def test_count_evens_exists(sub):
    assert hasattr(sub, "count_evens")
    assert callable(sub.count_evens)


def test_count_evens_value(sub):
    assert sub.count_evens() == 50
