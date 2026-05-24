# Literature Sourcing Agent — Pipeline Specification
# (Previously: SKILL.md — renamed to PIPELINE_SPEC.md to distinguish from
#  the slash command skill at .claude/skills/source-papers/SKILL.md)

---
name: literature-sourcing-pipeline
version: 2.0.0
description: >
  Searches multiple academic databases (open-access and paywalled),
  scores retrieved papers for relevance, tags each paper with its section,
  Kunze et al. (2018) dimension, and technique cluster, deduplicates,
  and stores structured metadata in Zotero subcollections and Excel.
  Designed as the sourcing stage of a two-agent literature review pipeline
  for the systematic review "Surveying AI in Robotics: Towards Autonomous
  Space Systems". Analytical backbone: Kunze et al. (2018) six-dimension
  framework (D1–D6) plus AI alignment subsection (S4g).
author: "Research Automation"
dependencies:
  - anthropic>=0.40.0        # Claude API for scoring
  - aiohttp>=3.10.0          # async HTTP for parallel database queries
  - httpx>=0.27.0            # alternative async client (Semantic Scholar)
  - requests>=2.32.0         # sync HTTP for simple queries
  - tenacity>=9.0.0          # retry logic with exponential backoff
  - playwright>=1.48.0       # browser automation for paywalled sources
  - feedparser>=6.0.11       # arXiv Atom XML parsing
  - openpyxl>=3.1.5          # Excel output
  - pyzotero>=1.5.18         # Zotero Web API
  - zotero-mcp-server>=0.3.0 # MCP server for Zotero (Claude Code integration)
  - rapidfuzz>=3.10.0        # fuzzy title deduplication
  - python-dotenv>=1.0.1     # .env file loading
  - pyyaml>=6.0.2            # CONTEXT.md YAML parsing
  - pydantic>=2.9.0          # PaperRecord and Config data models
  - loguru>=0.7.2            # structured logging
---


## Purpose & Scope

This specification describes the implementation of the literature sourcing
pipeline for the systematic review "Surveying AI in Robotics: Towards
Autonomous Space Systems". It does NOT describe the writing agent — that is
a separate project that reads from the Zotero library this pipeline populates.

The pipeline reads all configuration from `CONTEXT.md` and stores session
state in `./outputs/sourcing-progress.txt` so interrupted runs can be resumed
without re-querying databases. The primary analytical framework is the
Kunze et al. (2018) six-dimension taxonomy; every paper retrieved is tagged
with the section and Kunze dimension it serves, and S4 papers are additionally
assigned a technique cluster from the predefined list in CONTEXT.md.


## Core Pipeline Loop

```
READ CONTEXT.md + ANALYTICAL_FRAMEWORK (incl. technique cluster list)
    ↓
VALIDATE required fields and load technique clusters into working memory
    ↓
BUILD QUERY STRINGS (per tier-2 cluster, per enabled database)
    ↓
LOG all query strings to outputs/query-strings.txt
    ↓
QUERY DATABASES (priority order: open-access first, then paywalled)
    ↓
NORMALISE all records to canonical PaperRecord schema
    ↓
DEDUPLICATE (DOI exact match → fuzzy title match fallback)
    ↓
SCORE IN PARALLEL BATCHES
  → section tag assignment (primary + up to 2 secondary)
  → Kunze dimension assignment (D1–D6 or "alignment")
  → technique cluster assignment + confidence
  → boolean metadata flag extraction
  → three-dimension scoring (section_fit, contribution_quality, recency)
  → weighted score computation + venue bonus
    ↓
APPLY AUTO-INCLUDE / AUTO-EXCLUDE RULES
    ↓
BUCKET: include / maybe / exclude
    ↓
CHECK SECTION COVERAGE
  → if any section < 50% of target: run supplementary queries for that section
    ↓
WRITE TO ZOTERO subcollections with full tag schema
    ↓
WRITE TO EXCEL (4 sheets: All Papers, Section Coverage,
                           Analytical Data, PRISMA Flow)
    ↓
WRITE PROGRESS FILE + QUERY LOG
```

Between each major step the pipeline writes a checkpoint. If interrupted,
it resumes from the last successful step without re-querying databases.


## Step 1 — Reading and Validating CONTEXT.md

Load and parse `CONTEXT.md` from the working directory into a typed `Config`
object (Pydantic BaseModel).

**Required fields — abort with `ConfigError` if missing:**
- `RESEARCH_QUESTION`
- `KEYWORDS.tier_1` (at least one entry)
- `DATABASES` (at least one entry with `enabled: true`)
- `RELEVANCE_SCORING.thresholds.include`
- `RELEVANCE_SCORING.thresholds.maybe`
- `ANALYTICAL_FRAMEWORK.S4_READINESS_MATRIX.technique_cluster_list`
- `PAPER_STRUCTURE` (all section entries with `section_tag` and `target_paper_count`)

**Load into working memory immediately:**
- The full technique cluster list (all dimensions D1–D6 + alignment clusters)
- The section tag list (S1 through S6 with all subsections)
- The Kunze dimension descriptions (D1–D6)

These three structures are injected into the scoring prompt at runtime.

**Optional fields with defaults:**
- `FILTERS.date` → no date restriction
- `FILTERS.publication_types` → all types
- `OUTPUT.zotero.enabled` → true (default for this project)
- `OUTPUT.excel.enabled` → true

Log a configuration summary at the start of the run:
```
Config loaded: <PROJECT_TITLE>
  Databases enabled: <N> (<list of names>)
  Keyword clusters: <N>
  Technique clusters: <N> across D1–D6 + alignment
  Section targets: <N> sections (total target: <sum of lower bounds> papers)
  Output: Zotero=<enabled/disabled> Excel=<enabled/disabled>
```


## Step 2 — Building Query Strings

Construct database-specific query strings from keyword tiers. Log all
generated strings verbatim to `outputs/query-strings.txt` with timestamps.

### Query construction logic

```
base_query = tier_1[0] AND tier_1[1] AND ...   # all tier-1 terms ANDed

For each tier_2 cluster:
    cluster_query = base_query AND (term_1 OR term_2 OR ...)

Final queries = one cluster_query per tier_2 cluster per enabled database
```

### Database-specific syntax translations

| Generic | Semantic Scholar | arXiv | IEEE Xplore | Web of Science | Scopus | ACM DL | NASA NTRS |
|---|---|---|---|---|---|---|---|
| AND | `+` | `AND` | `AND` | `AND` | `AND` | `AND` | `AND` |
| OR | `\|` | `OR` | `OR` | `OR` | `OR` | `OR` | `OR` |
| field:title | `title:` | `ti:` | `Document Title:` | `TI=` | `TITLE()` | `Title:` | `title:` |
| field:abstract | `abstract:` | `abs:` | `Abstract:` | `AB=` | `ABS()` | `Abstract:` | (full text search) |
| date range | `year` filter param | `submittedDate:` | `Publication Year:` | `PY=YYYY-YYYY` | `PUBYEAR AFT YYYY` | `PublicationDate:` | `publicationDate:` |

Note: PubMed and Europe PMC are **disabled** for this project (low yield for
CS/robotics). Do not generate queries for them. If encountered in the DATABASES
list with `enabled: false`, skip without warning.


## Step 3 — Querying Open-Access APIs

Query all enabled open-access databases before attempting paywalled sources.
Implement each client as an async class with a `search` method.

### Semantic Scholar (priority 1)

```python
BASE_URL = "https://api.semanticscholar.org/graph/v1/"

async def search(query: str, config: Config) -> list[PaperRecord]:
    params = {
        "query": query,
        "limit": config.max_results_per_query,
        "fields": "paperId,title,abstract,authors,year,venue,"
                  "citationCount,isOpenAccess,openAccessPdf,"
                  "externalIds,publicationTypes"
    }
    headers = {}
    if api_key := os.environ.get("S2_API_KEY"):
        headers["x-api-key"] = api_key
    # Rate limit: 10 req/sec without key, 100/sec with key
    # Use tenacity for 429 backoff
```

Extract: `paperId` → `s2_paper_id`, `externalIds.DOI` → `doi`,
`externalIds.ArXiv` → `arxiv_id`, `title`, `abstract`, `authors` (list of
`{name: str}`), `year`, `venue` → `venue`, `citationCount` → `citation_count`,
`openAccessPdf.url` → `open_access_pdf_url`.

### arXiv (priority 2)

```python
BASE_URL = "https://export.arxiv.org/api/query"

async def search(query: str, config: Config) -> list[PaperRecord]:
    # Build category-filtered query
    cat_filter = " OR ".join(
        f"cat:{c}" for c in ["cs.RO", "cs.AI", "cs.LG", "cs.SY"]
    )
    full_query = f"({query}) AND ({cat_filter})"
    params = {
        "search_query": full_query,
        "max_results": config.max_results_per_query,
        "sortBy": "relevance"
    }
    # Returns Atom XML — parse with feedparser
```

Extract from Atom: `id` → `arxiv_id` (strip URL prefix),
`title`, `summary` → `abstract`, `author` entries → `authors`,
`published` year → `year`, `arxiv:journal_ref` → `venue` (if present),
`link[@type='application/pdf']` → `open_access_pdf_url`.

### NASA Technical Reports Server (priority 7)

```python
BASE_URL = "https://ntrs.nasa.gov/api/citations/search"

async def search(query: str, config: Config) -> list[PaperRecord]:
    params = {
        "q": query,
        "rows": config.max_results_per_query,
        "start": 0  # paginate with offset
    }
    # Public API — no authentication required
    # Response: JSON with `results` list
```

Extract: `id` → `nasa_ntrs_id`, `title`, `abstract`, `authors` (list of
`{name}`), `publicationDate` year → `year`, `reportNumber` → as part of venue,
`disseminated` date → `retrieved_at`. NASA NTRS records often lack DOI —
use `nasa_ntrs_id` as the primary identifier for deduplication fallback.

**Important:** NASA NTRS records are primary sources for S2 and S3. They must
never be auto-excluded for missing abstract. Tag all NTRS records with
`source_type: "technical_report"` or `"mission_document"` as appropriate.

### Disabled databases

PubMed, Europe PMC, JSTOR — do not implement clients. If these appear in
CONTEXT.md with `enabled: false`, skip without warning. Log a note if
encountered with `enabled: true` as this would be a configuration error.


## Step 4 — Querying Paywalled Sources (Browser Automation)

Use Playwright to automate IEEE Xplore, Web of Science, Scopus, and ACM DL.
Credentials are loaded exclusively from `os.environ` — never from the Config
object or any file committed to version control.

```python
from playwright.async_api import async_playwright

async def scrape(db_config: dict, query: str,
                 config: Config) -> list[PaperRecord]:
    username_key = db_config["credential_env_vars"]["username"]
    password_key = db_config["credential_env_vars"]["password"]
    proxy_key = db_config["credential_env_vars"].get("proxy_url", "")

    username = os.environ.get(username_key, "")
    password = os.environ.get(password_key, "")
    proxy_url = os.environ.get(proxy_key, "") if proxy_key else ""

    if not username or not password:
        logger.warning(f"{db_config['name']}: credentials missing — skipping")
        return []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        try:
            if proxy_url:
                await page.goto(proxy_url)
                await page.fill("#username", username)
                await page.fill("#password", password)
                await page.click("button[type='submit']")
                await page.wait_for_load_state("networkidle")
            await page.goto(db_config["url"])
            # ... database-specific search and pagination
            await asyncio.sleep(3)  # minimum delay between page loads
        except Exception as e:
            logger.error(f"{db_config['name']}: browser error — {e}")
            return []
        finally:
            await browser.close()
```

**Hard constraints for browser automation:**
- Retrieve title, authors, abstract, and bibliographic metadata only
- Never attempt bulk PDF downloads
- Never attempt to bypass CAPTCHA — log and skip the page, continue
- Minimum 3-second delay between page loads
- If login fails for any reason: log the failure, return empty list,
  continue with remaining databases. Do not abort the pipeline.
- Maximum results per query: from `db_config.max_results_per_query`


## Step 5 — Normalising Metadata

After retrieval from any database, normalise all records to the canonical
`PaperRecord` Pydantic model. One normaliser function per source format.

### Canonical PaperRecord schema

```python
from pydantic import BaseModel, model_validator
import datetime

class PaperRecord(BaseModel):
    # ── Identifiers ──────────────────────────────────────────────────────
    doi: str | None = None
    arxiv_id: str | None = None
    s2_paper_id: str | None = None
    nasa_ntrs_id: str | None = None

    # ── Core metadata ────────────────────────────────────────────────────
    title: str
    abstract: str | None = None
    authors: list[str] = []         # ["Last, First", ...] or ["Full Name", ...]
    year: int | None = None
    venue: str | None = None        # journal name or conference name
    volume: str | None = None
    issue: str | None = None
    pages: str | None = None
    publication_type: str | None = None

    # ── Sourcing ─────────────────────────────────────────────────────────
    source_database: str
    retrieved_at: str               # ISO 8601
    open_access_pdf_url: str | None = None
    citation_count: int | None = None
    citations_per_year: float | None = None  # computed on init

    # ── Section assignment (populated by scorer) ─────────────────────────
    primary_section: str | None = None      # e.g. "S4c:reasoning"
    secondary_sections: list[str] = []
    kunze_dimension: str | None = None      # "D1"–"D6" | "alignment" | None
    technique_cluster: str | None = None
    cluster_assignment_confidence: str | None = None  # high|medium|low
    source_type: str | None = None          # primary_research|secondary_source|
                                            # technical_report|mission_document|
                                            # roadmap

    # ── Scoring (populated by scorer) ────────────────────────────────────
    section_fit_score: float | None = None
    contribution_score: float | None = None
    recency_score: float | None = None
    weighted_score: float | None = None
    inclusion_decision: str | None = None   # include|maybe|exclude
    agent_notes: str | None = None

    # ── Boolean metadata flags (populated by scorer) ─────────────────────
    is_cross_cutting: bool = False
    is_historical: bool = False
    space_heritage: bool = False
    deployment_constraints_discussed: bool = False
    compute_requirements_noted: bool = False
    radiation_robustness_discussed: bool = False
    operational_description_present: bool = False  # S2 papers only
    alignment_paper: bool = False
    compositional_alignment: bool = False
    general_alignment_robotics_context: bool = False

    # ── S2-specific ───────────────────────────────────────────────────────
    mission_or_system_name: str | None = None

    # ── Utility ──────────────────────────────────────────────────────────
    abstract_snippet: str | None = None     # first 300 chars of abstract

    @model_validator(mode='after')
    def compute_derived_fields(self):
        # citations_per_year
        if self.citation_count is not None and self.year is not None:
            age = max(datetime.date.today().year - self.year + 0.5, 0.5)
            self.citations_per_year = round(self.citation_count / age, 1)
        # abstract_snippet
        if self.abstract and not self.abstract_snippet:
            self.abstract_snippet = self.abstract[:300]
        return self
```

**Normaliser requirements:**
- All fields populated to the extent the source provides
- `title` must always be populated; raise if absent
- `source_database` must always be set to the database name
- `retrieved_at` must be an ISO 8601 timestamp at the time of retrieval
- Log any fields that cannot be extracted as DEBUG-level messages


## Step 6 — Deduplication

```python
from rapidfuzz import fuzz

def deduplicate(records: list[PaperRecord],
                config: Config) -> list[PaperRecord]:

    # 1. DOI exact match (primary key)
    by_doi: dict[str, PaperRecord] = {}
    no_doi: list[PaperRecord] = []
    doi_dupe_count = 0

    for record in records:
        if record.doi:
            if record.doi in by_doi:
                doi_dupe_count += 1
                # Keep record from higher-priority database
                existing = by_doi[record.doi]
                if _db_priority(record, config) < _db_priority(existing, config):
                    # Carry arxiv_id from preprint to published version
                    if record.arxiv_id and not existing.arxiv_id:
                        existing.arxiv_id = record.arxiv_id
                    by_doi[record.doi] = record
            else:
                by_doi[record.doi] = record
        else:
            no_doi.append(record)

    # 2. Fuzzy title match (fallback for records without DOI)
    seen: list[PaperRecord] = list(by_doi.values())
    fuzzy_dupe_count = 0

    for record in no_doi:
        is_dupe = False
        for existing in seen:
            similarity = fuzz.ratio(
                record.title.lower(), existing.title.lower()
            )
            if similarity >= config.deduplication.fuzzy_threshold * 100:
                is_dupe = True
                fuzzy_dupe_count += 1
                # Merge arxiv_id if available
                if record.arxiv_id and not existing.arxiv_id:
                    existing.arxiv_id = record.arxiv_id
                break
        if not is_dupe:
            seen.append(record)

    logger.info(
        f"Deduplication: {doi_dupe_count} DOI dupes, "
        f"{fuzzy_dupe_count} fuzzy title dupes removed. "
        f"Unique: {len(seen)}"
    )
    return seen
```


## Step 7 — Relevance Scoring

Score papers in parallel async batches. The scoring prompt is the
authoritative definition of what the scorer extracts — every field in
the response JSON must map to a `PaperRecord` field.

### Scoring prompt

```
SYSTEM:
You are a research librarian screening papers for a systematic literature
review. Score and tag each paper based on the criteria below. Return ONLY
valid JSON — no preamble, no markdown fences, no trailing text.

USER:
REVIEW TITLE: {config.project_title}

RESEARCH QUESTION:
{config.research_question}

SECTION TAXONOMY (assign the best-fit primary section):
  S1:introduction      — Stakes, communication latency, autonomy motivation
  S2:history           — Historical space missions, capability evolution
  S3:ai-in-space       — Deployed/near-deployment AI in space systems
    S3a:ai-space-robotics — Rovers, arms, onboard science autonomy
    S3b:ai-spacecraft     — Fault detection, scheduling, onboard processing
  S4a:navigation    (D1) — SLAM, visual odometry, path planning, traversability
  S4b:perception    (D2) — Object recognition, VLMs, sensor fusion, anomaly detection
  S4c:reasoning     (D3) — PDDL, behaviour trees, LLM task planning, knowledge graphs
  S4d:planning      (D4) — Hierarchical planning, LLM policy, evolutionary methods
  S4e:interaction   (D5) — Shared autonomy, HRI, delayed teleoperation, safety
  S4f:learning      (D6) — RL control, imitation learning, sim-to-real, continual learning
  S4g:alignment         — AI alignment in robotic systems:
                          specification gaming, goal misgeneralisation, proxy collapse,
                          compositional misalignment in modular systems,
                          scalable oversight, alignment in space robotics
  S5a:multimodality     — Foundation models for robotics (RT-2, PaLM-E, VLAs)
  S5b:machine-brain     — Cognitive architectures, SNNs, embodied cognition
  S5c:integration-protocols — ROS/ROS2 middleware, MCP, A2A, inter-module comms
  S6:future-directions  — Roadmaps, safety/alignment gaps, evaluation frameworks

KUNZE DIMENSION (for S4 papers only — assign D1–D6 or "alignment"):
  D1: Navigation & Mapping
  D2: Perception
  D3: Knowledge Representation & Reasoning
  D4: Planning
  D5: Interaction (HRI, shared autonomy, safety)
  D6: Learning (RL, continual learning, sim-to-real)
  alignment: AI alignment subsection (S4g) — cross-cutting D5/D6
  null: for all non-S4 sections

TECHNIQUE CLUSTERS (for S4/S4g papers — assign best-fit from this list):
  D1: visual_odometry | lidar_slam | learning_based_navigation |
      terrain_traversability | path_planning_classical | multi_sensor_fusion_nav
  D2: object_recognition_deep_learning | visual_language_models |
      3d_scene_understanding | sensor_fusion_perception | anomaly_detection
  D3: classical_planning_pddl | behaviour_trees | llm_task_planning |
      neuro_symbolic_reasoning | knowledge_graphs_robotics
  D4: llm_policy_generation | hierarchical_task_planning |
      evolutionary_policy_search | model_predictive_control |
      behaviour_tree_llm_hybrid
  D5: shared_autonomy_frameworks | natural_language_hri |
      delayed_teleoperation | adaptive_autonomy | robot_safety_ethics
  D6: reinforcement_learning_control | imitation_learning |
      sim_to_real_transfer | continual_lifelong_learning |
      meta_learning | online_learning_deployment
  alignment: specification_gaming_reward_hacking | goal_misgeneralisation |
             proxy_collapse | compositional_misalignment_modular |
             scalable_oversight_robotics | inter_module_diagnostic_oversight |
             embodied_ai_safety_evaluation | alignment_space_robotics

EXCLUSIONS (do not include these):
  - Pure hardware/mechanical engineering without AI component
  - Autonomous road vehicles without transferable robotics contribution
  - UAVs/drones without ground robotics or space application
  - Medical robotics unless HRI or shared autonomy is primary contribution
  - NLP/LLM papers without physical robot application

PAPER TO SCORE:
  Title:          {paper.title}
  Abstract:       {paper.abstract or "[No abstract available]"}
  Year:           {paper.year}
  Venue:          {paper.venue}
  Source:         {paper.source_database}
  Citation count: {paper.citation_count}

SCORING INSTRUCTIONS:
Score each dimension 1.0–10.0 (one decimal place).

section_fit: Does this paper directly serve at least one section?
  10 = directly serves with a specific citable claim or data point.
  5  = generally relevant but no clear section fit.
  1  = not relevant.

contribution_quality: Substantive empirical, architectural, or analytical
  contribution? Real robot experiments or confirmed space mission heritage
  score highest (9–10). Position paper or opinion piece: 3–5.
  Highly cited survey that anchors a section: 7–8.

recency_score: Is this paper current enough for its purpose?
  For S2 (history) papers only: score 10.0 regardless of age if the paper
  contains historically significant operational data about a space mission.
  For all other sections: 2025–2026=10, 2023–2024=9, 2021–2022=7,
  2019–2020=5, 2017–2018=4, pre-2017=3.

Return ONLY this JSON (no other text):
{
  "primary_section": "<section_tag>",
  "secondary_sections": ["<tag>", "<tag>"],
  "kunze_dimension": "<D1|D2|D3|D4|D5|D6|alignment|null>",
  "technique_cluster": "<cluster_name or null>",
  "cluster_assignment_confidence": "<high|medium|low|null>",
  "source_type": "<primary_research|secondary_source|technical_report|mission_document|roadmap>",
  "section_fit_score": 0.0,
  "contribution_score": 0.0,
  "recency_score": 0.0,
  "is_historical": false,
  "space_heritage": false,
  "deployment_constraints_discussed": false,
  "compute_requirements_noted": false,
  "radiation_robustness_discussed": false,
  "operational_description_present": false,
  "alignment_paper": false,
  "compositional_alignment": false,
  "general_alignment_robotics_context": false,
  "mission_or_system_name": null,
  "agent_notes": "<one sentence: why this primary section? summarise scores>"
}
```

### Post-scoring computation (Python, not Claude)

```python
def compute_weighted_score(record: PaperRecord, config: Config) -> float:
    dims = config.relevance_scoring.dimensions
    raw = (
        (record.section_fit_score or 0.0)  * dims.section_fit.weight +
        (record.contribution_score or 0.0) * dims.contribution_quality.weight +
        (record.recency_score or 0.0)      * dims.recency_and_relevance.weight
    )
    # Venue bonus
    if record.venue and any(
        v.lower() in record.venue.lower()
        for v in config.relevance_scoring.venue_bonus.venues
    ):
        raw = min(raw + config.relevance_scoring.venue_bonus.bonus, 10.0)
    return round(raw, 2)
```

### Scoring error handling

| Failure | Action |
|---|---|
| JSON parse failure | scores → 0.0; `inclusion_decision` → "maybe"; `agent_notes` → "SCORING_ERROR: JSON parse failed"; continue |
| Unexpected JSON field | ignore silently; map known fields; continue |
| API 429 rate limit | tenacity exponential backoff; max 5 retries; then scoring_error state |
| No abstract available | score normally; cap `section_fit_score` at 6.0 UNLESS `source_type` is `technical_report` or `mission_document` |
| `kunze_dimension` is null for S4 paper | flag as scoring_error; set to "maybe"; log as WARNING |

### Batch execution

```python
async def score_papers(records: list[PaperRecord],
                       config: Config,
                       progress: ProgressTracker) -> list[PaperRecord]:
    batch_size = config.relevance_scoring.parallel_batch_size
    all_scored: list[PaperRecord] = []

    for i in range(0, len(records), batch_size):
        batch = records[i : i + batch_size]
        tasks = [score_single(paper, config) for paper in batch]
        scored = await asyncio.gather(*tasks, return_exceptions=False)
        all_scored.extend(scored)
        progress.write_checkpoint("scoring",
                                  {"last_batch_index": i + batch_size,
                                   "scored_so_far": len(all_scored)})
    return all_scored
```


## Step 8 — Apply Auto-Rules and Bucket Papers

```python
def assign_inclusion(record: PaperRecord, config: Config) -> PaperRecord:
    # 1. Auto-exclude rules (applied first)
    for rule in config.relevance_scoring.auto_exclude_rules:
        if evaluate_condition(rule["condition"], record):
            record.inclusion_decision = "exclude"
            record.agent_notes = (
                f"{record.agent_notes or ''} "
                f"[AUTO-EXCLUDED: {rule['condition']}]"
            ).strip()
            return record

    # 2. Special case: NASA/ESA technical reports → always include
    if record.source_type in ("technical_report", "mission_document"):
        if record.source_database == "NASA NTRS":
            record.inclusion_decision = "include"
            record.agent_notes = (
                f"{record.agent_notes or ''} [AUTO-INCLUDED: NASA NTRS mission document]"
            ).strip()
            return record

    # 3. Auto-include rules
    for rule in config.relevance_scoring.auto_include_rules:
        if evaluate_condition(rule["condition"], record):
            record.inclusion_decision = "include"
            record.agent_notes = (
                f"{record.agent_notes or ''} "
                f"[AUTO-INCLUDED: {rule['condition']}]"
            ).strip()
            return record

    # 4. Standard threshold bucketing
    score = record.weighted_score or 0.0
    thresholds = config.relevance_scoring.thresholds
    if score >= thresholds.include:
        record.inclusion_decision = "include"
    elif score >= thresholds.maybe:
        record.inclusion_decision = "maybe"
    else:
        record.inclusion_decision = "exclude"

    return record
```


## Step 9 — Section Coverage Check

After bucketing, check whether each section has reached 50% of its target
paper count. If not, run a supplementary targeted query for that section.

```python
def check_section_coverage(
    records: list[PaperRecord],
    config: Config
) -> list[str]:
    """Returns list of section tags that are undercovered."""
    undercovered = []
    included = [r for r in records if r.inclusion_decision == "include"]

    for section_id, section_config in config.paper_structure.items():
        section_tag = section_config.section_tag
        target_min = int(section_config.target_paper_count.split("-")[0])
        count = sum(
            1 for r in included
            if section_tag in ([r.primary_section] + r.secondary_sections)
        )
        if count < target_min * 0.5:
            logger.warning(
                f"Section {section_tag}: {count} included / "
                f"target {target_min}+ — running supplementary query"
            )
            undercovered.append(section_tag)

    return undercovered
```

For each undercovered section, run the section-specific keyword cluster
queries across all enabled databases, score the new results, and merge into
the main corpus (re-run deduplication after merging). Log all supplementary
queries as second-pass searches in `outputs/query-strings.txt`.


## Step 10 — Writing to Zotero

Write `include` and `maybe` papers to the Zotero library. Excluded papers
are not written to Zotero.

```python
def write_to_zotero(records: list[PaperRecord], config: Config) -> None:
    z = get_zotero_client()  # from pyzotero, credentials from env

    # Ensure top-level collection exists
    collection_key = ensure_collection(z, config.output.zotero.collection_name)

    # Ensure all subcollections exist
    subcollection_keys = {}
    for subcollection_name in config.output.zotero.subcollections:
        subcollection_keys[subcollection_name] = ensure_subcollection(
            z, collection_key, subcollection_name
        )

    for record in records:
        if record.inclusion_decision not in ("include", "maybe"):
            continue

        item = {
            "itemType": infer_item_type(record.publication_type),
            "title": record.title,
            "abstractNote": record.abstract or "",
            "date": str(record.year or ""),
            "DOI": record.doi or "",
            "url": record.open_access_pdf_url or "",
            "publicationTitle": record.venue or "",
            "creators": [
                {"creatorType": "author", "name": author}
                for author in record.authors
            ],
            "tags": build_tag_list(record, config),
            "collections": build_collection_list(record, subcollection_keys)
        }
        z.create_items([item])

        if config.output.zotero.add_abstract_note:
            add_abstract_note(z, item_key, record)
```

### Tag construction

```python
def build_tag_list(record: PaperRecord, config: Config) -> list[dict]:
    tags = []
    # Section tags
    if record.primary_section:
        tags.append({"tag": record.primary_section})
    for sec in record.secondary_sections:
        tags.append({"tag": sec})
    # Kunze dimension
    if record.kunze_dimension:
        tags.append({"tag": f"kunze:{record.kunze_dimension}"})
    # Technique cluster
    if record.technique_cluster:
        tags.append({"tag": f"cluster:{record.technique_cluster}"})
    # Confidence
    if record.cluster_assignment_confidence:
        tags.append({"tag": f"confidence:{record.cluster_assignment_confidence}"})
    # Source type
    if record.source_type:
        tags.append({"tag": f"type:{record.source_type}"})
    # Inclusion status
    tags.append({"tag": f"status:{record.inclusion_decision}"})
    # Source database
    tags.append({"tag": f"source:{record.source_database.lower().replace(' ', '_')}"})
    # Venue tier
    tier = get_venue_tier(record.venue, config)
    tags.append({"tag": f"venue:tier{tier}"})
    # Boolean flags
    bool_flags = [
        ("cross_cutting", record.is_cross_cutting),
        ("historical", record.is_historical),
        ("space_heritage", record.space_heritage),
        ("deployment_constraints", record.deployment_constraints_discussed),
        ("compute_noted", record.compute_requirements_noted),
        ("radiation_noted", record.radiation_robustness_discussed),
        ("alignment_paper", record.alignment_paper),
        ("compositional_alignment", record.compositional_alignment),
    ]
    for flag_name, flag_value in bool_flags:
        if flag_value:
            tags.append({"tag": flag_name})
    return tags
```

### Abstract note format

```python
def build_abstract_note(record: PaperRecord) -> str:
    return (
        f"<b>Abstract:</b><br>{record.abstract or '[Not available]'}<br><br>"
        f"<b>Primary Section:</b> {record.primary_section}<br>"
        f"<b>Kunze Dimension:</b> {record.kunze_dimension or 'N/A'}<br>"
        f"<b>Technique Cluster:</b> {record.technique_cluster or 'N/A'} "
        f"({record.cluster_assignment_confidence or 'N/A'} confidence)<br>"
        f"<b>Source Type:</b> {record.source_type}<br>"
        f"<b>Section Fit:</b> {record.section_fit_score} | "
        f"<b>Contribution:</b> {record.contribution_score} | "
        f"<b>Recency:</b> {record.recency_score}<br>"
        f"<b>Weighted Score:</b> {record.weighted_score}<br>"
        f"<b>Agent Notes:</b> {record.agent_notes}"
    )
```

### Subcollection placement

Place each paper in its `primary_section` subcollection. Duplicate into
`secondary_sections` subcollections (intentional — enables section-based
queries at the writing stage without requiring joins).


## Step 11 — Writing to Excel

Write four sheets using `openpyxl`:

**Sheet 1 — "All Papers"**
All records with full column set from CONTEXT.md. Colour coding:
- Include: `#C6EFCE` (green)
- Maybe: `#FFEB9C` (yellow)
- Exclude: `#FFC7CE` (red)

**Sheet 2 — "Section Coverage"**
Columns: `section_tag`, `section_title`, `kunze_dimension`,
`target_paper_count`, `included_count`, `maybe_count`,
`coverage_status` ("adequate" / "needs more"),
`cluster_confidence_high_pct` (S4/S4g sections only).

**Sheet 3 — "Analytical Data"** (four sub-tables)

*Tab 3a — S2 Mission Taxonomy:*
Rows: one per unique `mission_or_system_name`. Columns: mission name,
year_deployed, D1 through D6 (cell: brief operational description or blank).

*Tab 3b — S2 Deployment Lag:*
Rows: from S2 included papers where `space_heritage` is True.
Columns: `ai_capability`, `terrestrial_first_pub_year`,
`space_deployment_year`, `deployment_lag_years`, `evidence_paper`.

*Tab 3c — S4 Technique Cluster Summary:*
Rows: one per technique cluster. Columns: `kunze_dimension`,
`technique_cluster`, `paper_count`, `space_heritage_count`,
`deployment_constraints_count`, `compute_noted_count`,
`radiation_noted_count`, `high_confidence_pct`.

*Tab 3d — Bibliometric Trend:*
Rows: one per year (2015–2026). Columns: `year`, `S4a_count`, `S4b_count`,
`S4c_count`, `S4d_count`, `S4e_count`, `S4f_count`, `S4g_alignment_count`.

**Sheet 4 — "PRISMA Flow"**
Columns: `stage`, `database`, `count`.
Rows: records_identified (per DB), after_dedup (total), screened (total),
excluded_reason_database_query (count), excluded_reason_date (count),
excluded_reason_auto_exclude (count), excluded_reason_threshold (count),
included (total).


## Step 12 — Progress File Format

Write `outputs/sourcing-progress.txt` after every major step:

```yaml
RUN_ID: run_YYYYMMDD_HHMMSS
PROJECT: <PROJECT_TITLE>
STATUS: in_progress | complete | interrupted

STEPS_COMPLETED:
  config_loaded: true
  queries_built: true
  query_log_written: true
  semantic_scholar_queried: true   # retrieved: N
  arxiv_queried: true              # retrieved: N
  nasa_ntrs_queried: false
  ieee_queried: false
  wos_queried: false
  scopus_queried: false
  acm_queried: false
  normalised: true
  deduplicated: true               # unique: N; doi_dupes: N; fuzzy_dupes: N
  scored: true                     # total: N; errors: N
  bucketed: true
  coverage_checked: true
  supplementary_queries_run: false # sections: []
  zotero_written: false
  excel_written: false

PRISMA:
  semantic_scholar_identified: N
  arxiv_identified: N
  nasa_ntrs_identified: N
  ieee_identified: N
  wos_identified: N
  scopus_identified: N
  acm_identified: N
  after_dedup: N
  screened: N
  excluded: N
  included: N

SCORING:
  total: N
  scored: N
  errors: N
  last_batch_index: N

RESULTS:
  include: N
  maybe: N
  exclude: N
  by_kunze: {D1: N, D2: N, D3: N, D4: N, D5: N, D6: N, alignment: N}

CLUSTER_CONFIDENCE:
  high: N
  medium: N    # flag these for researcher review
  low: N       # flag these for researcher review

RESUME_FROM: <step_name>
```


## Error Handling Reference

| Error Condition | Action |
|---|---|
| Missing required CONTEXT field | Abort with `ConfigError` naming the field |
| Technique cluster list missing | Abort — cannot score without clusters |
| Database API rate limit (429) | Exponential backoff via tenacity, max 5 retries |
| Database API down / timeout | Skip database, log ERROR, continue with next |
| Browser login failure | Log WARNING with database name, return [], continue |
| CAPTCHA encountered | Log WARNING, skip that page, continue pagination |
| Abstract missing (non-NTRS) | Score on title only; cap section_fit at 6.0 |
| Abstract missing (NASA NTRS) | Score normally; no cap; tag as technical_report |
| Score JSON parse failure | scores → 0.0; decision → "maybe"; log ERROR; continue |
| `kunze_dimension` null for S4 | Log WARNING; set decision → "maybe"; flag in Excel |
| Cluster assignment confidence low | Flag in Section Coverage sheet; do not exclude |
| Section undercoverage (< 50%) | Run supplementary query; log in query-strings.txt |
| Zotero connection failure | Log ERROR; fall back to Excel output only |
| Zotero subcollection creation failure | Log WARNING; place in top-level collection |
| Session interrupt | Write checkpoint; exit cleanly; resume on next run |


## What This Specification Does NOT Cover

- Writing literature review prose → handled by a separate writing agent
- Downloading or storing full-text PDFs → writing agent handles this
- Synthesising or comparing papers → writing agent handles this
- ACS (Autonomy Characterisation Scale) level assignment → writing agent
- SDRR (Space Deployment Readiness Rubric) rating → writing agent
- Modifying any files outside `./outputs/` and `./src/`
