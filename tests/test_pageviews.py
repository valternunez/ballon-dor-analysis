"""Offline unit tests for the pageviews pure helpers (no network)."""

from __future__ import annotations

import pandas as pd

from bdor.data.pageviews import _aggregate_all_lang, _encode_title


def test_encode_title_spaces_and_accents():
    assert _encode_title("Lionel Messi") == "Lionel_Messi"
    assert _encode_title("Kylian Mbappé") == "Kylian_Mbapp%C3%A9"
    assert _encode_title("AC/DC") == "AC%2FDC"  # slash must be encoded


def test_aggregate_all_lang_sums_across_languages():
    per_lang = pd.DataFrame(
        {
            "player": ["Messi", "Messi", "Messi", "Messi"],
            "lang": ["en", "es", "en", "es"],
            "date": pd.to_datetime(["2022-12-03", "2022-12-03", "2022-12-04", "2022-12-04"]),
            "views": [380000, 200000, 217000, 150000],
        }
    )
    out = _aggregate_all_lang(per_lang)
    assert list(out.columns) == ["player", "date", "views"]
    assert len(out) == 2  # two distinct dates
    d3 = out[out.date == pd.Timestamp("2022-12-03")]["views"].iloc[0]
    assert d3 == 580000  # en + es summed


def test_aggregate_all_lang_empty():
    out = _aggregate_all_lang(pd.DataFrame(columns=["player", "lang", "date", "views"]))
    assert out.empty
    assert list(out.columns) == ["player", "date", "views"]
