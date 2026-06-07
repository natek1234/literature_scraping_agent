"""Tests for scorer.py helpers — no LLM calls, no external API."""

from __future__ import annotations

import pytest

# Import the private helpers directly for unit testing
from sourcing_agent.pipeline.scorer import (  # type: ignore[attr-defined]
    _SECTION_CANONICAL,
    _normalize_section_tag,
)


class TestNormalizeSectionTag:
    """_normalize_section_tag expands short codes to canonical form."""

    def test_null_passthrough(self) -> None:
        assert _normalize_section_tag(None) is None

    def test_null_string_passthrough(self) -> None:
        assert _normalize_section_tag("null") is None

    def test_empty_string_passthrough(self) -> None:
        assert _normalize_section_tag("") is None

    def test_already_canonical_unchanged(self) -> None:
        assert _normalize_section_tag("S4e:interaction") == "S4e:interaction"

    def test_unknown_tag_returned_as_is(self) -> None:
        # Tags not in the canonical map are returned unchanged so we don't
        # silently discard LLM output we haven't anticipated.
        assert _normalize_section_tag("S9:unknown") == "S9:unknown"

    @pytest.mark.parametrize("short, expected", list(_SECTION_CANONICAL.items()))
    def test_all_short_codes_expand(self, short: str, expected: str) -> None:
        assert _normalize_section_tag(short) == expected

    def test_s4a(self) -> None:
        assert _normalize_section_tag("S4a") == "S4a:navigation"

    def test_s4b(self) -> None:
        assert _normalize_section_tag("S4b") == "S4b:perception"

    def test_s4c(self) -> None:
        assert _normalize_section_tag("S4c") == "S4c:reasoning"

    def test_s4d(self) -> None:
        assert _normalize_section_tag("S4d") == "S4d:planning"

    def test_s4e(self) -> None:
        assert _normalize_section_tag("S4e") == "S4e:interaction"

    def test_s4f(self) -> None:
        assert _normalize_section_tag("S4f") == "S4f:learning"

    def test_s4g(self) -> None:
        assert _normalize_section_tag("S4g") == "S4g:alignment"

    def test_s2(self) -> None:
        assert _normalize_section_tag("S2") == "S2:history"

    def test_s3(self) -> None:
        assert _normalize_section_tag("S3") == "S3:ai-in-space"
