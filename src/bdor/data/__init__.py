"""Data-source pull modules.

One module per source. Each exposes a top-level ``pull()`` returning a tidy DataFrame,
wrapped in a cache helper so re-running is free. Implemented: ``awards`` (join target),
``understat`` (player-season xG performance — replaced FBref), ``wikidata`` (QID + all-language
sitelinks + aliases) and ``pageviews`` (all-language daily attention). ``gdelt`` is a stub.
"""
