from __future__ import annotations

from loguru import logger
from rapidfuzz import fuzz

from ..config import Config
from ..models import PaperRecord


def deduplicate(records: list[PaperRecord], config: Config) -> list[PaperRecord]:
    threshold = config.deduplication.fuzzy_threshold * 100  # rapidfuzz uses 0-100 scale

    by_doi: dict[str, PaperRecord] = {}
    no_doi: list[PaperRecord] = []
    doi_dupe_count = 0

    for record in records:
        doi = _normalise_doi(record.doi)
        if doi:
            if doi in by_doi:
                doi_dupe_count += 1
                existing = by_doi[doi]
                if config.db_priority(record.source_database) < config.db_priority(
                    existing.source_database
                ):
                    # Keep arxiv_id from the lower-priority version before replacing
                    if record.arxiv_id and not existing.arxiv_id:
                        record = record.model_copy(
                            update={"arxiv_id": existing.arxiv_id}
                        )
                    by_doi[doi] = record
                else:
                    # Merge arxiv_id into existing
                    if record.arxiv_id and not existing.arxiv_id:
                        by_doi[doi] = existing.model_copy(
                            update={"arxiv_id": record.arxiv_id}
                        )
            else:
                by_doi[doi] = record
        else:
            no_doi.append(record)

    # Fuzzy title dedup for records without DOI
    seen: list[PaperRecord] = list(by_doi.values())
    fuzzy_dupe_count = 0

    for record in no_doi:
        is_dupe = False
        record_title = record.title.lower()
        for existing in seen:
            similarity = fuzz.ratio(record_title, existing.title.lower())
            if similarity >= threshold:
                is_dupe = True
                fuzzy_dupe_count += 1
                # Merge arxiv_id into the winner
                if record.arxiv_id and not existing.arxiv_id:
                    idx = seen.index(existing)
                    seen[idx] = existing.model_copy(
                        update={"arxiv_id": record.arxiv_id}
                    )
                break
        if not is_dupe:
            seen.append(record)

    logger.info(
        f"Deduplication complete: {doi_dupe_count} DOI dupes, "
        f"{fuzzy_dupe_count} fuzzy title dupes removed. "
        f"Unique: {len(seen)} (from {len(records)} total)"
    )
    return seen


def _normalise_doi(doi: str | None) -> str | None:
    if not doi:
        return None
    doi = doi.strip().lower()
    # Strip URL prefix if present
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if doi.startswith(prefix):
            doi = doi[len(prefix) :]
    return doi if doi else None
