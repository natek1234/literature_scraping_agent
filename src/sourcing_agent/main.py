from __future__ import annotations

import asyncio
import os
import sys
import time
from collections import defaultdict
from typing import TYPE_CHECKING, Any

from dotenv import load_dotenv
from loguru import logger

if TYPE_CHECKING:
    from .config import Config, DatabaseConfig
    from .models import PaperRecord

load_dotenv()

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf-8-sig"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]


# ── JSONL helpers (used for per-DB and dedup caches) ─────────────────────────


def _save_jsonl(path: str, records: list[PaperRecord]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(r.model_dump_json() + "\n")


def _load_jsonl(path: str) -> list[PaperRecord]:
    from .models import PaperRecord as _PR

    with open(path, encoding="utf-8") as f:
        return [_PR.model_validate_json(line) for line in f if line.strip()]


def _db_cache_path(out_dir: str, db_name: str) -> str:
    slug = db_name.lower().replace(" ", "_")
    return os.path.join(out_dir, f"papers-{slug}.jsonl")


_CRED_PLACEHOLDERS = ("your_email", "your_password", "placeholder", "institution.edu")


def _browser_creds_available(db: DatabaseConfig) -> bool:
    """Return True when real (non-placeholder) credentials exist for a paywalled DB."""
    if db.type != "paywalled_browser":
        return True
    cred = db.credential_env_vars
    username = os.environ.get(cred.get("username", ""), "")
    password = os.environ.get(cred.get("password", ""), "")
    if not username or not password:
        return False
    return not (
        any(p in username for p in _CRED_PLACEHOLDERS)
        or any(p in password for p in _CRED_PLACEHOLDERS)
    )


def _db_skip_note(db: DatabaseConfig) -> str:
    """Return a short reason string when a browser DB returns 0 results."""
    if db.type != "paywalled_browser":
        return ""
    cred = db.credential_env_vars
    username = os.environ.get(cred.get("username", ""), "")
    password = os.environ.get(cred.get("password", ""), "")
    if not username or not password:
        return "no credentials in .env"
    if any(p in username for p in _CRED_PLACEHOLDERS) or any(
        p in password for p in _CRED_PLACEHOLDERS
    ):
        return "placeholder credentials — update .env"
    return "access blocked or 0 results"


# ── Logging setup ─────────────────────────────────────────────────────────────


def _setup_logging(log_file: str) -> None:
    os.makedirs(os.path.dirname(log_file) or ".", exist_ok=True)
    logger.remove()
    logger.add(
        sys.stderr,
        level="INFO",
        colorize=True,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
    )
    logger.add(
        log_file,
        level="DEBUG",
        rotation="50 MB",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{line} — {message}",
    )


# ── Main pipeline ─────────────────────────────────────────────────────────────


async def run(context_path: str = "CONTEXT.md") -> None:
    from .config import Config
    from .output.excel_writer import write_to_excel
    from .output.zotero_writer import write_to_zotero
    from .pipeline.deduplicator import deduplicate
    from .pipeline.query_builder import build_queries, build_supplementary_queries
    from .pipeline.scorer import apply_auto_rules, score_papers
    from .progress import ProgressTracker
    from .summary import SummaryWriter

    config = Config.from_file(context_path)
    _setup_logging(config.output.log_file)
    progress = ProgressTracker(config.output.progress_file)
    progress.load_or_init(config.project_title)

    out_dir = os.path.dirname(config.output.progress_file) or "./outputs"
    summary = SummaryWriter(os.path.join(out_dir, "sourcing-summary.txt"))
    summary.init(progress.run_id, config.project_title)

    start_time = time.time()
    all_records: list[PaperRecord] = []

    # ── Step 1: Build queries ─────────────────────────────────────────────────
    if not progress.is_step_complete("queries_built"):
        queries = build_queries(config)
        progress.write_checkpoint(
            "queries_built", {"clusters": len(config.keywords_tier_2)}
        )
    else:
        queries = build_queries(config)
        logger.info("Queries rebuilt from config (step already complete)")

    n_queries = sum(len(v) for v in queries.values())
    logger.info(f"✓ Queries built: {n_queries} queries across {len(queries)} databases")
    logger.info(f"  Query log written to: {config.output.query_log}")

    # ── Step 2: Query databases (per-DB cache for true resume) ───────────────
    from .databases import arxiv, nasa_ntrs, semantic_scholar

    # True whenever any DB is freshly queried this session (not from cache).
    # Used below to invalidate a stale dedup cache so new records aren't lost.
    any_db_newly_queried = False

    for db in config.databases:
        if not db.enabled:
            continue

        step_key = f"{db.name.lower().replace(' ', '_')}_queried"
        db_cache = _db_cache_path(out_dir, db.name)

        # Resume: load from cache when step is complete AND cache file exists
        if progress.is_step_complete(step_key) and os.path.exists(db_cache):
            try:
                db_records = _load_jsonl(db_cache)
                all_records.extend(db_records)
                logger.info(
                    f"  {db.name}: loaded {len(db_records):,} papers from cache "
                    "(skipping re-query)"
                )
                summary.update_db(db.name, len(db_records), note="resumed from cache")
                continue
            except Exception as e:
                logger.warning(f"  {db.name}: cache load failed ({e}) — re-querying")

        # Skip paywalled DBs that have no credentials — do NOT save cache or mark
        # the step complete so that adding credentials later and resuming will
        # re-query this DB rather than loading an empty cache.
        if db.type == "paywalled_browser" and not _browser_creds_available(db):
            logger.warning(
                f"  {db.name}: skipped — credentials missing from .env "
                "(add credentials and re-run to query this database)"
            )
            summary.update_db(
                db.name, 0, note="skipped — add credentials to .env and resume"
            )
            continue

        # Query the database
        db_records = []
        db_queries = queries.get(db.name, [])

        if db.type == "open_access_api":
            for q in db_queries:
                try:
                    if db.name == "Semantic Scholar":
                        batch = await semantic_scholar.search(q, config)
                    elif db.name == "arXiv":
                        batch = await arxiv.search(q, config)
                    elif db.name == "NASA Technical Reports Server":
                        batch = await nasa_ntrs.search(q, config)
                    else:
                        batch = []
                    db_records.extend(batch)
                except Exception as e:
                    logger.error(f"{db.name}: query failed — {e}")

        elif db.type == "paywalled_browser":
            from .databases.browser_scraper import search_batch as browser_search_batch

            try:
                db_records = await browser_search_batch(db, db_queries, config)
            except Exception as e:
                logger.error(f"{db.name}: browser batch failed — {e}")

        # Persist to cache so this DB never needs re-querying on resume
        _save_jsonl(db_cache, db_records)
        all_records.extend(db_records)
        progress.log_prisma_count("identified", db.name, len(db_records))
        progress.write_checkpoint(step_key, {"retrieved": len(db_records)})
        any_db_newly_queried = True

        if db_records:
            logger.info(f"✓ {db.name}: {len(db_records):,} results")
            summary.update_db(db.name, len(db_records))
        else:
            note = _db_skip_note(db)
            logger.info(f"  {db.name}: 0 results{f' ({note})' if note else ''}")
            summary.update_db(db.name, 0, note=note)

    # ── Step 3: Deduplicate ───────────────────────────────────────────────────
    dedup_cache = os.path.join(out_dir, "papers-deduped.jsonl")

    # If any DB was freshly queried this session, the stale dedup cache is
    # incomplete — the new records were never included. Invalidate it so the
    # full all_records list (old + new) is deduped together.
    if any_db_newly_queried and progress.is_step_complete("deduplicated"):
        logger.info(
            "  Deduplication: invalidating stale cache — new database results arrived"
        )
        progress.invalidate_step("deduplicated")

    if not progress.is_step_complete("deduplicated"):
        before = len(all_records)
        all_records = deduplicate(all_records, config)
        removed = before - len(all_records)
        _save_jsonl(dedup_cache, all_records)
        progress.log_prisma_count("after_dedup", "all", len(all_records))
        progress.write_checkpoint(
            "deduplicated", {"unique": len(all_records), "removed": removed}
        )
        logger.info(
            f"✓ Deduplication: {len(all_records):,} unique papers "
            f"(removed {removed:,} duplicates)"
        )
        summary.update_dedup(len(all_records), removed)
    else:
        if os.path.exists(dedup_cache):
            all_records = _load_jsonl(dedup_cache)
            logger.info(
                f"  Deduplication: already complete — "
                f"loaded {len(all_records):,} papers from cache"
            )
            summary.update_dedup(
                len(all_records),
                sum(v.get("count", 0) for v in summary._db.values()) - len(all_records),
            )
        else:
            logger.warning(
                "  Deduplication: marked complete but cache missing — "
                "re-running database queries is required"
            )

    # ── Step 4: Score ─────────────────────────────────────────────────────────
    scored_cache = os.path.join(out_dir, "papers-scored.jsonl")

    if not progress.is_step_complete("scored"):
        summary.update_scoring(
            total=len(all_records),
            scored=0,
            include=0,
            maybe=0,
            exclude=0,
            errors=0,
        )
        progress.write_checkpoint("scoring", {"total": len(all_records)})
        all_records = await score_papers(
            all_records,
            config,
            progress,
            summary=summary,
            scored_cache=scored_cache,
        )
        all_records = apply_auto_rules(all_records, config)

        # Overwrite scored cache with post-auto-rules records
        _save_jsonl(scored_cache, all_records)

        errors = sum(
            1 for r in all_records if r.agent_notes and "SCORING_ERROR" in r.agent_notes
        )
        if errors == len(all_records) and errors > 0:
            logger.error(
                f"All {errors} papers failed scoring. "
                "Likely cause: ANTHROPIC_API_KEY is missing from .env."
            )
        progress.write_checkpoint(
            "scored", {"total": len(all_records), "errors": errors}
        )
        logger.info(
            f"✓ Scoring: {len(all_records):,} papers scored "
            f"({errors} errors flagged for review)"
        )
    else:
        if os.path.exists(scored_cache):
            all_records = _load_jsonl(scored_cache)
            logger.info(
                f"  Scoring: already complete — "
                f"loaded {len(all_records):,} scored papers from cache"
            )
        else:
            logger.warning(
                "  Scoring: marked complete but scored cache missing — "
                "continuing with in-memory records (scores may be lost)"
            )

    # ── Step 5: Coverage check + supplementary queries ────────────────────────
    if not progress.is_step_complete("coverage_checked"):
        undercovered = _check_section_coverage(all_records, config)
        if undercovered:
            logger.info(
                f"  Section undercoverage: {undercovered} — running supplementary queries"
            )
            for section_tag in undercovered:
                supp_queries = build_supplementary_queries(section_tag, config)
                supp_records: list[PaperRecord] = []

                for db_name, db_qs in supp_queries.items():
                    supp_db = config.db_by_name(db_name)
                    if not supp_db or not supp_db.enabled:
                        continue
                    for q in db_qs:
                        try:
                            if db_name == "Semantic Scholar":
                                batch = await semantic_scholar.search(q, config)
                            elif db_name == "arXiv":
                                batch = await arxiv.search(q, config)
                            elif db_name == "NASA Technical Reports Server":
                                batch = await nasa_ntrs.search(q, config)
                            else:
                                batch = []
                            supp_records.extend(batch)
                        except Exception as e:
                            logger.error(f"Supplementary query failed: {e}")

                if supp_records:
                    all_records.extend(supp_records)
                    all_records = deduplicate(all_records, config)
                    supp_scored = await score_papers(
                        supp_records, config, progress, summary=summary
                    )
                    supp_scored = apply_auto_rules(supp_scored, config)
                    supp_titles = {r.title for r in supp_scored}
                    all_records = [r for r in all_records if r.title not in supp_titles]
                    all_records.extend(supp_scored)
                    logger.info(
                        f"  Supplementary: +{len(supp_scored):,} records for {section_tag}"
                    )

        progress.write_checkpoint("coverage_checked", {"undercovered": undercovered})

    # ── Step 6: Print coverage summary ────────────────────────────────────────
    _print_coverage(all_records, config)

    # ── Step 7: Write to Zotero ───────────────────────────────────────────────
    if not progress.is_step_complete("zotero_written"):
        if config.output.zotero.enabled:
            try:
                summary.update_zotero("writing...")
                n_written = write_to_zotero(all_records, config)
                progress.write_checkpoint("zotero_written", {"written": n_written})
                logger.info(f"✓ Zotero: {n_written:,} papers written")
                summary.update_zotero(f"complete ({n_written:,} papers)")
            except Exception as e:
                logger.error(f"Zotero write failed — {e} — falling back to Excel only")
                summary.update_zotero(f"FAILED: {e}")
        else:
            logger.info("  Zotero: disabled in config")
            summary.update_zotero("disabled")
    else:
        logger.info("  Zotero: already written")
        summary.update_zotero("already written (previous run)")

    # ── Step 8: Write to Excel ────────────────────────────────────────────────
    if not progress.is_step_complete("excel_written"):
        try:
            summary.update_excel("writing...")
            write_to_excel(all_records, config)
            progress.write_checkpoint(
                "excel_written", {"path": config.output.excel.path}
            )
            logger.info(f"✓ Excel: written to {config.output.excel.path}")
            summary.update_excel(f"complete — {config.output.excel.path}")
        except Exception as e:
            logger.error(f"Excel write failed — {e}")
            summary.update_excel(f"FAILED: {e}")
    else:
        logger.info("  Excel: already written")
        summary.update_excel("already written (previous run)")

    # ── Results tallies ───────────────────────────────────────────────────────
    n_include = sum(1 for r in all_records if r.inclusion_decision == "include")
    n_maybe = sum(1 for r in all_records if r.inclusion_decision == "maybe")
    n_exclude = sum(1 for r in all_records if r.inclusion_decision == "exclude")
    n_errors = sum(
        1 for r in all_records if r.agent_notes and "SCORING_ERROR" in r.agent_notes
    )

    by_kunze: dict[str, int] = defaultdict(int)
    for r in all_records:
        if r.inclusion_decision in ("include", "maybe") and r.kunze_dimension:
            by_kunze[r.kunze_dimension] += 1

    conf_counts: dict[str, int] = defaultdict(int)
    for r in all_records:
        if r.cluster_assignment_confidence:
            conf_counts[r.cluster_assignment_confidence] += 1

    summary.update_scoring(
        total=len(all_records),
        scored=len(all_records),
        include=n_include,
        maybe=n_maybe,
        exclude=n_exclude,
        errors=n_errors,
    )
    summary.mark_complete()

    progress.update_results(
        include=n_include,
        maybe=n_maybe,
        exclude=n_exclude,
        by_kunze=dict(by_kunze),
        cluster_confidence=dict(conf_counts),
    )
    progress.write_checkpoint("complete", {"status": "complete"})
    progress.mark_complete()

    elapsed = time.time() - start_time
    _print_final_summary(
        all_records,
        config,
        elapsed,
        n_include,
        n_maybe,
        n_exclude,
        by_kunze,
        conf_counts,
    )


# ── Helpers ───────────────────────────────────────────────────────────────────


def _check_section_coverage(records: list[Any], config: Config) -> list[str]:
    included = [r for r in records if r.inclusion_decision == "include"]
    undercovered: list[str] = []
    for _tag, sec in config.paper_structure.items():
        count = sum(
            1
            for r in included
            if sec.section_tag in [r.primary_section, *r.secondary_sections]
        )
        if count < sec.target_min * config.edge_cases.section_undercoverage_threshold:
            undercovered.append(sec.section_tag)
    return undercovered


def _print_coverage(records: list[Any], config: Config) -> None:
    included = [r for r in records if r.inclusion_decision == "include"]
    print("\n✓ Section coverage check:")
    target_map = {
        "S1:introduction": "10-20",
        "S2:history": "25-40",
        "S3:ai-in-space": "30-50",
        "S3a:ai-space-robotics": "20-30",
        "S3b:ai-spacecraft": "10-20",
        "S4a:navigation": "15-25",
        "S4b:perception": "15-25",
        "S4c:reasoning": "20-30",
        "S4d:planning": "20-30",
        "S4e:interaction": "15-25",
        "S4f:learning": "15-25",
        "S4g:alignment": "20-30",
        "S5a:multimodality": "15-25",
        "S5b:machine-brain": "20-30",
        "S5c:integration-protocols": "10-20",
        "S6:future-directions": "15-25",
    }
    for sec_tag, target in target_map.items():
        count = sum(
            1 for r in included if sec_tag in [r.primary_section, *r.secondary_sections]
        )
        target_min = int(target.split("-")[0])
        status = "adequate" if count >= target_min * 0.5 else "needs more"
        label = sec_tag.split(":")[0].upper()
        print(f"    {label:<6} {count:>3} included / target {target:>7}  [{status}]")


def _print_final_summary(
    records: list[Any],
    config: Config,
    elapsed: float,
    n_include: int,
    n_maybe: int,
    n_exclude: int,
    by_kunze: dict,
    conf_counts: dict,
) -> None:
    mins = int(elapsed // 60)
    secs = int(elapsed % 60)

    by_db: dict[str, int] = defaultdict(int)
    for r in records:
        if r.inclusion_decision in ("include", "maybe"):
            by_db[r.source_database] += 1

    print(f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Sourcing run complete
  Project: {config.project_title}
  Run time: {mins}m {secs}s
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Candidates retrieved (total):  {len(records):,}

  INCLUDED:  {n_include:,} papers  →  Zotero + Excel
  MAYBE:     {n_maybe:,} papers  →  Zotero + Excel (flagged for review)
  EXCLUDED:  {n_exclude:,} papers  →  Excel only

  By Kunze dimension (included + maybe):
    D1 Navigation & Mapping:         {by_kunze.get('D1', 0)}
    D2 Perception:                   {by_kunze.get('D2', 0)}
    D3 Knowledge & Reasoning:        {by_kunze.get('D3', 0)}
    D4 Planning:                     {by_kunze.get('D4', 0)}
    D5 Interaction:                  {by_kunze.get('D5', 0)}
    D6 Learning:                     {by_kunze.get('D6', 0)}
    Alignment (S4g, cross-cutting):  {by_kunze.get('alignment', 0)}

  Cluster confidence breakdown (S4 papers):
    High:    {conf_counts.get('high', 0)}
    Medium:  {conf_counts.get('medium', 0)}  ← review before writing stage
    Low:     {conf_counts.get('low', 0)}  ← requires full-text review

  Outputs:
    Zotero collection:  {config.output.zotero.collection_name}
    Excel file:         {config.output.excel.path}
    Summary file:       {os.path.join(os.path.dirname(config.output.progress_file) or './outputs', 'sourcing-summary.txt')}
    Query log:          {config.output.query_log}
    Progress file:      {config.output.progress_file}
    Run log:            {config.output.log_file}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  NEXT STEPS (in order):
  1. Review medium/low confidence cluster assignments in Excel
  2. Review "maybe" papers in Zotero or Excel
  3. Verify S2 mission taxonomy in "Analytical Data" sheet
  4. Hand confirmed include set to writing agent
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━""")


def cli() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    asyncio.run(run())
