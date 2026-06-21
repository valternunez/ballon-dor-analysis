"""Tests for the cache-first helpers — the most important piece of the scaffold."""

from __future__ import annotations

import pandas as pd

from bdor.cache import cached_frame, cached_records


def test_cached_frame_computes_once_then_serves_from_disk(tmp_path):
    calls = {"n": 0}

    def producer() -> pd.DataFrame:
        calls["n"] += 1
        return pd.DataFrame({"x": [1, 2, 3]})

    first = cached_frame("demo", producer, root=tmp_path)
    second = cached_frame("demo", producer, root=tmp_path)

    assert calls["n"] == 1  # producer NOT re-invoked on the second call
    assert (tmp_path / "demo.parquet").exists()
    pd.testing.assert_frame_equal(first, second)


def test_cached_frame_refresh_recomputes(tmp_path):
    calls = {"n": 0}

    def producer() -> pd.DataFrame:
        calls["n"] += 1
        return pd.DataFrame({"x": [calls["n"]]})

    cached_frame("demo", producer, root=tmp_path)
    cached_frame("demo", producer, root=tmp_path, refresh=True)

    assert calls["n"] == 2


def test_cached_records_is_resumable(tmp_path):
    fetched: list[str] = []

    def fetch_one(key: str) -> pd.DataFrame:
        fetched.append(key)
        return pd.DataFrame({"key": [key], "val": [len(key)]})

    # First pass: a + b.
    cached_records("rec", ["a", "b"], fetch_one, root=tmp_path, progress=False)
    assert fetched == ["a", "b"]

    # Second pass adds c; a + b are served from shards, only c is fetched.
    out = cached_records("rec", ["a", "b", "c"], fetch_one, root=tmp_path, progress=False)
    assert fetched == ["a", "b", "c"]
    assert sorted(out["key"]) == ["a", "b", "c"]
    assert len(out) == 3
