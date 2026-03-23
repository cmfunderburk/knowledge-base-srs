import json
import httpx
import pytest
from unittest.mock import patch, Mock
from knowledge_base.wb_api import fetch_indicator


# Sample World Bank API response shape
SAMPLE_WB_RESPONSE = [
    {"page": 1, "pages": 1, "per_page": 50, "total": 2},
    [
        {
            "indicator": {"id": "SP.POP.TOTL", "value": "Population, total"},
            "country": {"id": "IN", "value": "India"},
            "countryiso3code": "IND",
            "date": "1990",
            "value": 873277798,
        },
        {
            "indicator": {"id": "SP.POP.TOTL", "value": "Population, total"},
            "country": {"id": "IN", "value": "India"},
            "countryiso3code": "IND",
            "date": "1960",
            "value": 450547679,
        },
    ],
]


def _mock_response(data, status_code=200):
    """Create a properly constructed httpx.Response with JSON body."""
    response = httpx.Response(
        status_code,
        content=json.dumps(data).encode(),
        headers={"content-type": "application/json"},
    )
    # Attach a mock request to allow raise_for_status to work
    response._request = Mock()
    return response


def test_fetch_indicator_parses_response():
    with patch("knowledge_base.wb_api.httpx.get", return_value=_mock_response(SAMPLE_WB_RESPONSE)):
        results = fetch_indicator("SP.POP.TOTL", ["IND"], 1955, 1995)

    assert len(results) == 2
    assert results[0]["country_code"] == "IND"
    assert results[0]["year"] == 1990
    assert results[0]["value"] == 873277798


def test_fetch_indicator_skips_null_values():
    response_with_null = [
        {"page": 1, "pages": 1, "per_page": 50, "total": 2},
        [
            {
                "indicator": {"id": "SI.POV.GINI"},
                "country": {"id": "IN", "value": "India"},
                "countryiso3code": "IND",
                "date": "2020",
                "value": None,
            },
            {
                "indicator": {"id": "SI.POV.GINI"},
                "country": {"id": "IN", "value": "India"},
                "countryiso3code": "IND",
                "date": "2019",
                "value": 35.7,
            },
        ],
    ]
    with patch("knowledge_base.wb_api.httpx.get", return_value=_mock_response(response_with_null)):
        results = fetch_indicator("SI.POV.GINI", ["IND"], 2015, 2025)

    assert len(results) == 1
    assert results[0]["value"] == 35.7


def test_fetch_indicator_handles_empty_response():
    empty_response = [
        {"page": 1, "pages": 1, "per_page": 50, "total": 0},
        None,
    ]
    with patch("knowledge_base.wb_api.httpx.get", return_value=_mock_response(empty_response)):
        results = fetch_indicator("SP.POP.TOTL", ["IND"], 1950, 1950)

    assert results == []
