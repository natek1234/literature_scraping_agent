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

            if name in ("Semantic Scholar", "arXiv", "NASA Technical Reports Server"):
                full_query = _build_natural_query(name, cluster_terms)
            elif name == "Web of Science":
                full_query = _build_wos_query(config.keywords_tier_1, cluster_terms)
            elif name == "Scopus":
                full_query = _build_scopus_query(config.keywords_tier_1, cluster_terms)
            elif name in ("IEEE Xplore", "ACM Digital Library"):
                full_query = _build_ieee_query(config.keywords_tier_1, cluster_terms)
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
    """Build targeted supplementary queries for a single undercovered section.

    Returns one query per cluster per database. Sections may map to multiple
    clusters — the supplementary loop in main.py runs all of them.
    Returns {} for parent sections that have no targeted clusters.
    """
    _PARENT_SECTIONS = {"S4:ai-in-robotics", "S5:new-paradigms"}
    if section_tag in _PARENT_SECTIONS:
        logger.debug(
            f"Skipping supplementary queries for parent section {section_tag} "
            "— target the subsections directly"
        )
        return {}

    # 1:many mapping — each section may have multiple targeted clusters.
    # Sections with a single broad cluster keep a one-element list.
    cluster_map: dict[str, list[str]] = {
        "S1:introduction": ["space_history_cluster"],
        "S2:history": [
            "s2_early_space_computers",
            "s2_mars_rover_systems",
            "s2_modern_space_systems",
            "s2_space_robotics_surveys",
        ],
        "S3:ai-in-space": [
            "s3_deployed_rover_intelligence",
            "s3_spacecraft_autonomous_systems",
            "s3_near_deployment_systems",
        ],
        "S3a:ai-space-robotics": ["ai_space_cluster"],
        "S3b:ai-spacecraft": ["ai_space_cluster"],
        "S4a:navigation": ["navigation_cluster"],
        "S4b:perception": ["perception_cluster"],
        "S4c:reasoning": ["reasoning_cluster"],
        "S4d:planning": ["planning_cluster"],
        "S4e:interaction": ["interaction_cluster"],
        "S4f:learning": ["learning_cluster"],
        "S4g:alignment": [
            "alignment_foundation",
            "alignment_reward_specification",
            "alignment_emergent_agentic",
            "alignment_scalable_oversight",
            "alignment_safe_rl_robotics",
            "alignment_embodied_robotics",
        ],
        "S5a:multimodality": ["multimodal_cluster"],
        "S5b:machine-brain": ["machine_brain_cluster"],
        "S5c:integration-protocols": ["integration_cluster"],
        "S6:future-directions": ["future_cluster"],
    }

    cluster_names = cluster_map.get(section_tag)
    if not cluster_names:
        logger.warning(f"No cluster mapping for section {section_tag}")
        return {}

    result: dict[str, list[str]] = {}
    enabled_dbs = [db for db in config.databases if db.enabled]

    for cluster_name in cluster_names:
        if cluster_name not in config.keywords_tier_2:
            logger.warning(
                f"Cluster {cluster_name!r} not found in config "
                f"(section {section_tag}) — skipping"
            )
            continue

        cluster_terms = config.keywords_tier_2[cluster_name]

        for db in enabled_dbs:
            name = db.name
            if name in ("Semantic Scholar", "arXiv", "NASA Technical Reports Server"):
                result.setdefault(name, []).append(
                    _build_natural_query(name, cluster_terms)
                )
            elif name == "Web of Science":
                result.setdefault(name, []).append(
                    _build_wos_query(config.keywords_tier_1, cluster_terms)
                )
            elif name == "Scopus":
                result.setdefault(name, []).append(
                    _build_scopus_query(config.keywords_tier_1, cluster_terms)
                )
            elif name in ("IEEE Xplore", "ACM Digital Library"):
                result.setdefault(name, []).append(
                    _build_ieee_query(config.keywords_tier_1, cluster_terms)
                )
            else:
                and_op = _AND.get(name, " AND ")
                or_op = _OR.get(name, " OR ")
                tier1_parts = [_quote(t, name) for t in config.keywords_tier_1]
                base_query = and_op.join(tier1_parts)
                cluster_part = f"({or_op.join(_quote(t, name) for t in cluster_terms)})"
                result.setdefault(name, []).append(
                    f"{base_query}{and_op}{cluster_part}"
                )

    return result


# ── Helpers ───────────────────────────────────────────────────────────────────


def _build_natural_query(db_name: str, cluster_terms: list[str]) -> str:
    """Build a plain-text query for S2, arXiv, and NTRS.

    S2 and arXiv accept up to 6 natural-language terms joined by spaces.
    NTRS uses Elasticsearch in strict all-terms-must-match mode and returns
    zero results for queries longer than ~4 words, so we use only the first
    cluster term (a short 2-4 word phrase) as the entire query.
    """
    if db_name == "NASA Technical Reports Server":
        first = cluster_terms[0] if cluster_terms else ""
        return " ".join(first.split()[:4])
    return " ".join(cluster_terms[:6])


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


def _shorten_term(term: str, max_words: int = 3) -> str:
    """Trim long cluster phrases to max_words for boolean search.

    Long exact phrases (5-7 words) return near-zero results on WoS/Scopus/IEEE
    because the full phrase rarely appears verbatim in abstracts. Keeping ≤3
    words gives a short, quotable phrase with acceptable precision.
    """
    words = term.split()
    if len(words) <= max_words:
        return term
    return " ".join(words[:max_words])


def _format_term(term: str) -> str:
    """Quote multi-word short phrases; leave single words bare."""
    short = _shorten_term(term)
    return f'"{short}"' if " " in short else short


def _build_wos_query(tier1_terms: list[str], cluster_terms: list[str]) -> str:
    """WoS advanced search: TS= field tags, shortened cluster phrases.

    tier1_terms are full boolean expressions (e.g. "autonomous robot OR robotic
    autonomy OR autonomous robotics") — pass them through unchanged so the OR
    operators are not mangled by _format_term / _shorten_term.
    """
    t1 = " OR ".join(tier1_terms)
    cl = " OR ".join(_format_term(t) for t in cluster_terms)
    return f"TS=({t1}) AND TS=({cl})"


def _build_scopus_query(tier1_terms: list[str], cluster_terms: list[str]) -> str:
    """Scopus advanced search: TITLE-ABS-KEY() field tags, shortened cluster phrases."""
    t1 = " OR ".join(tier1_terms)
    cl = " OR ".join(_format_term(t) for t in cluster_terms)
    return f"TITLE-ABS-KEY({t1}) AND TITLE-ABS-KEY({cl})"


def _build_ieee_query(tier1_terms: list[str], cluster_terms: list[str]) -> str:
    """IEEE/ACM basic search: boolean OR groups, shortened cluster phrases."""
    t1 = " OR ".join(tier1_terms)
    cl = " OR ".join(_format_term(t) for t in cluster_terms)
    return f"({t1}) AND ({cl})"


def _write_query_log(config: Config, lines: list[str]) -> None:
    log_path = config.output.query_log
    os.makedirs(os.path.dirname(log_path) or ".", exist_ok=True)
    with open(log_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    logger.info(f"Query log written to: {log_path}")
