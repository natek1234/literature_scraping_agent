from __future__ import annotations

import os
import re
import time
from typing import TYPE_CHECKING

from loguru import logger
from pyzotero import zotero

if TYPE_CHECKING:
    from ..config import Config
    from ..models import PaperRecord


def write_to_zotero(
    records: list[PaperRecord], config: Config, clear_first: bool = False
) -> int:
    """Write include/maybe papers to Zotero. Returns count of items written.

    Args:
        clear_first: If True, delete all existing items in the collection
            before writing — use this to fix duplicates from prior runs.
            If False (default), existing items with matching DOI or title
            are skipped (upsert behaviour).
    """
    z = _get_client()
    if z is None:
        logger.error("Zotero: client unavailable — skipping Zotero write")
        return 0

    to_write = [r for r in records if r.inclusion_decision in ("include", "maybe")]
    if not to_write:
        logger.info("Zotero: no papers to write (include + maybe = 0)")
        return 0

    # Ensure collection hierarchy exists
    top_key = _ensure_collection(z, config.output.zotero.collection_name)
    subcol_keys: dict[str, str] = {}
    for name in config.output.zotero.subcollections:
        subcol_keys[name] = _ensure_subcollection(z, top_key, name)

    if clear_first:
        logger.info("Zotero: clearing all existing items before rewrite...")
        _clear_collection_items(z, top_key, subcol_keys)
        existing_dois: set[str] = set()
        existing_titles: set[str] = set()
    else:
        existing_dois, existing_titles = _build_doi_title_index(z, top_key)
        if existing_dois or existing_titles:
            logger.info(
                f"Zotero: upsert mode — {len(existing_dois)} existing DOIs, "
                f"{len(existing_titles)} title fingerprints loaded"
            )

    written = 0
    skipped = 0
    for record in to_write:
        try:
            doi_key = (record.doi or "").strip().lower()
            title_key = _normalize_title(record.title)

            if doi_key and doi_key in existing_dois:
                skipped += 1
                continue
            if not doi_key and title_key in existing_titles:
                skipped += 1
                continue

            _write_record(z, record, config, top_key, subcol_keys)

            if doi_key:
                existing_dois.add(doi_key)
            existing_titles.add(title_key)
            written += 1
        except Exception as e:
            logger.warning(f"Zotero: failed to write '{record.title[:60]}': {e}")

    if skipped:
        logger.info(f"Zotero: {skipped} already-existing papers skipped (upsert)")
    logger.info(f"Zotero: {written}/{len(to_write)} papers written")
    return written


def _clear_collection_items(
    z: zotero.Zotero, top_key: str, subcol_keys: dict[str, str]
) -> None:
    """Delete all library items that belong to this collection tree.

    Fetches a fresh library version immediately before each batch DELETE to
    avoid HTTP 412 (Precondition Failed) errors caused by the collection
    ensure calls or Zotero desktop syncing bumping the library version between
    our item-fetch and delete calls.
    """
    seen: set[str] = set()
    all_items: list[dict] = []

    for col_key in [top_key] + [k for k in subcol_keys.values() if k]:
        try:
            items = z.everything(z.collection_items_top(col_key))
            for item in items:
                key = item.get("key", "")
                if key and key not in seen:
                    seen.add(key)
                    all_items.append(item)
        except Exception as exc:
            logger.warning(
                f"Zotero: could not fetch items from collection {col_key}: {exc}"
            )

    if not all_items:
        logger.info("Zotero: no existing items to clear")
        return

    logger.info(f"Zotero: deleting {len(all_items)} existing items...")
    _BATCH = 50
    _MAX_RETRIES = 3
    deleted = 0
    for i in range(0, len(all_items), _BATCH):
        batch = all_items[i : i + _BATCH]
        for attempt in range(_MAX_RETRIES):
            try:
                # Fetch a fresh library version immediately before the DELETE
                # so the If-Unmodified-Since-Version header is current.
                last_modified = z.last_modified_version()
                z.delete_item(batch, last_modified=last_modified)
                deleted += len(batch)
                break
            except Exception as exc:
                err = str(exc)
                is_412 = "412" in err or "precondition" in err.lower()
                if is_412 and attempt < _MAX_RETRIES - 1:
                    logger.debug(f"Zotero: 412 on batch {i // _BATCH + 1}, retrying...")
                    time.sleep(1)
                else:
                    logger.warning(
                        f"Zotero: batch {i // _BATCH + 1} delete failed ({exc}); skipping"
                    )
                    break
        time.sleep(0.3)
    logger.info(f"Zotero: {deleted}/{len(all_items)} items cleared")


def _build_doi_title_index(z: zotero.Zotero, top_key: str) -> tuple[set[str], set[str]]:
    """Return (doi_set, title_set) of items already in the top collection."""
    dois: set[str] = set()
    titles: set[str] = set()
    try:
        items = z.everything(z.collection_items_top(top_key))
        for item in items:
            data = item.get("data", {})
            doi = data.get("DOI", "").strip().lower()
            if doi:
                dois.add(doi)
            title = data.get("title", "")
            if title:
                titles.add(_normalize_title(title))
    except Exception as exc:
        logger.warning(f"Zotero: could not build dedup index — {exc}")
    return dois, titles


def _normalize_title(title: str) -> str:
    """Lowercase + collapse non-alphanumeric chars for fuzzy title dedup."""
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]", " ", title.lower())).strip()


def _get_client() -> zotero.Zotero | None:
    api_key = os.environ.get("ZOTERO_API_KEY", "")
    lib_id = os.environ.get("ZOTERO_LIBRARY_ID", "")
    if not api_key or not lib_id:
        logger.error("Zotero: ZOTERO_API_KEY or ZOTERO_LIBRARY_ID not set")
        return None
    try:
        z = zotero.Zotero(lib_id, "user", api_key)
        return z
    except Exception as e:
        logger.error(f"Zotero: client init failed — {e}")
        return None


def _ensure_collection(z: zotero.Zotero, name: str) -> str:
    try:
        collections = z.collections()
        for col in collections:
            if col["data"]["name"] == name:
                return col["key"]
        resp = z.create_collections([{"name": name}])
        return resp["successful"]["0"]["key"]
    except Exception as e:
        logger.error(f"Zotero: could not create top-level collection '{name}': {e}")
        return ""


def _ensure_subcollection(z: zotero.Zotero, parent_key: str, name: str) -> str:
    if not parent_key:
        return ""
    try:
        collections = z.collections_sub(parent_key)
        for col in collections:
            if col["data"]["name"] == name:
                return col["key"]
        resp = z.create_collections([{"name": name, "parentCollection": parent_key}])
        return resp["successful"]["0"]["key"]
    except Exception as e:
        logger.warning(f"Zotero: could not create subcollection '{name}': {e}")
        return parent_key  # Fall back to parent


def _write_record(
    z: zotero.Zotero,
    record: PaperRecord,
    config: Config,
    top_key: str,
    subcol_keys: dict[str, str],
) -> None:

    collection_keys = _build_collection_keys(record, config, top_key, subcol_keys)
    tags = _build_tags(record, config)

    item_type = _infer_item_type(record.publication_type)

    item: dict = {
        "itemType": item_type,
        "title": record.title,
        "abstractNote": record.abstract or "",
        "date": str(record.year or ""),
        "DOI": record.doi or "",
        "url": record.open_access_pdf_url or "",
        "publicationTitle": record.venue or "",
        "volume": record.volume or "",
        "issue": record.issue or "",
        "pages": record.pages or "",
        "creators": [
            {"creatorType": "author", "name": author} for author in record.authors
        ],
        "tags": tags,
        "collections": collection_keys,
    }

    resp = z.create_items([item])
    failed = resp.get("failed", {})
    if failed:
        reasons = [str(v) for v in failed.values()]
        raise RuntimeError(f"Zotero rejected item '{record.title[:60]}': {reasons}")
    item_key = resp.get("successful", {}).get("0", {}).get("key", "")

    if item_key and config.output.zotero.add_abstract_note:
        note_text = _build_abstract_note(record)
        try:
            z.create_items(
                [
                    {
                        "itemType": "note",
                        "parentItem": item_key,
                        "note": note_text,
                        "tags": [],
                    }
                ]
            )
        except Exception as e:
            logger.debug(f"Zotero: could not add abstract note: {e}")


def _build_collection_keys(
    record: PaperRecord,
    config: Config,
    top_key: str,
    subcol_keys: dict[str, str],
) -> list[str]:
    keys = set()
    if top_key:
        keys.add(top_key)

    section_to_subcol = {
        "S1:introduction": "S1_Introduction",
        "S2:history": "S2_SpaceAutonomyHistory",
        "S3:ai-in-space": "S3_AIinSpace",
        "S3a:ai-space-robotics": "S3a_AISpaceRobotics",
        "S3b:ai-spacecraft": "S3b_AISpacecraft",
        "S4a:navigation": "S4a_D1_NavigationMapping",
        "S4b:perception": "S4b_D2_Perception",
        "S4c:reasoning": "S4c_D3_KnowledgeReasoning",
        "S4d:planning": "S4d_D4_Planning",
        "S4e:interaction": "S4e_D5_Interaction",
        "S4f:learning": "S4f_D6_Learning",
        "S4g:alignment": "S4g_Alignment",
        "S5a:multimodality": "S5a_Multimodality",
        "S5b:machine-brain": "S5b_MachineBrain",
        "S5c:integration-protocols": "S5c_IntegrationProtocols",
        "S6:future-directions": "S6_FutureDirections",
    }

    all_sections = (
        [record.primary_section] if record.primary_section else []
    ) + record.secondary_sections
    for sec in all_sections:
        subcol_name = section_to_subcol.get(sec)
        if subcol_name and subcol_name in subcol_keys and subcol_keys[subcol_name]:
            keys.add(subcol_keys[subcol_name])

    if record.is_cross_cutting and "_CrossCutting" in subcol_keys:
        keys.add(subcol_keys["_CrossCutting"])

    if record.inclusion_decision == "maybe" and "_MaybeReview" in subcol_keys:
        keys.add(subcol_keys["_MaybeReview"])

    return list(keys)


def _build_tags(record: PaperRecord, config: Config) -> list[dict]:
    tags: list[dict] = []

    def _tag(t: str) -> None:
        tags.append({"tag": t})

    if record.primary_section:
        _tag(record.primary_section)
    for sec in record.secondary_sections:
        _tag(sec)
    if record.kunze_dimension:
        _tag(f"kunze:{record.kunze_dimension}")
    if record.technique_cluster:
        _tag(f"cluster:{record.technique_cluster}")
    if record.cluster_assignment_confidence:
        _tag(f"confidence:{record.cluster_assignment_confidence}")
    if record.source_type:
        _tag(f"type:{record.source_type}")
    if record.inclusion_decision:
        _tag(f"status:{record.inclusion_decision}")

    db_slug = record.source_database.lower().replace(" ", "_")
    _tag(f"source:{db_slug}")

    tier = _get_venue_tier(record.venue, config)
    _tag(f"venue:tier{tier}")

    bool_flags = [
        ("cross_cutting", record.is_cross_cutting),
        ("historical", record.is_historical),
        ("space_heritage", record.space_heritage),
        ("deployment_constraints_discussed", record.deployment_constraints_discussed),
        ("compute_requirements_noted", record.compute_requirements_noted),
        ("radiation_robustness_discussed", record.radiation_robustness_discussed),
        ("alignment_paper", record.alignment_paper),
        ("compositional_alignment", record.compositional_alignment),
        (
            "general_alignment_robotics_context",
            record.general_alignment_robotics_context,
        ),
        ("operational_description_present", record.operational_description_present),
    ]
    for flag_name, flag_value in bool_flags:
        if flag_value:
            _tag(flag_name)

    return tags


def _build_abstract_note(record: PaperRecord) -> str:
    return (
        f"<b>Abstract:</b><br>{record.abstract or '[Not available]'}<br><br>"
        f"<b>Primary Section:</b> {record.primary_section}<br>"
        f"<b>Secondary Sections:</b> {', '.join(record.secondary_sections) or 'None'}<br>"
        f"<b>Kunze Dimension:</b> {record.kunze_dimension or 'N/A'}<br>"
        f"<b>Technique Cluster:</b> {record.technique_cluster or 'N/A'} "
        f"({record.cluster_assignment_confidence or 'N/A'} confidence)<br>"
        f"<b>Source Type:</b> {record.source_type or 'N/A'}<br>"
        f"<b>Section Fit:</b> {record.section_fit_score} | "
        f"<b>Contribution:</b> {record.contribution_score} | "
        f"<b>Recency:</b> {record.recency_score}<br>"
        f"<b>Weighted Score:</b> {record.weighted_score}<br>"
        f"<b>Agent Notes:</b> {record.agent_notes}"
    )


def _infer_item_type(pub_type: str | None) -> str:
    if not pub_type:
        return "journalArticle"
    pt = pub_type.lower()
    if "conference" in pt or "proceeding" in pt:
        return "conferencePaper"
    if "report" in pt or "technical" in pt:
        return "report"
    if "preprint" in pt or "arxiv" in pt:
        return "preprint"
    if "book" in pt or "chapter" in pt:
        return "bookSection"
    return "journalArticle"


def _get_venue_tier(venue: str | None, config: Config) -> int:
    if not venue:
        return 3
    v = venue.lower()
    for t1 in config.filters.tier_1_venues:
        if t1.lower() in v:
            return 1
    for t2 in config.filters.tier_2_venues:
        if t2.lower() in v:
            return 2
    return 3
