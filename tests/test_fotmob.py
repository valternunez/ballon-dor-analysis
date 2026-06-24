"""Offline unit tests for the FotMob rating helpers (no network)."""

from __future__ import annotations

from bdor.data.fotmob import _aggregate_seasons, _season_entries


def _nextdata(entries):
    return {"props": {"pageProps": {"data": {"careerHistory": {"careerItems": {
        "senior": {"seasonEntries": entries}}}}}}}


def test_season_entries_extracts_senior_list():
    nd = _nextdata([{"seasonName": "2020/2021", "rating": {"rating": "7.05"}, "appearances": "50"}])
    out = _season_entries(nd)
    assert len(out) == 1 and out[0]["seasonName"] == "2020/2021"
    assert _season_entries({}) == []  # missing structure -> empty, no crash


def test_aggregate_weights_duplicate_seasons_by_appearances():
    # A mid-season transfer: same season, two rows -> appearance-weighted mean.
    entries = [
        {"seasonName": "2017/2018", "rating": {"rating": "7.00"}, "appearances": "10"},
        {"seasonName": "2017/2018", "rating": {"rating": "8.00"}, "appearances": "30"},
    ]
    out = _aggregate_seasons(entries, "Test Player")
    assert len(out) == 1
    row = out.iloc[0]
    assert row["season"] == "2017/2018"
    assert abs(row["fotmob_rating"] - 7.75) < 1e-9  # (7*10 + 8*30)/40
    assert row["apps"] == 40
    assert row["player"] == "Test Player"


def test_aggregate_drops_ratingless_and_non_domestic_seasons():
    entries = [
        {"seasonName": "2019/2020", "rating": {"rating": "6.88"}, "appearances": "49"},
        {"seasonName": "2016/2017", "rating": {"rating": None}, "appearances": "28"},  # no rating
        {"seasonName": "2026", "rating": {"rating": "7.5"}, "appearances": "5"},  # natl team
    ]
    out = _aggregate_seasons(entries, "P")
    assert list(out["season"]) == ["2019/2020"]


def test_aggregate_empty_is_empty_frame():
    out = _aggregate_seasons([], "P")
    assert out.empty and list(out.columns) == ["player", "season", "fotmob_rating", "apps"]
