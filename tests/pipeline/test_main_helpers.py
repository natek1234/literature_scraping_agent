"""Unit tests for module-level helpers in main.py."""

from __future__ import annotations

# _make_record_key lives at module level in main.py — import it directly.
from sourcing_agent.main import _make_record_key  # type: ignore[attr-defined]
from sourcing_agent.models import PaperRecord


def _record(**kwargs) -> PaperRecord:  # type: ignore[return]
    defaults = {
        "title": "Test Paper Title",
        "source_database": "Semantic Scholar",
        "retrieved_at": "2026-01-01T00:00:00",
    }
    defaults.update(kwargs)
    return PaperRecord(**defaults)


class TestMakeRecordKey:
    def test_doi_takes_priority(self) -> None:
        r = _record(doi="10.1234/test", arxiv_id="2301.00001", title="Anything")
        assert _make_record_key(r) == "doi:10.1234/test"

    def test_doi_is_lowercased(self) -> None:
        r = _record(doi="10.1234/TEST")
        assert _make_record_key(r) == "doi:10.1234/test"

    def test_doi_is_stripped(self) -> None:
        r = _record(doi="  10.1234/test  ")
        assert _make_record_key(r) == "doi:10.1234/test"

    def test_arxiv_used_when_no_doi(self) -> None:
        r = _record(doi=None, arxiv_id="2301.00001", s2_paper_id="abc123")
        assert _make_record_key(r) == "arxiv:2301.00001"

    def test_s2_used_when_no_doi_or_arxiv(self) -> None:
        r = _record(doi=None, arxiv_id=None, s2_paper_id="abc123def456")
        assert _make_record_key(r) == "s2:abc123def456"

    def test_title_fallback(self) -> None:
        r = _record(doi=None, arxiv_id=None, s2_paper_id=None, title="Robots in Space!")
        key = _make_record_key(r)
        assert key.startswith("title:")
        assert "robots in space" in key

    def test_title_normalises_punctuation(self) -> None:
        r1 = _record(doi=None, arxiv_id=None, s2_paper_id=None, title="Robot: A Survey")
        r2 = _record(doi=None, arxiv_id=None, s2_paper_id=None, title="Robot  A Survey")
        assert _make_record_key(r1) == _make_record_key(r2)

    def test_title_normalises_case(self) -> None:
        r1 = _record(
            doi=None, arxiv_id=None, s2_paper_id=None, title="ROBOT NAVIGATION"
        )
        r2 = _record(
            doi=None, arxiv_id=None, s2_paper_id=None, title="robot navigation"
        )
        assert _make_record_key(r1) == _make_record_key(r2)

    def test_different_dois_produce_different_keys(self) -> None:
        r1 = _record(doi="10.1/a")
        r2 = _record(doi="10.1/b")
        assert _make_record_key(r1) != _make_record_key(r2)

    def test_same_doi_same_key_regardless_of_title(self) -> None:
        r1 = _record(doi="10.1/same", title="Title One")
        r2 = _record(doi="10.1/same", title="Title Two")
        assert _make_record_key(r1) == _make_record_key(r2)
