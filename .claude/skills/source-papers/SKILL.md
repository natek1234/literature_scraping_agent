---
name: source-papers
description: >
  Run the full literature sourcing pipeline. Reads CONTEXT.md, queries all
  enabled academic databases, scores papers for relevance, tags each paper
  with its section, Kunze dimension, and technique cluster, deduplicates,
  and writes results to Zotero subcollections and Excel. Use when starting
  a new sourcing run or re-running an existing project.
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
---

# /source-papers — Literature Sourcing Pipeline

You are executing the literature sourcing agent for this project.
Work through every phase below in order. Do not skip phases.
After each phase, write a checkpoint to `outputs/sourcing-progress.txt`.

The review is structured around the Kunze et al. (2018) six-dimension
framework. Every paper must be tagged with the section it serves AND,
for S4 papers, the Kunze dimension (D1–D6) and technique cluster.
The alignment subsection (S4g) is cross-cutting across D5/D6 — papers
assigned to S4g receive `kunze_dimension: "alignment"`.

---

## Phase 0 — Pre-flight checks

Before writing a single line of source code, complete all of these checks.
If any check fails, stop and tell the user what needs to be fixed.

**Check 1 — CONTEXT.md exists and is valid**
Read `CONTEXT.md`. Verify these required fields are present and non-empty:
- `RESEARCH_QUESTION`
- `KEYWORDS.tier_1` (at least one entry)
- `DATABASES` (at least one entry with `enabled: true`)
- `RELEVANCE_SCORING.thresholds.include`
- `RELEVANCE_SCORING.thresholds.maybe`
- `ANALYTICAL_FRAMEWORK.S4_READINESS_MATRIX.technique_cluster_list` (must exist)

Also load and store the technique cluster list from CONTEXT.md into the
agent's working memory — it is required by `scorer.py` at scoring time.

**Check 2 — Python environment**
```bash
python --version   # require 3.11+
python -c "import anthropic, requests, aiohttp, httpx, tenacity, \
           playwright, openpyxl, pyzotero, rapidfuzz, loguru, \
           dotenv, yaml, pydantic"
```
If any import fails: `pip install -e ".[dev]" --break-system-packages`

**Check 3 — .env credentials**
For each database with `enabled: true` and `type: paywalled_browser`,
verify the corresponding env vars are set. Warn on missing credentials
but do not abort — skip that database and log the reason.
For Zotero: if `ZOTERO_API_KEY` or `ZOTERO_LIBRARY_ID` are missing,
warn and disable Zotero output for this run (fall back to Excel only).

**Check 4 — Playwright browsers**
```bash
python -m playwright install chromium --with-deps
```

**Check 5 — Output directory**
```bash
mkdir -p outputs
```

**Check 6 — Zotero connectivity (if enabled)**
```bash
python -c "
import os; from dotenv import load_dotenv; load_dotenv()
from pyzotero import zotero
z = zotero.Zotero(os.environ['ZOTERO_LIBRARY_ID'], 'user',
                  os.environ['ZOTERO_API_KEY'])
print(f'Zotero OK — {z.count_items()} items in library')
"
```

Print pre-flight summary:
```
Pre-flight complete.
  CONTEXT.md:          OK (project: <PROJECT_TITLE>)
  Kunze cluster list:  OK (<N> clusters across <M> dimensions + alignment)
  Python:              OK (3.x.x)
  Dependencies:        OK
  Databases enabled:   <list>
  Credentials:         <list found / missing>
  Zotero:              OK / DISABLED (<reason>)
  Output directory:    ./outputs/
```

---

## Phase 1 — Build the codebase

Build the source tree under `src/sourcing_agent/` following the structure
in `CLAUDE.md`. Each module must be complete and importable before moving
to the next.

### 1. `src/sourcing_agent/config.py`

Parse `CONTEXT.md` into a typed `Config` dataclass. Required fields:
`RESEARCH_QUESTION`, `KEYWORDS`, `DATABASES`, `RELEVANCE_SCORING`,
`ANALYTICAL_FRAMEWORK` (including `technique_cluster_list`),
`PAPER_STRUCTURE`, `OUTPUT`, `DEDUPLICATION`, `EDGE_CASES`.
Raise clear `ConfigError` with field name on any missing required field.

### 2. `src/sourcing_agent/models.py`

`PaperRecord` as a Pydantic BaseModel with all fields from the
`CLAUDE.md` PaperRecord field reference. Key fields for this project:

```python
class PaperRecord(BaseModel):
    # Identifiers
    doi: str | None = None
    arxiv_id: str | None = None
    s2_paper_id: str | None = None
    nasa_ntrs_id: str | None = None

    # Core metadata
    title: str
    abstract: str | None = None
    authors: list[str] = []
    year: int | None = None
    venue: str | None = None
    publication_type: str | None = None

    # Sourcing
    source_database: str
    retrieved_at: str  # ISO 8601
    open_access_pdf_url: str | None = None
    citation_count: int | None = None
    citations_per_year: float | None = None  # computed on assignment

    # Section assignment (populated by scorer)
    primary_section: str | None = None
    secondary_sections: list[str] = []
    kunze_dimension: str | None = None       # "D1"–"D6" or "alignment"
    technique_cluster: str | None = None
    cluster_assignment_confidence: str | None = None  # high|medium|low
    source_type: str | None = None

    # Scoring dimensions (populated by scorer)
    section_fit_score: float | None = None
    contribution_score: float | None = None
    recency_score: float | None = None
    weighted_score: float | None = None
    inclusion_decision: str | None = None    # include|maybe|exclude
    agent_notes: str | None = None

    # Boolean metadata flags (populated by scorer)
    is_cross_cutting: bool = False
    is_historical: bool = False
    space_heritage: bool = False
    deployment_constraints_discussed: bool = False
    compute_requirements_noted: bool = False
    radiation_robustness_discussed: bool = False
    operational_description_present: bool = False
    alignment_paper: bool = False
    compositional_alignment: bool = False
    general_alignment_robotics_context: bool = False

    # S2-specific
    mission_or_system_name: str | None = None

    # Utility
    abstract_snippet: str | None = None      # first 300 chars of abstract

    def model_post_init(self, __context):
        # Compute citations_per_year on record creation
        if self.citation_count is not None and self.year is not None:
            import datetime
            age = max(datetime.date.today().year - self.year + 0.5, 0.5)
            self.citations_per_year = round(self.citation_count / age, 1)
        # Populate abstract_snippet
        if self.abstract and not self.abstract_snippet:
            self.abstract_snippet = self.abstract[:300]
```

### 3. Database clients

Build one client per enabled database. All clients implement:
```python
async def search(query: str, config: Config) -> list[PaperRecord]
```

**`databases/semantic_scholar.py`** — Semantic Scholar Graph API v1.
Fields to request: `paperId,title,abstract,authors,year,venue,
citationCount,isOpenAccess,openAccessPdf,externalIds,publicationTypes`.
Rate limit: 10 req/sec without key, 100/sec with `S2_API_KEY` env var.
Use `tenacity` with exponential backoff for 429 responses.

**`databases/arxiv.py`** — arXiv API. Parse Atom XML with `feedparser`.
Filter to categories: `cs.RO`, `cs.AI`, `cs.LG`, `cs.SY`.

**`databases/nasa_ntrs.py`** — NASA Technical Reports Server REST API.
Endpoint: `https://ntrs.nasa.gov/api/citations/search`
Params: `q=<query>`, `rows=<max>`, `start=<offset>`.
Parse JSON response. This is an open API — no credentials needed.
These are primary sources for S2 — never auto-exclude for missing abstract.

**`databases/browser_scraper.py`** — Playwright automation for IEEE Xplore,
Web of Science, Scopus, ACM Digital Library.
Load credentials exclusively from `os.environ` using the env var names
in CONTEXT.md — never from the Config object directly.
Minimum 3-second delay between page loads.
Handle login failure, CAPTCHA, and session timeout gracefully:
log the error, skip the database, continue with remaining sources.

### 4. `pipeline/query_builder.py`

```python
def build_queries(config: Config) -> dict[str, list[str]]:
    """
    Returns {database_name: [query_string_1, query_string_2, ...]}
    One query per tier-2 cluster per database.
    Translates generic keyword syntax to database-native format.
    Logs all generated query strings to outputs/query-strings.txt.
    """
```

Translation table (generic → database syntax):
- PubMed: `[Title/Abstract]`, date: `YYYY:YYYY[pdat]`
- Semantic Scholar: `+` for AND, `|` for OR
- arXiv: `all:<term>` format
- IEEE/Scopus/WoS: varies — implement per-database translation

### 5. `pipeline/normalizer.py`

```python
def normalize(raw: dict, source: str) -> PaperRecord:
    """One normalizer per source format → canonical PaperRecord."""
```

All normalizers must populate: `title`, `source_database`, `retrieved_at`.
Populate all available metadata fields. Log fields that cannot be extracted.

### 6. `pipeline/deduplicator.py`

```python
def deduplicate(records: list[PaperRecord],
                config: Config) -> list[PaperRecord]:
```

1. DOI exact match (primary) — keep the record from the higher-priority
   source database (lower `priority` number in CONTEXT.md DATABASES list)
2. Fuzzy title match via `rapidfuzz.fuzz.ratio` (fallback for records
   without DOI) — threshold from `config.deduplication.fuzzy_threshold`
3. For arXiv preprint + published version of same paper: keep published,
   store arXiv ID in `arxiv_id` field of the published record
4. Log: DOI duplicate count, fuzzy duplicate count, total removed

### 7. `pipeline/scorer.py`

This is the most critical module. Read this section carefully.

```python
async def score_papers(
    records: list[PaperRecord],
    config: Config
) -> list[PaperRecord]:
    """Score all records in async parallel batches."""
```

**Scoring prompt template:**

```
SYSTEM:
You are a research librarian screening papers for a systematic literature
review. Your task is to score each paper AND extract structured metadata
that feeds into the review's analytical framework. Return ONLY valid JSON
with no preamble, no markdown fences, and no trailing text.

USER:
REVIEW TITLE: {config.project_title}

RESEARCH QUESTION:
{config.research_question}

REVIEW STRUCTURE (sections this paper could serve):
S1: Introduction — stakes, communication latency constraints, autonomy motivation
S2: Space Autonomy History — historical space missions, capability evolution
S3: AI in Space — deployed/near-deployment AI in space systems
S3a: AI in Space Robotics (rovers, arms, science autonomy)
S3b: AI in Spacecraft Systems (fault detection, scheduling)
S4: AI in Robotics — terrestrial AI capabilities by Kunze et al. dimension:
  S4a/D1: Navigation & Mapping (SLAM, visual odometry, path planning)
  S4b/D2: Perception (object recognition, VLMs, sensor fusion)
  S4c/D3: Knowledge Representation & Reasoning (PDDL, behaviour trees, LLM planning)
  S4d/D4: Planning (hierarchical planning, LLM policy, evolutionary methods)
  S4e/D5: Interaction (shared autonomy, HRI, delayed teleoperation, safety)
  S4f/D6: Learning (RL, imitation learning, sim-to-real, continual learning)
  S4g/Alignment: AI alignment in robotic systems (specification gaming,
                 goal misgeneralisation, compositional misalignment,
                 scalable oversight, alignment in space robotics)
S5a: Multimodality & Foundation Models (RT-2, PaLM-E, VLAs)
S5b: Bio-inspiration & Cognitive Architectures (SNNs, whole brain models)
S5c: Standardisation & Inter-Module Communication (ROS, MCP, A2A)
S6: Future Directions (roadmaps, safety, evaluation, alignment gaps)

TECHNIQUE CLUSTERS (for S4 papers only — assign the best-fit cluster):
D1/Navigation: visual_odometry | lidar_slam | learning_based_navigation |
               terrain_traversability | path_planning_classical |
               multi_sensor_fusion_nav
D2/Perception: object_recognition_deep_learning | visual_language_models |
               3d_scene_understanding | sensor_fusion_perception |
               anomaly_detection
D3/Reasoning:  classical_planning_pddl | behaviour_trees | llm_task_planning |
               neuro_symbolic_reasoning | knowledge_graphs_robotics
D4/Planning:   llm_policy_generation | hierarchical_task_planning |
               evolutionary_policy_search | model_predictive_control |
               behaviour_tree_llm_hybrid
D5/Interaction: shared_autonomy_frameworks | natural_language_hri |
                delayed_teleoperation | adaptive_autonomy |
                robot_safety_ethics
D6/Learning:   reinforcement_learning_control | imitation_learning |
               sim_to_real_transfer | continual_lifelong_learning |
               meta_learning | online_learning_deployment
Alignment:     specification_gaming_reward_hacking | goal_misgeneralisation |
               proxy_collapse | compositional_misalignment_modular |
               scalable_oversight_robotics | inter_module_diagnostic_oversight |
               embodied_ai_safety_evaluation | alignment_space_robotics

CONTEXT (what we are NOT looking for):
- Pure hardware/mechanical engineering without AI component
- Autonomous road vehicles without transferable robotics contribution
- UAVs/drones without ground robotics or space application
- Medical robotics unless HRI or shared autonomy is primary
- NLP/LLM papers without physical robot application

PAPER TO SCORE:
Title: {paper.title}
Abstract: {paper.abstract or '[No abstract available]'}
Year: {paper.year}
Venue: {paper.venue}
Source: {paper.source_database}
Citation count: {paper.citation_count}

SCORING INSTRUCTIONS:
Score each dimension 1.0–10.0 (one decimal place).

section_fit: How directly does this paper serve at least one review section?
  10 = directly and specifically serves a section with a citable claim.
  5  = generally related but no clear section fit.
  1  = not relevant.

contribution_quality: Substantive empirical, architectural, or analytical
  contribution? Real robot experiments or mission heritage score highest.
  10 = strong empirical contribution; 5 = position paper; 1 = opinion.

recency_score: Is the paper current enough for its purpose?
  Exception: S2 (history) papers score 10 regardless of age if historically
  significant. For all others: 2026=10, 2024=9, 2022=7, 2020=5, pre-2018=3.

Return ONLY this JSON object (no other text):
{{
  "primary_section": "<section_tag e.g. S4c:reasoning>",
  "secondary_sections": ["<tag>", "<tag>"],
  "kunze_dimension": "<D1|D2|D3|D4|D5|D6|alignment|null>",
  "technique_cluster": "<cluster_name or null>",
  "cluster_assignment_confidence": "<high|medium|low>",
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
  "agent_notes": "<one sentence explaining primary section assignment and scores>"
}}
```

**Post-scoring computation (done in Python, not by Claude):**

```python
def compute_weighted_score(record: PaperRecord, config: Config) -> float:
    weights = config.relevance_scoring.dimensions
    score = (
        record.section_fit_score * weights.section_fit.weight +
        record.contribution_score * weights.contribution_quality.weight +
        record.recency_score * weights.recency_and_relevance.weight
    )
    # Venue bonus
    if record.venue and any(
        v.lower() in record.venue.lower()
        for v in config.relevance_scoring.venue_bonus.venues
    ):
        score = min(score + config.relevance_scoring.venue_bonus.bonus, 10.0)
    return round(score, 2)

def assign_inclusion(record: PaperRecord, config: Config) -> str:
    # 1. Apply auto-exclude rules first
    # 2. Apply auto-include rules
    # 3. Threshold bucketing: include / maybe / exclude
    # 4. NASA/ESA technical reports: bump to include regardless of score
    ...
```

**Error handling in scorer.py:**
- JSON parse failure: assign all scores to 0.0, set `agent_notes` to
  "SCORING_ERROR: JSON parse failed", set `inclusion_decision` to "maybe"
  for human review. Do NOT raise — continue with next paper.
- API rate limit (429): backoff using `tenacity` with exponential backoff,
  max 5 retries before logging error and assigning scoring_error state.
- Missing abstract: score normally but cap `section_fit_score` at 6.0
  unless the paper is a NASA/ESA technical report (no cap applies).

**Batch execution:**
```python
async def score_batch(batch: list[PaperRecord],
                      config: Config) -> list[PaperRecord]:
    tasks = [score_single(paper, config) for paper in batch]
    return await asyncio.gather(*tasks, return_exceptions=False)

# Run in batches of config.relevance_scoring.parallel_batch_size (default: 10)
for i in range(0, len(records), batch_size):
    batch = records[i:i + batch_size]
    scored = await score_batch(batch, config)
    all_scored.extend(scored)
    progress.write_checkpoint("scoring", {"last_batch_index": i + batch_size})
```

### 8. `output/zotero_writer.py`

```python
def write_to_zotero(records: list[PaperRecord], config: Config) -> None:
```

- Write `include` and `maybe` papers only. Excluded papers are not written.
- Create the top-level collection if it does not exist.
- Create all subcollections from the list in CONTEXT.md if they do not exist.
- Place each paper in its `primary_section` subcollection.
- Duplicate into `secondary_sections` subcollections (intentional — enables
  section-based queries without joins at the writing stage).
- Apply the full tag schema from CONTEXT.md: section tags, kunze_dimension
  tags, technique_cluster tags, source_type tags, inclusion status tags,
  venue_tier tags, source_db tags, and all boolean flag tags where True.
- Add abstract note if `config.output.zotero.add_abstract_note` is True.
  Note format: `<b>Abstract:</b><br>{abstract}<br><br>
                <b>Kunze Dimension:</b> {kunze_dimension}<br>
                <b>Technique Cluster:</b> {technique_cluster}<br>
                <b>Section Fit:</b> {section_fit_score}<br>
                <b>Weighted Score:</b> {weighted_score}<br>
                <b>Agent Notes:</b> {agent_notes}`

### 9. `output/excel_writer.py`

```python
def write_to_excel(records: list[PaperRecord], config: Config) -> None:
```

Write four sheets:

**Sheet 1 — "All Papers"**
All records (include + maybe + exclude). Columns from CONTEXT.md
`OUTPUT.excel.sheets.main_sheet.columns`. Apply row colour coding:
- Include: light green (`#C6EFCE`)
- Maybe: light yellow (`#FFEB9C`)
- Exclude: light red (`#FFC7CE`)

**Sheet 2 — "Section Coverage"**
One row per section. Columns: section_tag, section_title, kunze_dimension,
target_paper_count (from CONTEXT.md), included_count, maybe_count,
coverage_status ("adequate" if included >= 50% of target, else "needs more").
Flag S4g_Alignment separately.

**Sheet 3 — "Analytical Data"** (four tabs within this sheet, or sub-tables)

*Tab 3a — S2 Mission Taxonomy:*
Columns: mission_or_system_name, year_deployed, D1_nav, D2_perc, D3_kr,
D4_plan, D5_interact, D6_learn, reference_paper.
Rows: one per unique `mission_or_system_name` from S2 included papers.
Cells: brief description from `operational_description_present` papers.

*Tab 3b — S2 Deployment Lag:*
Columns: ai_capability, terrestrial_first_pub_year, space_deployment_year,
deployment_lag_years, evidence_paper.
Rows: from S2 papers where `space_heritage` is True.

*Tab 3c — S4 Technique Cluster Summary:*
Columns: kunze_dimension, technique_cluster, paper_count,
space_heritage_count, deployment_constraints_count,
compute_noted_count, radiation_noted_count, cluster_confidence_high_pct.
One row per technique cluster (including alignment clusters).

*Tab 3d — Bibliometric Trend:*
Columns: year (2015–2026), S4a_count, S4b_count, S4c_count, S4d_count,
S4e_count, S4f_count, S4g_alignment_count.
Rows: one per year. Counts = included S4 papers for that dimension/year.

**Sheet 4 — "PRISMA Flow"**
Columns: stage, database, count.
Rows covering: records_identified, after_dedup, screened, excluded_with_reason,
included. Populate from pipeline metrics written to progress file.

### 10. `progress.py`

```python
class ProgressTracker:
    def write_checkpoint(self, step: str, data: dict) -> None: ...
    def read_checkpoint(self) -> dict | None: ...
    def is_step_complete(self, step: str) -> bool: ...
    def log_prisma_count(self, stage: str, db: str, count: int) -> None: ...
    def get_prisma_table(self) -> list[dict]: ...
```

Progress file format (YAML-compatible):
```
RUN_ID: run_YYYYMMDD_HHMMSS
PROJECT: <PROJECT_TITLE>
STATUS: in_progress | complete | interrupted
STEPS_COMPLETED:
  config_loaded: true
  queries_built: true
  semantic_scholar_queried: true  # retrieved: N
  arxiv_queried: false
  ...
PRISMA:
  semantic_scholar_identified: N
  arxiv_identified: N
  ...
  after_dedup: N
  screened: N
  excluded: N
  included: N
SCORING:
  total: N
  scored: N
  last_batch_index: N
RESULTS:
  include: N
  maybe: N
  exclude: N
RESUME_FROM: <step_name>
```

### 11. `main.py`

```python
async def run(context_path: str = "CONTEXT.md") -> None:
    config = Config.from_file(context_path)
    progress = ProgressTracker(config.output.progress_file)

    # Resume from checkpoint if interrupted
    if not progress.is_step_complete("config_loaded"):
        # ... validate config
        progress.write_checkpoint("config_loaded", {...})

    # Query each enabled database (skip if already complete)
    all_records: list[PaperRecord] = []
    for db in config.databases:
        if db.enabled and not progress.is_step_complete(f"{db.name}_queried"):
            records = await query_database(db, config)
            all_records.extend(records)
            progress.write_checkpoint(f"{db.name}_queried",
                                      {"retrieved": len(records)})

    # Deduplicate
    if not progress.is_step_complete("deduplicated"):
        all_records = deduplicate(all_records, config)
        progress.write_checkpoint("deduplicated", {"unique": len(all_records)})

    # Score
    if not progress.is_step_complete("scored"):
        all_records = await score_papers(all_records, config)
        progress.write_checkpoint("scored", {...})

    # Check section undercoverage — run supplementary queries if needed
    undercovered = check_section_coverage(all_records, config)
    for section in undercovered:
        supplementary = await run_supplementary_query(section, config)
        all_records.extend(supplementary)
        all_records = deduplicate(all_records, config)  # re-dedup
        supplementary_scored = await score_papers(supplementary, config)
        all_records = merge_scored(all_records, supplementary_scored)

    # Write outputs
    if config.output.zotero.enabled:
        write_to_zotero(all_records, config)
    write_to_excel(all_records, config)
    progress.write_checkpoint("complete", {"status": "complete"})
```

After building all modules, run:
```bash
python -c "from src.sourcing_agent.main import run; print('Import OK')"
```
Fix any import errors before proceeding to Phase 2.

---

## Phase 2 — Run the pipeline

```bash
python -m src.sourcing_agent.main
```

Report to the user after each major step:
```
✓ Config loaded: <PROJECT_TITLE>
  Technique clusters loaded: <N> clusters across D1–D6 + alignment
✓ Queries built: <N> queries across <M> databases
  Query log written to: outputs/query-strings.txt
✓ Semantic Scholar: <N> results
✓ arXiv:            <N> results
✓ NASA NTRS:        <N> results
✓ IEEE Xplore:      <N> results  [or: SKIPPED (login failed)]
✓ Web of Science:   <N> results  [or: SKIPPED]
✓ Scopus:           <N> results  [or: SKIPPED]
✓ ACM DL:           <N> results  [or: SKIPPED]
✓ Deduplication: <N> unique papers (removed <M> duplicates)
  DOI duplicates: <N> | Fuzzy title duplicates: <N>
✓ Scoring: <N> papers scored (<N> errors flagged for review)
✓ Section coverage check:
    S1:  <n> included / target 10-20  [adequate/needs more]
    S2:  <n> included / target 25-40  [adequate/needs more]
    S3:  <n> included / target 30-50  [adequate/needs more]
    S4a: <n> included / target 15-25  [adequate/needs more]
    S4b: <n> included / target 15-25  [adequate/needs more]
    S4c: <n> included / target 20-30  [adequate/needs more]
    S4d: <n> included / target 20-30  [adequate/needs more]
    S4e: <n> included / target 15-25  [adequate/needs more]
    S4f: <n> included / target 15-25  [adequate/needs more]
    S4g: <n> included / target 20-30  [adequate/needs more]
    S5a: <n> included / target 15-25  [adequate/needs more]
    S5b: <n> included / target 20-30  [adequate/needs more]
    S5c: <n> included / target 10-20  [adequate/needs more]
    S6:  <n> included / target 15-25  [adequate/needs more]
  [Supplementary queries run for undercovered sections: <list or none>]
✓ Zotero: <N> papers written across <M> subcollections
✓ Excel: written to outputs/sourcing_results.xlsx (4 sheets)
```

---

## Phase 3 — Post-run summary

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Sourcing run complete
  Project: <PROJECT_TITLE>
  Run time: <duration>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Candidates retrieved:     <total before dedup>
  After deduplication:      <unique total>

  INCLUDED:  <n> papers  →  Zotero + Excel
  MAYBE:     <n> papers  →  Zotero + Excel (flagged for review)
  EXCLUDED:  <n> papers  →  Excel only

  By Kunze dimension (included papers):
    D1 Navigation & Mapping:         <n>
    D2 Perception:                   <n>
    D3 Knowledge & Reasoning:        <n>
    D4 Planning:                     <n>
    D5 Interaction:                  <n>
    D6 Learning:                     <n>
    Alignment (S4g, cross-cutting):  <n>
    New Paradigms (S5):              <n>
    History / Space / Other:         <n>

  By database:
    Semantic Scholar:  <n>
    arXiv:             <n>
    NASA NTRS:         <n>
    IEEE Xplore:       <n>
    Web of Science:    <n>
    Scopus:            <n>
    ACM DL:            <n>

  Cluster confidence breakdown (S4 papers):
    High confidence:    <n> (<pct>%)
    Medium confidence:  <n> (<pct>%) ← review these before writing stage
    Low confidence:     <n> (<pct>%) ← requires full-text review

  Analytical data:
    S2 missions mapped:           <n>
    S2 deployment lag entries:    <n>
    S4 technique clusters:        <n>
    Bibliometric trend years:     2015–2026

  Outputs:
    Zotero collection:  <collection_name>
    Excel file:         outputs/sourcing_results.xlsx
    Query log:          outputs/query-strings.txt
    Progress file:      outputs/sourcing-progress.txt
    Run log:            outputs/sourcing-log.txt
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  NEXT STEPS (in order):
  1. Review medium/low confidence cluster assignments in Excel
     → Correct or merge clusters with < 3 papers
  2. Review "maybe" papers in Zotero or Excel
     → Promote or exclude as appropriate
  3. Verify S2 mission taxonomy data in "Analytical Data" sheet
  4. Hand confirmed include set to writing agent
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```
