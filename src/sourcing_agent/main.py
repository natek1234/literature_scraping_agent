from __future__ import annotations

import asyncio
import sys
import time
from collections import defaultdict
from typing import TYPE_CHECKING, Any

from dotenv import load_dotenv
from loguru import logger

if TYPE_CHECKING:
    from .config import Config

load_dotenv()


def _setup_logging(log_file: str) -> None:
    import os

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


async def run(context_path: str = "CONTEXT.md") -> None:
    from .config import Config
    from .models import PaperRecord
    from .output.excel_writer import write_to_excel
    from .output.zotero_writer import write_to_zotero
    from .pipeline.deduplicator import deduplicate
    from .pipeline.query_builder import build_queries, build_supplementary_queries
    from .pipeline.scorer import apply_auto_rules, score_papers
    from .progress import ProgressTracker

    config = Config.from_file(context_path)
    _setup_logging(config.output.log_file)
    progress = ProgressTracker(config.output.progress_file)
    progress.load_or_init(config.project_title)

    start_time = time.time()
    all_records: list[PaperRecord] = []

    # ── Step 1: Build queries ─────────────────────────────────────────────────
    if not progress.is_step_complete("queries_built"):
        queries = build_queries(config)
        progress.write_checkpoint(
            "queries_built", {"clusters": len(config.keywords_tier_2)}
        )
    else:
        queries = build_queries(config)  # Rebuild from config (no network calls)
        logger.info("Queries rebuilt from config (step already complete)")

    n_queries = sum(len(v) for v in queries.values())
    logger.info(f"✓ Queries built: {n_queries} queries across {len(queries)} databases")
    logger.info(f"  Query log written to: {config.output.query_log}")

    # ── Step 2: Query open-access databases ──────────────────────────────────
    from .databases import arxiv, nasa_ntrs, semantic_scholar

    for db in config.databases:
        if not db.enabled:
            continue
        step_key = f"{db.name.lower().replace(' ', '_')}_queried"

        if progress.is_step_complete(step_key):
            logger.info(f"  {db.name}: already queried (skipping)")
            continue

        if db.type == "open_access_api":
            db_records: list[PaperRecord] = []
            db_queries = queries.get(db.name, [])

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

            all_records.extend(db_records)
            progress.log_prisma_count("identified", db.name, len(db_records))
            progress.write_checkpoint(step_key, {"retrieved": len(db_records)})
            logger.info(f"✓ {db.name}: {len(db_records)} results")

        elif db.type == "paywalled_browser":
            from .databases.browser_scraper import search as browser_search

            db_records = []
            db_queries = queries.get(db.name, [])

            for q in db_queries:
                try:
                    batch = await browser_search(db, q, config)
                    db_records.extend(batch)
                except Exception as e:
                    logger.error(f"{db.name}: browser query failed — {e}")

            all_records.extend(db_records)
            progress.log_prisma_count("identified", db.name, len(db_records))
            progress.write_checkpoint(step_key, {"retrieved": len(db_records)})
            if db_records:
                logger.info(f"✓ {db.name}: {len(db_records)} results")
            else:
                logger.info(f"  {db.name}: SKIPPED or 0 results")

    # ── Step 3: Deduplicate ───────────────────────────────────────────────────
    if not progress.is_step_complete("deduplicated"):
        before_dedup = len(all_records)
        all_records = deduplicate(all_records, config)
        progress.log_prisma_count("after_dedup", "all", len(all_records))
        progress.write_checkpoint(
            "deduplicated",
            {
                "unique": len(all_records),
                "removed": before_dedup - len(all_records),
            },
        )
        logger.info(
            f"✓ Deduplication: {len(all_records)} unique papers "
            f"(removed {before_dedup - len(all_records)} duplicates)"
        )
    else:
        logger.info(
            f"  Deduplication: already complete ({len(all_records)} records in memory)"
        )

    # ── Step 4: Score ─────────────────────────────────────────────────────────
    if not progress.is_step_complete("scored"):
        progress.write_checkpoint("scoring", {"total": len(all_records)})
        all_records = await score_papers(all_records, config, progress)
        all_records = apply_auto_rules(all_records, config)
        errors = sum(
            1
            for r in all_records
            if r.agent_notes and "SCORING_ERROR" in (r.agent_notes or "")
        )
        progress.write_checkpoint(
            "scored", {"total": len(all_records), "errors": errors}
        )
        logger.info(
            f"✓ Scoring: {len(all_records)} papers scored ({errors} errors flagged for review)"
        )
    else:
        logger.info("  Scoring: already complete")

    # ── Step 5: Coverage check + supplementary queries ────────────────────────
    if not progress.is_step_complete("coverage_checked"):
        undercovered = _check_section_coverage(all_records, config)
        if undercovered:
            logger.info(
                f"  Section undercoverage detected: {undercovered} — "
                "running supplementary queries"
            )
            for section_tag in undercovered:
                supp_queries = build_supplementary_queries(section_tag, config)
                supp_records: list[PaperRecord] = []

                for db_name, db_qs in supp_queries.items():
                    supp_db = config.db_by_name(db_name)
                    if not supp_db or not supp_db.enabled:
                        continue
                    db = supp_db
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
                    supp_scored = await score_papers(supp_records, config, progress)
                    supp_scored = apply_auto_rules(supp_scored, config)
                    # Replace un-scored supplementary records with scored versions
                    supp_titles = {r.title for r in supp_scored}
                    all_records = [r for r in all_records if r.title not in supp_titles]
                    all_records.extend(supp_scored)
                    logger.info(
                        f"  Supplementary: +{len(supp_scored)} records for {section_tag}"
                    )

        progress.write_checkpoint("coverage_checked", {"undercovered": undercovered})

    # ── Step 6: Print coverage summary ────────────────────────────────────────
    _print_coverage(all_records, config)

    # ── Step 7: Write to Zotero ───────────────────────────────────────────────
    if not progress.is_step_complete("zotero_written"):
        if config.output.zotero.enabled:
            try:
                n_written = write_to_zotero(all_records, config)
                progress.write_checkpoint("zotero_written", {"written": n_written})
                logger.info(f"✓ Zotero: {n_written} papers written")
            except Exception as e:
                logger.error(f"Zotero write failed — {e} — falling back to Excel only")
        else:
            logger.info("  Zotero: disabled in config")
    else:
        logger.info("  Zotero: already written")

    # ── Step 8: Write to Excel ────────────────────────────────────────────────
    if not progress.is_step_complete("excel_written"):
        try:
            write_to_excel(all_records, config)
            progress.write_checkpoint(
                "excel_written", {"path": config.output.excel.path}
            )
            logger.info(f"✓ Excel: written to {config.output.excel.path}")
        except Exception as e:
            logger.error(f"Excel write failed — {e}")
    else:
        logger.info("  Excel: already written")

    # ── Results tallies ───────────────────────────────────────────────────────
    n_include = sum(1 for r in all_records if r.inclusion_decision == "include")
    n_maybe = sum(1 for r in all_records if r.inclusion_decision == "maybe")
    n_exclude = sum(1 for r in all_records if r.inclusion_decision == "exclude")

    by_kunze: dict[str, int] = defaultdict(int)
    for r in all_records:
        if r.inclusion_decision in ("include", "maybe") and r.kunze_dimension:
            by_kunze[r.kunze_dimension] += 1

    conf_counts: dict[str, int] = defaultdict(int)
    for r in all_records:
        if r.cluster_assignment_confidence:
            conf_counts[r.cluster_assignment_confidence] += 1

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
        target_min = sec.target_min
        count = sum(
            1
            for r in included
            if sec.section_tag in [r.primary_section, *r.secondary_sections]
        )
        if count < target_min * config.edge_cases.section_undercoverage_threshold:
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
  Candidates retrieved (total):  {len(records)}

  INCLUDED:  {n_include} papers  →  Zotero + Excel
  MAYBE:     {n_maybe} papers  →  Zotero + Excel (flagged for review)
  EXCLUDED:  {n_exclude} papers  →  Excel only

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
