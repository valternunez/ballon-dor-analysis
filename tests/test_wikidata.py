"""Offline unit tests for the Wikidata resolver pure helpers (no network)."""

from __future__ import annotations

from bdor.data.wikidata import (
    _extract_rows,
    _is_language_wiki,
    _pick_footballer,
    _wiki_to_lang,
)

_FOOTBALLER = "Q937857"


def test_language_wiki_filter():
    assert _is_language_wiki("enwiki")
    assert _is_language_wiki("eswiki")
    assert _is_language_wiki("be-x-oldwiki")
    assert not _is_language_wiki("commonswiki")   # non-language wiki
    assert not _is_language_wiki("enwikiquote")   # not a Wikipedia
    assert not _is_language_wiki("metawiki")


def test_wiki_to_lang():
    assert _wiki_to_lang("enwiki") == "en"
    assert _wiki_to_lang("simplewiki") == "simple"


def test_pick_footballer_prefers_p106_over_book_and_trial():
    # Order mirrors a real search: footballer, then a book, then a trial.
    entities = {
        "Q615": {"claims": {"P106": [{"mainsnak": {"datavalue": {"value": {"id": _FOOTBALLER}}}}]},
                 "sitelinks": {f"{i}wiki": {} for i in range(60)}},
        "Q122": {"claims": {}, "sitelinks": {"enwiki": {}}},
        "Q414": {"claims": {}, "sitelinks": {"enwiki": {}}},
    }
    order = ["Q615", "Q122", "Q414"]
    descs = {"Q615": "Argentine footballer", "Q122": "book", "Q414": "trial"}
    assert _pick_footballer(entities, order, descs) == "Q615"


def test_pick_footballer_falls_back_to_description():
    entities = {  # no P106 anywhere
        "Q1": {"claims": {}, "sitelinks": {"enwiki": {}}},
        "Q2": {"claims": {}, "sitelinks": {"enwiki": {}}},
    }
    order = ["Q1", "Q2"]
    descs = {"Q1": "book edition", "Q2": "Brazilian association football player"}
    assert _pick_footballer(entities, order, descs) == "Q2"


def test_pick_footballer_returns_none_when_no_match():
    entities = {"Q1": {"claims": {}, "sitelinks": {}}}
    assert _pick_footballer(entities, ["Q1"], {"Q1": "a book"}) is None


def test_extract_rows_emits_sitelinks_and_aliases():
    entity = {
        "sitelinks": {
            "enwiki": {"title": "Lionel Messi"},
            "eswiki": {"title": "Lionel Messi"},
            "commonswiki": {"title": "Category:Lionel Messi"},  # dropped
        },
        "aliases": {"en": [{"value": "Leo Messi"}], "es": [{"value": "La Pulga"}]},
    }
    df = _extract_rows("Lionel Messi", "Q615", entity)
    sitelinks = df[df.kind == "sitelink"]
    aliases = df[df.kind == "alias"]
    assert set(sitelinks.key) == {"en", "es"}          # commonswiki filtered out
    assert set(aliases.value) == {"Leo Messi", "La Pulga"}
    assert (df["qid"] == "Q615").all()
