from __future__ import annotations

import datetime
import os
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from ..config import Config

# Database-specific syntax maps
_AND: dict[str, str] = {
    "Semantic Scholar": "+",
    "arXiv": " AND ",
    "IEEE Xplore": " AND ",
    "Web of Science": " AND ",
    "Scopus": " AND ",
    "ACM Digital Library": " AND ",
    "NASA Technical Reports Server": " AND ",
}
_OR: dict[str, str] = {
    "Semantic Scholar": "|",
    "arXiv": " OR ",
    "IEEE Xplore": " OR ",
    "Web of Science": " OR ",
    "Scopus": " OR ",
    "ACM Digital Library": " OR ",
    "NASA Technical Reports Server": " OR ",
}


def build_queries(config: Config) -> dict[str, list[str]]:
    """
    Returns {database_name: [query_string, ...]}
    One query per tier-2 cluster per enabled database.
    Logs all generated query strings to outputs/query-strings.txt.
    """
    result: dict[str, list[str]] = {}
    log_lines: list[str] = [
        f"# Query log — {config.project_title}",
        f"# Generated: {datetime.datetime.utcnow().isoformat()}",
        "",
    ]

    enabled_dbs = [db for db in config.databases if db.enabled]

    for db in enabled_dbs:
        name = db.name
        or_op = _OR.get(name, " OR ")

        queries: list[str] = []
        log_lines.append(f"## {name}")
        log_lines.append("")

        for cluster_name, cluster_terms in config.keywords_tier_2.items():
            if not cluster_terms:
                continue

            if name in ("Semantic Scholar", "arXiv"):
                # S2 and arXiv both work best with natural language cluster terms.
                # S2 rejects complex boolean; arXiv's category filter (applied in
                # databases/arxiv.py) already scopes the discipline domain, so tier_1
                # boolean strings are redundant and produce 0 results when quoted.
                full_query = " ".join(cluster_terms[:6])
            else:
                and_op = _AND.get(name, " AND ")
                tier1_parts = [_quote(t, name) for t in config.keywords_tier_1]
                base_query = and_op.join(tier1_parts)
                cluster_part = f"({or_op.join(_quote(t, name) for t in cluster_terms)})"
                full_query = f"{base_query}{and_op}{cluster_part}"

            queries.append(full_query)
            log_lines.append(f"  [{cluster_name}]")
            log_lines.append(f"  {full_query}")
            log_lines.append("")

        result[name] = queries
        logger.debug(f"Built {len(queries)} queries for {name}")

    # Write query log
    _write_query_log(config, log_lines)
    total_queries = sum(len(v) for v in result.values())
    logger.info(
        f"Queries built: {total_queries} total across {len(result)} databases "
        f"({len(config.keywords_tier_2)} clusters x {len(result)} DBs)"
    )
    return result


def build_supplementary_queries(
    section_tag: str,
    config: Config,
) -> dict[str, list[str]]:
    """Build targeted supplementary queries for a single undercovered section."""
    cluster_map: dict[str, str] = {
        "S1:introduction": "space_history_cluster",
        "S2:history": "space_history_cluster",
        "S3:ai-in-space": "ai_space_cluster",
        "S3a:ai-space-robotics": "ai_space_cluster",
        "S3b:ai-spacecraft": "ai_space_cluster",
        "S4a:navigation": "navigation_cluster",
        "S4b:perception": "perception_cluster",
        "S4c:reasoning": "reasoning_cluster",
        "S4d:planning": "planning_cluster",
        "S4e:interaction": "interaction_cluster",
        "S4f:learning": "learning_cluster",
        "S4g:alignment": "alignment_cluster",
        "S5a:multimodality": "multimodal_cluster",
        "S5b:machine-brain": "machine_brain_cluster",
        "S5c:integration-protocols": "integration_cluster",
        "S6:future-directions": "future_cluster",
    }

    cluster_name = cluster_map.get(section_tag)
    if not cluster_name or cluster_name not in config.keywords_tier_2:
        logger.warning(f"No cluster mapping for section {section_tag}")
        return {}

    cluster_terms = config.keywords_tier_2[cluster_name]
    result: dict[str, list[str]] = {}

    enabled_dbs = [db for db in config.databases if db.enabled]
    for db in enabled_dbs:
        name = db.name
        and_op = _AND.get(name, " AND ")
        or_op = _OR.get(name, " OR ")
        tier1_parts = [_quote(t, name) for t in config.keywords_tier_1]
        base_query = and_op.join(tier1_parts)
        cluster_part = f"({or_op.join(_quote(t, name) for t in cluster_terms)})"
        result[name] = [f"{base_query}{and_op}{cluster_part}"]

    return result


# ── Helpers ───────────────────────────────────────────────────────────────────


def _quote(term: str, db_name: str) -> str:
    """Wrap multi-word terms in quotes for databases that support it.

    Terms containing boolean operators (OR/AND) are grouped in parens,
    not quoted — quoting them would treat OR as a literal word.
    """
    has_boolean = any(op in term for op in (" OR ", " AND ", " NOT "))
    if has_boolean:
        return f"({term})"
    if " " in term and db_name not in ("Semantic Scholar",):
        return f'"{term}"'
    return term


def _write_query_log(config: Config, lines: list[str]) -> None:
    log_path = config.output.query_log
    os.makedirs(os.path.dirname(log_path) or ".", exist_ok=True)
    with open(log_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    logger.info(f"Query log written to: {log_path}")
