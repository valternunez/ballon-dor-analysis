"""Offline unit tests for the GDELT-BigQuery pure helpers (no network / no BigQuery)."""

from __future__ import annotations

from bdor.data.gdelt_bq import _build_sql, _fold, _name_pairs, _sql_literal


def test_fold_strips_accents_lowercases_and_collapses_space():
    assert _fold("Kylian Mbappé") == "kylian mbappe"
    assert _fold("  Rúben  Dias ") == "ruben dias"
    assert _fold("N'Golo Kanté") == "n'golo kante"


def test_name_pairs_includes_full_name_and_surname_variant():
    # name-order alias "Lewandowski Robert" (shares surname) is kept; a non-surname-sharing alias is
    # dropped (matches gdelt._is_name_variant's surname-substring rule).
    pairs = _name_pairs({"Robert Lewandowski": ["Lewandowski Robert", "Lewy The Goat"]})
    forms = {f for f, _ in pairs}
    players = {p for _, p in pairs}
    assert "robert lewandowski" in forms
    assert "lewandowski robert" in forms     # surname-sharing variant kept
    assert "lewy the goat" not in forms      # no shared surname -> dropped
    assert players == {"Robert Lewandowski"}


def test_name_pairs_dedupes_and_drops_empty():
    pairs = _name_pairs({"Pelé": ["Pelé", "Pele"]})  # all fold to the same "pele"
    assert pairs == [("pele", "Pelé")]


def test_sql_literal_escapes_quotes():
    assert _sql_literal("O'Neil") == "'O\\'Neil'"


def test_build_sql_has_partition_filter_and_names_and_table():
    sql = _build_sql([("lionel messi", "Lionel Messi")], start="2017-01-01", end="2026-01-01")
    assert "gdelt-bq.gdeltv2.gkg_partitioned" in sql
    assert "STRUCT('lionel messi' AS form, 'Lionel Messi' AS player)" in sql
    assert "_PARTITIONTIME >= '2017-01-01'" in sql and "_PARTITIONTIME < '2026-01-01'" in sql
    assert "SPLIT(g.V2Persons" in sql and "GROUP BY player, date" in sql
    # accent-folding on the GKG side mirrors _fold (NORMALIZE NFD + strip combining marks)
    assert "NORMALIZE(LOWER(TRIM(SPLIT(person_raw" in sql
