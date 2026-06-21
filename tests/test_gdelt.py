"""Offline unit tests for the GDELT pure helpers (no network)."""

from __future__ import annotations

import pandas as pd

from bdor.data.gdelt import _build_query, _is_name_variant, _parse_timeline


def test_build_query_name_only():
    assert _build_query("Lionel Messi", []) == '"Lionel Messi"'


def test_build_query_ors_name_variant_aliases_only():
    # "Leo Messi" shares surname -> included; "La Pulga" doesn't -> excluded.
    q = _build_query("Lionel Messi", ["Leo Messi", "La Pulga"])
    assert q == '("Lionel Messi" OR "Leo Messi")'


def test_build_query_caps_aliases():
    aliases = ["Leo Messi", "Lio Messi", "Lionel Andres Messi", "Messi Cuccittini"]
    q = _build_query("Lionel Messi", aliases)
    # name + up to _MAX_ALIASES (3) variants
    assert q.count(" OR ") <= 3


def test_is_name_variant():
    assert _is_name_variant("Son Heung-min", "Heung-min Son")   # reorder, shares 'son'
    assert not _is_name_variant("La Pulga", "Lionel Messi")     # no shared surname
    assert not _is_name_variant("Leo", "Lionel Messi")          # single word


def test_parse_timeline_reads_data():
    payload = {
        "timeline": [
            {
                "series": "Volume Intensity",
                "data": [
                    {"date": "20221217T000000Z", "value": 1.04},
                    {"date": "20221218T000000Z", "value": 2.98},
                ],
            }
        ]
    }
    df = _parse_timeline(payload)
    assert list(df.columns) == ["date", "volume"]
    assert df["volume"].tolist() == [1.04, 2.98]
    assert df["date"].tolist() == [pd.Timestamp("2022-12-17"), pd.Timestamp("2022-12-18")]


def test_parse_timeline_empty():
    assert _parse_timeline({}).empty                       # no matches -> {}
    assert _parse_timeline({"timeline": []}).empty
    assert list(_parse_timeline({}).columns) == ["date", "volume"]
