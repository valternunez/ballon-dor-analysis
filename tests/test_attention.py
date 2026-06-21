"""Offline unit tests for the pool universe dedup (no network)."""

from __future__ import annotations

from bdor.features.pool import _dedupe_universe


def test_dedupe_prefers_finisher_spelling_and_dedupes_by_key():
    finishers = ["Kylian Mbappé", "Luka Modrić"]
    pool = ["Kylian Mbappe-Lottin", "Luka Modric", "Florian Wirtz"]  # first two = same players
    out = _dedupe_universe(finishers, pool)
    # the finisher (awards) spelling wins; the Understat variants are folded away
    assert "Kylian Mbappé" in out
    assert "Kylian Mbappe-Lottin" not in out
    assert "Luka Modrić" in out
    assert "Luka Modric" not in out
    # a pool-only player keeps its (Understat) spelling
    assert "Florian Wirtz" in out
    assert len(out) == 3


def test_dedupe_is_sorted_and_unique():
    out = _dedupe_universe(["B Player", "A Player"], ["A Player", "C Player"])
    assert out == sorted(out)
    assert len(out) == len(set(out))
