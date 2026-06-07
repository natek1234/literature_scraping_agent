"""Unit tests for query_builder.py — no external API calls."""

from __future__ import annotations

import pytest

from sourcing_agent.config import Config
from sourcing_agent.pipeline.query_builder import (
    _build_natural_query,
    build_supplementary_queries,
)


@pytest.fixture(scope="module")
def config() -> Config:
    return Config.from_file("CONTEXT.md")


# ── _build_natural_query ──────────────────────────────────────────────────────


class TestBuildNaturalQuery:
    def test_s2_joins_up_to_six_terms(self) -> None:
        terms = ["a b", "c d", "e f", "g h", "i j", "k l", "m n"]
        result = _build_natural_query("Semantic Scholar", terms)
        assert result == "a b c d e f g h i j k l"  # first 6 joined

    def test_arxiv_joins_up_to_six_terms(self) -> None:
        terms = ["foo", "bar", "baz"]
        result = _build_natural_query("arXiv", terms)
        assert result == "foo bar baz"

    def test_ntrs_uses_only_first_term(self) -> None:
        terms = [
            "Apollo guidance computer",
            "Viking lander autonomy",
            "Voyager spacecraft automation",
        ]
        result = _build_natural_query("NASA Technical Reports Server", terms)
        assert result == "Apollo guidance computer"

    def test_ntrs_caps_at_four_words(self) -> None:
        terms = ["one two three four five six seven"]
        result = _build_natural_query("NASA Technical Reports Server", terms)
        assert result == "one two three four"

    def test_ntrs_empty_cluster(self) -> None:
        result = _build_natural_query("NASA Technical Reports Server", [])
        assert result == ""

    def test_ntrs_single_word_term(self) -> None:
        result = _build_natural_query("NASA Technical Reports Server", ["robotics"])
        assert result == "robotics"


# ── build_supplementary_queries ───────────────────────────────────────────────


class TestBuildSupplementaryQueries:
    def test_parent_section_returns_empty(self, config: Config) -> None:
        assert build_supplementary_queries("S4:ai-in-robotics", config) == {}
        assert build_supplementary_queries("S5:new-paradigms", config) == {}

    def test_unknown_section_returns_empty(self, config: Config) -> None:
        result = build_supplementary_queries("S99:nonexistent", config)
        assert result == {}

    def test_s2_history_maps_to_multiple_clusters(self, config: Config) -> None:
        result = build_supplementary_queries("S2:history", config)
        s2_queries = result.get("Semantic Scholar", [])
        # S2:history maps to 4 clusters → 4 queries for Semantic Scholar
        assert len(s2_queries) == 4

    def test_s4g_alignment_maps_to_six_clusters(self, config: Config) -> None:
        result = build_supplementary_queries("S4g:alignment", config)
        s2_queries = result.get("Semantic Scholar", [])
        assert len(s2_queries) == 6

    def test_ntrs_queries_are_short(self, config: Config) -> None:
        result = build_supplementary_queries("S2:history", config)
        ntrs_queries = result.get("NASA Technical Reports Server", [])
        for q in ntrs_queries:
            words = q.split()
            assert len(words) <= 4, f"NTRS query too long ({len(words)} words): {q!r}"

    def test_single_cluster_section(self, config: Config) -> None:
        result = build_supplementary_queries("S4a:navigation", config)
        s2_queries = result.get("Semantic Scholar", [])
        assert len(s2_queries) == 1

    def test_result_contains_enabled_databases(self, config: Config) -> None:
        result = build_supplementary_queries("S4f:learning", config)
        assert "Semantic Scholar" in result
        assert "arXiv" in result
