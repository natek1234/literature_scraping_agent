from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import yaml
from loguru import logger


class ConfigError(Exception):
    pass


# ── Sub-configs ───────────────────────────────────────────────────────────────


@dataclass
class DatabaseConfig:
    name: str
    type: str
    priority: int
    enabled: bool
    api: str | None = None
    categories: list[str] = field(default_factory=list)
    max_results_per_query: int = 100
    login_method: str | None = None
    credential_env_vars: dict[str, str] = field(default_factory=dict)
    note: str | None = None


@dataclass
class ScoringDimension:
    weight: float
    description: str


@dataclass
class ScoringDimensions:
    section_fit: ScoringDimension
    contribution_quality: ScoringDimension
    recency_and_relevance: ScoringDimension


@dataclass
class ScoringThresholds:
    include: float
    maybe: float


@dataclass
class VenueBonus:
    apply: bool
    venues: list[str]
    bonus: float
    cap_at: float = 10.0


@dataclass
class ScoringConfig:
    dimensions: ScoringDimensions
    thresholds: ScoringThresholds
    venue_bonus: VenueBonus
    auto_include_rules: list[dict[str, Any]]
    auto_exclude_rules: list[dict[str, Any]]
    parallel_batch_size: int = 10


@dataclass
class DeduplicationConfig:
    primary_key: str = "DOI"
    fallback_key: str = "title_fuzzy_match"
    fuzzy_threshold: float = 0.92


@dataclass
class ZoteroOutputConfig:
    enabled: bool
    collection_name: str
    subcollections: list[str]
    add_abstract_note: bool = True


@dataclass
class ExcelOutputConfig:
    enabled: bool
    path: str
    sheets: dict[str, Any] = field(default_factory=dict)


@dataclass
class OutputConfig:
    zotero: ZoteroOutputConfig
    excel: ExcelOutputConfig
    progress_file: str = "./outputs/sourcing-progress.txt"
    log_file: str = "./outputs/sourcing-log.txt"
    query_log: str = "./outputs/query-strings.txt"


@dataclass
class SectionConfig:
    title: str
    section_tag: str
    target_paper_count: str  # e.g. "10-20"
    kunze_dimension: str | None = None

    @property
    def target_min(self) -> int:
        return int(str(self.target_paper_count).split("-")[0])


@dataclass
class FilterConfig:
    default_start_year: int = 2015
    default_end_year: int = 2026
    s2_start_year: int = 1960
    publication_types_include: list[str] = field(default_factory=list)
    tier_1_venues: list[str] = field(default_factory=list)
    tier_2_venues: list[str] = field(default_factory=list)


@dataclass
class EdgeCaseConfig:
    section_undercoverage_threshold: float = 0.5
    min_papers_per_cluster: int = 3


# ── Root config ───────────────────────────────────────────────────────────────


@dataclass
class Config:
    project_id: str
    project_title: str
    zotero_collection: str
    research_question: str
    keywords_tier_1: list[str]
    keywords_tier_2: dict[str, list[str]]
    keywords_tier_3: list[str]
    databases: list[DatabaseConfig]
    filters: FilterConfig
    relevance_scoring: ScoringConfig
    technique_cluster_list: dict[str, list[str]]
    deduplication: DeduplicationConfig
    output: OutputConfig
    paper_structure: dict[str, SectionConfig]
    edge_cases: EdgeCaseConfig

    @classmethod
    def from_file(cls, path: str = "CONTEXT.md") -> Config:
        with open(path, encoding="utf-8") as f:
            raw = yaml.safe_load(f)

        if raw is None:
            raise ConfigError("CONTEXT.md is empty or invalid YAML")

        _require(raw, "RESEARCH_QUESTION")
        _require(raw, "KEYWORDS")
        _require(raw, "DATABASES")
        _require(raw, "RELEVANCE_SCORING")
        _require(raw, "ANALYTICAL_FRAMEWORK")

        if not raw["KEYWORDS"].get("tier_1"):
            raise ConfigError("KEYWORDS.tier_1 must have at least one entry")

        enabled_dbs = [d for d in raw["DATABASES"] if d.get("enabled", False)]
        if not enabled_dbs:
            raise ConfigError("DATABASES: at least one must have enabled: true")

        scoring_raw = raw["RELEVANCE_SCORING"]
        thresholds_raw = scoring_raw.get("thresholds", {})
        for field_name in ("include", "maybe"):
            if field_name not in thresholds_raw:
                raise ConfigError(
                    f"RELEVANCE_SCORING.thresholds.{field_name} is required"
                )

        af = raw["ANALYTICAL_FRAMEWORK"]
        cluster_list = af.get("S4_READINESS_MATRIX", {}).get("technique_cluster_list")
        if not cluster_list:
            raise ConfigError(
                "ANALYTICAL_FRAMEWORK.S4_READINESS_MATRIX.technique_cluster_list is required"
            )

        # ── Databases ─────────────────────────────────────────────────────────
        databases = [
            DatabaseConfig(
                name=db["name"],
                type=db.get("type", "open_access_api"),
                priority=db.get("priority", 99),
                enabled=db.get("enabled", False),
                api=db.get("api"),
                categories=db.get("categories", []),
                max_results_per_query=db.get("max_results_per_query", 100),
                login_method=db.get("login_method"),
                credential_env_vars=db.get("credential_env_vars", {}),
                note=db.get("note"),
            )
            for db in raw["DATABASES"]
        ]

        # ── Scoring ───────────────────────────────────────────────────────────
        dims_raw = scoring_raw.get("dimensions", {})
        dimensions = ScoringDimensions(
            section_fit=ScoringDimension(
                weight=float(dims_raw.get("section_fit", {}).get("weight", 0.55)),
                description=str(dims_raw.get("section_fit", {}).get("description", "")),
            ),
            contribution_quality=ScoringDimension(
                weight=float(
                    dims_raw.get("contribution_quality", {}).get("weight", 0.30)
                ),
                description=str(
                    dims_raw.get("contribution_quality", {}).get("description", "")
                ),
            ),
            recency_and_relevance=ScoringDimension(
                weight=float(
                    dims_raw.get("recency_and_relevance", {}).get("weight", 0.15)
                ),
                description=str(
                    dims_raw.get("recency_and_relevance", {}).get("description", "")
                ),
            ),
        )
        vb_raw = scoring_raw.get("venue_bonus", {})
        relevance_scoring = ScoringConfig(
            dimensions=dimensions,
            thresholds=ScoringThresholds(
                include=float(thresholds_raw["include"]),
                maybe=float(thresholds_raw["maybe"]),
            ),
            venue_bonus=VenueBonus(
                apply=bool(vb_raw.get("apply", False)),
                venues=vb_raw.get("venues", []),
                bonus=float(vb_raw.get("bonus", 0.0)),
                cap_at=float(vb_raw.get("cap_at", 10.0)),
            ),
            auto_include_rules=scoring_raw.get("auto_include_rules", []),
            auto_exclude_rules=scoring_raw.get("auto_exclude_rules", []),
            parallel_batch_size=int(scoring_raw.get("parallel_batch_size", 10)),
        )

        # ── Filters ───────────────────────────────────────────────────────────
        flt = raw.get("FILTERS", {})
        date_flt = flt.get("date", {})
        sec_ov = date_flt.get("section_overrides", {})
        pub_types = flt.get("publication_types", {})
        venues_prio = flt.get("publication_venues_priority", {})
        filters = FilterConfig(
            default_start_year=int(date_flt.get("default_start_year", 2015)),
            default_end_year=int(date_flt.get("default_end_year", 2026)),
            s2_start_year=int(sec_ov.get("S2_history", {}).get("start_year", 1960)),
            publication_types_include=pub_types.get("include", []),
            tier_1_venues=venues_prio.get("tier_1", []),
            tier_2_venues=venues_prio.get("tier_2", []),
        )

        # ── Technique clusters ────────────────────────────────────────────────
        technique_clusters: dict[str, list[str]] = {}
        for dim_key, clusters in cluster_list.items():
            if isinstance(clusters, list):
                technique_clusters[dim_key] = clusters

        # ── Output ────────────────────────────────────────────────────────────
        out = raw.get("OUTPUT", {})
        zr = out.get("zotero", {})
        er = out.get("excel", {})
        output_cfg = OutputConfig(
            zotero=ZoteroOutputConfig(
                enabled=bool(zr.get("enabled", True)),
                collection_name=str(
                    zr.get("collection_name", "SpaceAutonomy_Review_2026")
                ),
                subcollections=zr.get("subcollections", []),
                add_abstract_note=bool(zr.get("add_abstract_note", True)),
            ),
            excel=ExcelOutputConfig(
                enabled=bool(er.get("enabled", True)),
                path=str(er.get("path", "./outputs/sourcing_results.xlsx")),
                sheets=er.get("sheets", {}),
            ),
            progress_file=str(
                out.get("progress_file", "./outputs/sourcing-progress.txt")
            ),
            log_file=str(out.get("log_file", "./outputs/sourcing-log.txt")),
            query_log=str(out.get("query_log", "./outputs/query-strings.txt")),
        )

        # ── Deduplication ─────────────────────────────────────────────────────
        dedup = raw.get("DEDUPLICATION", {})
        dedup_cfg = DeduplicationConfig(
            primary_key=str(dedup.get("primary_key", "DOI")),
            fallback_key=str(dedup.get("fallback_key", "title_fuzzy_match")),
            fuzzy_threshold=float(dedup.get("fuzzy_threshold", 0.92)),
        )

        # ── Paper structure ───────────────────────────────────────────────────
        paper_structure = _extract_sections(raw.get("PAPER_STRUCTURE", {}))

        # ── Edge cases ────────────────────────────────────────────────────────
        ec = raw.get("EDGE_CASES", {})
        edge_cases = EdgeCaseConfig(
            section_undercoverage_threshold=float(
                ec.get("section_undercoverage", {}).get("threshold", 0.5)
            ),
            min_papers_per_cluster=int(
                ec.get("cluster_underpopulation", {}).get(
                    "minimum_papers_per_cluster", 3
                )
            ),
        )

        # ── Keywords ─────────────────────────────────────────────────────────
        kw = raw.get("KEYWORDS", {})
        tier_2_clusters_raw = kw.get("tier_2", {}).get("clusters", {})
        tier_2: dict[str, list[str]] = {
            k: v for k, v in tier_2_clusters_raw.items() if isinstance(v, list)
        }

        config = cls(
            project_id=str(raw.get("PROJECT_ID", "")),
            project_title=str(raw.get("PROJECT_TITLE", "")),
            zotero_collection=str(
                raw.get("ZOTERO_COLLECTION", "SpaceAutonomy_Review_2026")
            ),
            research_question=str(raw.get("RESEARCH_QUESTION", "")),
            keywords_tier_1=kw.get("tier_1", []),
            keywords_tier_2=tier_2,
            keywords_tier_3=kw.get("tier_3", []),
            databases=databases,
            filters=filters,
            relevance_scoring=relevance_scoring,
            technique_cluster_list=technique_clusters,
            deduplication=dedup_cfg,
            output=output_cfg,
            paper_structure=paper_structure,
            edge_cases=edge_cases,
        )

        n_clusters = sum(len(v) for v in technique_clusters.values())
        n_dims = len(technique_clusters)
        logger.info(
            f"Config loaded: {config.project_title}\n"
            f"  Databases enabled: {sum(1 for d in databases if d.enabled)}"
            f" ({', '.join(d.name for d in databases if d.enabled)})\n"
            f"  Keyword clusters: {len(tier_2)}\n"
            f"  Technique clusters: {n_clusters} across {n_dims} dimensions\n"
            f"  Section targets: {len(paper_structure)} sections"
        )
        return config

    def db_by_name(self, name: str) -> DatabaseConfig | None:
        for db in self.databases:
            if db.name == name:
                return db
        return None

    def db_priority(self, source_database: str) -> int:
        db = self.db_by_name(source_database)
        return db.priority if db else 99


# ── Helpers ───────────────────────────────────────────────────────────────────


def _require(raw: dict, key: str) -> None:
    if key not in raw:
        raise ConfigError(f"Missing required CONTEXT.md field: {key}")


def _extract_sections(struct: dict) -> dict[str, SectionConfig]:
    result: dict[str, SectionConfig] = {}

    def _walk(node: Any, _depth: int = 0) -> None:
        if not isinstance(node, dict):
            return
        if "section_tag" in node:
            tag = str(node["section_tag"])
            result[tag] = SectionConfig(
                title=str(node.get("title", tag)),
                section_tag=tag,
                target_paper_count=str(node.get("target_paper_count", "10-20")),
                kunze_dimension=node.get("kunze_dimension"),
            )
        for v in node.values():
            _walk(v, _depth + 1)

    _walk(struct)
    return result
