# Literature Sourcing Agent — Parameter Reference
# Systematic Review: "Surveying AI in Robotics: Towards Autonomous Space Systems"
# Version: 2.0 — updated for Kunze framework, ACS/SDRR analytical structure,
#                 technique cluster system, and AI alignment subsection (S4g)

This file documents every parameter you can set in CONTEXT.md, what it does,
its default value, and guidance for tuning. Parameters are grouped by block.

---

## PROJECT PARAMETERS

| Parameter | Type | Default | Description |
|---|---|---|---|
| `PROJECT_ID` | string | required | Unique run identifier. Used in progress file naming. |
| `PROJECT_TITLE` | string | required | Human-readable name. Used in Zotero collection and Excel headers. |
| `REVIEW_TYPE` | string | "structured_narrative_systematic_review" | Declared in Methods section of paper. Do not change. |
| `TARGET_JOURNAL` | string | — | Stored in metadata. No functional effect. |
| `LEAD_RESEARCHER` | string | "" | Stored in metadata. No functional effect. |
| `INSTITUTION` | string | "" | Stored in metadata. No functional effect. |
| `ZOTERO_COLLECTION` | string | required if Zotero enabled | Top-level Zotero collection name. Subcollections are created automatically from the section list. |
| `DATE_INITIATED` | ISO date | today | Logged in progress file. No functional effect. |
| `OUTPUT_EXCEL_PATH` | path | "./outputs/sourcing_results.xlsx" | Output path for Excel file. |

---

## REVIEW METHODOLOGY PARAMETERS

| Parameter | Type | Default | Description |
|---|---|---|---|
| `REVIEW_METHODOLOGY.prisma_tracking` | bool | true | Whether to record PRISMA-stage counts. Required for journal submission. Do not disable. |
| `REVIEW_METHODOLOGY.search_transparency.record_query_strings` | bool | true | Log exact query strings to `outputs/query-strings.txt`. Required for Methods section reproducibility. |
| `REVIEW_METHODOLOGY.search_transparency.record_search_dates` | bool | true | Log date each database was queried. Required. |
| `REVIEW_METHODOLOGY.search_transparency.record_result_counts` | bool | true | Log raw result count per query. Required. |

### Inclusion criteria parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `preprint_citation_quality_rule.threshold` | int | 5 | Minimum citations per year for non-peer-reviewed preprints. Calculation: `total_citations / max(years_since_pub, 0.5)`. Loose first-pass gate — tighten to 10 if too many low-quality preprints pass. |
| `preprint_citation_quality_rule.recency_exception.window_months` | int | 18 | Papers published within this many months of the search date are exempt from the citations-per-year floor. Rationale: recent landmark papers have not had time to accumulate citations. |
| `preprint_citation_quality_rule.historical_exception.apply` | bool | true | Disable citation-rate gate entirely for papers assigned to S2 (history). Historical significance in a smaller research community cannot be proxied by citation velocity. |

---

## ANALYTICAL FRAMEWORK PARAMETERS

These parameters define the two primary analytical contributions embedded in
the review. Changing them has downstream effects on the scoring prompt,
the Zotero tag schema, and the Excel analytical data sheet.

### S2 Capability Taxonomy (Kunze et al. framework)

| Parameter | Type | Default | Description |
|---|---|---|---|
| `S2_CAPABILITY_TAXONOMY.six_dimensions` | object | fixed | The six Kunze et al. dimensions (D1–D6). Do not modify — these are the backbone of the paper. Adding or removing dimensions would require restructuring Sections 2–4 of the paper. |
| `S2_CAPABILITY_TAXONOMY.missions_to_cover_minimum` | list | 11 missions | The minimum set of space missions the writing agent must include in the Section 2 heatmap. Extend this list if additional missions are identified during sourcing. |

### S4 Readiness Matrix

#### Autonomy Characterisation Scale (ACS)

The ACS is defined in the `ANALYTICAL_FRAMEWORK.S4_READINESS_MATRIX.autonomy_characterisation_scale` block. It has four fixed levels. Do not change the level definitions — they are cited in the paper's Methods section.

| ACS Level | Label | Parasuraman Coverage |
|---|---|---|
| ACS-1 | Human-Operated | Information acquisition only |
| ACS-2 | Human-Supervised | Information acquisition + analysis |
| ACS-3 | Conditionally Autonomous | All four functions in nominal conditions |
| ACS-4 | Fully Autonomous | All four functions including failure handling |

ACS level assignments are made by the **writing agent** during synthesis, not by the sourcing agent. The sourcing agent collects the boolean metadata flags that enable these assignments.

#### Space Deployment Readiness Rubric (SDRR)

The SDRR has four fixed levels. Do not change the level definitions.

| SDRR Level | Label | Key Criterion |
|---|---|---|
| SDRR-3 | Space-Ready | Published evidence on space-qualified hardware or confirmed mission deployment |
| SDRR-2 | Deployment-Candidate | Edge hardware results + radiation/thermal work + communication-delay discussion (all three required) |
| SDRR-1 | Research-Mature | Tier-1 venue with real-robot demonstrations; no space constraint work |
| SDRR-0 | Pre-Deployment | Primarily simulation; no physical deployment |

SDRR assignments are made by the **writing agent**. The sourcing agent flags `deployment_constraints_discussed`, `compute_requirements_noted`, `radiation_robustness_discussed`, and `space_heritage` to enable these assignments.

#### Technique Cluster System

| Parameter | Type | Default | Description |
|---|---|---|---|
| `S4_READINESS_MATRIX.technique_cluster_list` | object | 7 dimensions × N clusters | Predefined cluster names per Kunze dimension plus the alignment dimension. The scorer assigns each S4/S4g paper to one primary cluster. Do not rename existing clusters without updating CONTEXT.md, CLAUDE.md, and the scorer prompt simultaneously. |
| `S4_READINESS_MATRIX.technique_cluster_list.ALIGNMENT` | list | 8 clusters | Alignment-specific clusters for S4g papers. Cross-cutting across D5/D6 — papers assigned here receive `kunze_dimension: "alignment"` rather than D1–D6. |
| `cluster_assignment_confidence` | enum | assigned by scorer | `high` = abstract clearly matches one cluster; `medium` = paper spans two clusters or uses hybrid approach; `low` = no clear cluster match from abstract alone. Medium and low confidence assignments are flagged in the Section Coverage sheet for researcher review before the writing stage. |
| Minimum papers per cluster | int | 3 | Clusters with fewer than 3 included papers are flagged for researcher review. Decision options: merge into a related cluster, run a supplementary query, or note the gap in the paper's limitations section. |

---

## PAPER STRUCTURE PARAMETERS

Each section entry in `PAPER_STRUCTURE` has the following parameters:

| Parameter | Type | Description |
|---|---|---|
| `title` | string | Section heading used in the paper. |
| `kunze_dimensions_relevant` | list | Which of D1–D6 apply to this section. All six apply to S2, S4, S5, and S6. |
| `section_tag` | string | The tag applied to papers in this section. Used in Zotero and Excel. Format: `S<N>:<slug>`. |
| `target_paper_count` | range | Expected number of included papers. Used by the undercoverage check — supplementary queries are triggered if included count < 50% of the lower bound. |
| `analytical_outputs` | object | Describes the analytical output this section contributes to. Read-only — do not edit without revising the paper structure simultaneously. |

### Section target counts (reference)

| Section | Kunze Dim. | Target Count |
|---|---|---|
| S1 Introduction | — | 10–20 |
| S2 History | D1–D6 | 25–40 |
| S3 AI in Space | D1–D5 | 30–50 |
| S4a Navigation & Mapping | D1 | 15–25 |
| S4b Perception | D2 | 15–25 |
| S4c Knowledge & Reasoning | D3 | 20–30 |
| S4d Planning | D4 | 20–30 |
| S4e Interaction | D5 | 15–25 |
| S4f Learning | D6 | 15–25 |
| S4g Alignment | D5/D6 cross-cutting | 20–30 |
| S5a Multimodality | D1–D6 | 15–25 |
| S5b Machine Brain | D1–D6 | 20–30 |
| S5c Integration Protocols | D1–D6 | 10–20 |
| S6 Future Directions | D1–D6 | 15–25 |

---

## KEYWORD PARAMETERS

| Parameter | Type | Default | Description |
|---|---|---|---|
| `KEYWORDS.tier_1` | list | required (≥1) | Must-have concepts. All terms ANDed in every query. Keep to 1–3 terms. |
| `KEYWORDS.tier_2.clusters` | named lists | required | One cluster per section or sub-topic. Each cluster generates one query per database: `tier_1 AND (cluster_term_1 OR cluster_term_2...)`. |
| `KEYWORDS.tier_3` | list | optional | Scoring-context only — not used in database queries. Injected into the scoring prompt to help the scorer recognise domain-specific terminology. |

**Cluster naming convention:** Clusters are named by section: `space_history_cluster`, `ai_space_cluster`, `navigation_cluster`, `perception_cluster`, `reasoning_cluster`, `planning_cluster`, `interaction_cluster`, `learning_cluster`, `alignment_cluster`, `multimodal_cluster`, `machine_brain_cluster`, `integration_cluster`, `future_cluster`.

**Tuning tips:**
- Too few results in a section → add synonyms to that section's cluster or add a new cluster
- Too many irrelevant results → tighten tier_1 or add exclusion language to `EXTENDED_CONTEXT`
- Alignment subsection under-covered → the `alignment_cluster` has 12 terms; add domain-specific synonyms (e.g. "reward misspecification", "inner alignment", "mesa-optimisation")

---

## DATABASE PARAMETERS

| Parameter | Type | Default | Description |
|---|---|---|---|
| `name` | string | required | Database display name. |
| `type` | enum | required | `open_access_api` or `paywalled_browser`. |
| `priority` | int | required | Query order (1 = first). Lower number = queried earlier. Open-access databases should have lower priority numbers. |
| `enabled` | bool | required | Toggle without deleting configuration. |
| `max_results_per_query` | int | 200 | Results per cluster query per database. Total candidates ≈ this × number of enabled clusters. |
| `api` | string | — | API identifier for open-access sources. |
| `login_method` | string | — | Paywalled sources only. Currently: `institutional_sso`. |
| `credential_env_vars` | object | — | Maps credential fields to env var names. Never put values here. |
| `categories` | list | — | arXiv only. Currently: `["cs.RO", "cs.AI", "cs.LG", "cs.SY"]`. |
| `note` | string | — | Human-readable note. No functional effect. |

**Database priority for this project:**

| Priority | Database | Type | Why |
|---|---|---|---|
| 1 | Semantic Scholar | Open API | Best general CS/AI coverage |
| 2 | arXiv | Open API | Essential for recent AI preprints |
| 3 | IEEE Xplore | Paywalled | ICRA, IROS, AERO proceedings |
| 4 | Web of Science | Paywalled | Cross-disciplinary journal coverage |
| 5 | Scopus | Paywalled | Cross-disciplinary journal coverage |
| 6 | ACM Digital Library | Paywalled | HRI conference proceedings |
| 7 | NASA NTRS | Open API | Primary sources for S2/S3 history |

---

## FILTER PARAMETERS

| Parameter | Type | Default | Description |
|---|---|---|---|
| `FILTERS.date.default_start_year` | int | 2015 | General default. Override per-section for S2 (1960) and S3 (2000). |
| `FILTERS.date.default_end_year` | int | current year | Upper bound. |
| `FILTERS.date.section_overrides` | object | S2: 1960, S3: 2000 | Per-section date overrides. S2 must reach back to 1960 to cover Apollo-era material. |
| `FILTERS.date.strict` | bool | false | `false` = flag out-of-range papers rather than hard-exclude. Recommended — important historical papers must not be silently dropped. |
| `FILTERS.publication_types.include` | list | journal, conference, workshop, technical report, preprint | Types to retrieve. Conference papers are essential for robotics. |
| `FILTERS.publication_venues_priority` | object | tier_1 and tier_2 lists | Used for venue bonus scoring. Tier-1 venues receive a +0.5 score bonus. |
| `FILTERS.secondary_source_flag.enabled` | bool | true | Tag survey/review/meta-analysis papers as `secondary_source:true`. Required to distinguish primary research from context-setting surveys. |

---

## RELEVANCE SCORING PARAMETERS

**Scoring dimensions for this review:**

| Dimension | Weight | Description |
|---|---|---|
| `section_fit` | 0.55 | How directly does the paper serve a specific section? Can the writing agent make a citable claim from it? |
| `contribution_quality` | 0.30 | Substantive empirical, architectural, or analytical contribution? Real robot experiments score highest. |
| `recency_and_relevance` | 0.15 | Current enough for its purpose? Exception: S2 historical papers score 10 on recency regardless of age if historically significant. |

**Note on dimension names:** Earlier versions of this project used `topical_relevance` and `methodological_fit`. These have been replaced by `section_fit`, `contribution_quality`, and `recency_and_relevance` to better reflect the structured-review purpose of this sourcing run. Do not use the old names in code.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `RELEVANCE_SCORING.dimensions.section_fit.weight` | float | 0.55 | Primary dimension — does the paper serve a section? |
| `RELEVANCE_SCORING.dimensions.contribution_quality.weight` | float | 0.30 | Methodological rigour. |
| `RELEVANCE_SCORING.dimensions.recency_and_relevance.weight` | float | 0.15 | Currency of the work. Must sum to 1.0 across all three dimensions. |
| `RELEVANCE_SCORING.thresholds.include` | float | 7.0 | Papers ≥ this are auto-included. |
| `RELEVANCE_SCORING.thresholds.maybe` | float | 5.0 | Papers ≥ maybe but < include are flagged for human review. |
| `RELEVANCE_SCORING.scoring_basis` | enum | title_and_abstract | Basis for scoring. `title_and_abstract` is recommended. `full_text` is too slow for large candidate sets. |
| `RELEVANCE_SCORING.parallel_batch_size` | int | 10 | Papers scored per async batch. Increase up to 20 for speed; decrease if hitting API rate limits. |
| `RELEVANCE_SCORING.venue_bonus.apply` | bool | true | Apply bonus to tier-1 venue papers. |
| `RELEVANCE_SCORING.venue_bonus.bonus` | float | 0.5 | Score bonus added for papers in tier-1 venues. Capped at 10.0. |
| `RELEVANCE_SCORING.auto_include_rules` | list | 3 rules | Conditional overrides. Conditions are natural language evaluated by the scorer. NASA/ESA technical reports auto-include regardless of score. |
| `RELEVANCE_SCORING.auto_exclude_rules` | list | 3 rules | Applied before auto-include. UAVs, road vehicles, and no-abstract papers in low-tier venues are auto-excluded. |

**Special scoring rules for this project:**

- **NASA/ESA technical reports (S2/S3):** Auto-include regardless of weighted score. These are primary mission documents not subject to standard quality gates.
- **S2 historical papers:** `recency_score` should be set to 10.0 for historically significant papers regardless of publication year. The scoring prompt instructs Claude accordingly.
- **S4g alignment papers:** Papers from the general AI alignment literature (not robotics-specific) are in scope if they have direct implications for robotic deployment. Flag as `general_alignment_robotics_context: true`. These are not excluded but should be tagged as secondary context in Zotero.
- **Scoring errors:** If Claude returns a malformed JSON response, assign all scores to 0.0, set inclusion_decision to "maybe", and record `agent_notes: "SCORING_ERROR: JSON parse failed"`. Do not raise an exception — continue with the next paper.

---

## SECTION ASSIGNMENT AND TAGGING PARAMETERS

These parameters govern what metadata the scorer extracts from each paper in
addition to the relevance scores.

| Parameter | Assigned By | Description |
|---|---|---|
| `primary_section` | scorer | The section this paper most directly serves. One of the section tags in CONTEXT.md. Non-null for all included/maybe papers — null is a bug. |
| `secondary_sections` | scorer | Up to 2 additional sections served. Used for Zotero subcollection duplication. |
| `kunze_dimension` | scorer | `"D1"` through `"D6"` for S4 papers; `"alignment"` for S4g papers; `null` for all other sections. Non-null for all S4 and S4g included/maybe papers — null is a bug. |
| `technique_cluster` | scorer | One cluster name from the predefined list in CONTEXT.md. Non-null for all S4/S4g papers. |
| `cluster_assignment_confidence` | scorer | `high` / `medium` / `low`. Medium and low are flagged for researcher review before writing stage. |
| `is_cross_cutting` | scorer | `true` if paper serves 3 or more sections. |
| `is_historical` | scorer | `true` if paper assigned to S2. |
| `space_heritage` | scorer | `true` if paper describes a technique confirmed deployed in a space mission. |
| `deployment_constraints_discussed` | scorer | `true` if paper addresses real-world operational limits relevant to space deployment. |
| `compute_requirements_noted` | scorer | `true` if paper notes hardware resource requirements or constraints. |
| `radiation_robustness_discussed` | scorer | `true` if paper discusses radiation tolerance, thermal robustness, or space environmental effects. |
| `operational_description_present` | scorer | `true` (S2 papers) if paper contains specific capability descriptions of what a system could and could not do autonomously. |
| `alignment_paper` | scorer | `true` if the paper's primary topic is AI alignment, safety, or misalignment. |
| `compositional_alignment` | scorer | `true` if the paper specifically addresses alignment properties of composed or modular AI systems (not single models). |
| `general_alignment_robotics_context` | scorer | `true` if the paper is from the general alignment literature but is cited for its implications for robotic deployment. |
| `mission_or_system_name` | scorer | S2 papers only. Name of the specific space mission or system described (e.g. "Curiosity rover (AEGIS)"). |

---

## DEDUPLICATION PARAMETERS

| Parameter | Type | Default | Description |
|---|---|---|---|
| `DEDUPLICATION.primary_key` | enum | DOI | Primary duplicate detection key. |
| `DEDUPLICATION.fallback_key` | enum | title_fuzzy_match | Fallback for records without DOI. |
| `DEDUPLICATION.fuzzy_threshold` | float (0–1) | 0.92 | Levenshtein similarity above which titles are treated as duplicates. 0.92 catches minor formatting differences. Lower to 0.85 to catch more variants (higher false-positive risk). |
| `DEDUPLICATION.on_duplicate` | enum | keep_highest_scoring_source | Keep the record from the higher-priority database (lower `priority` number). Options: `keep_highest_scoring_source`, `keep_first_found`, `keep_all_flag_dupes`. |
| `DEDUPLICATION.arxiv_published_handling.action` | enum | keep_published_version | If a paper exists as both arXiv preprint and published version, keep the published version and store the arXiv ID as `arxiv_id`. |

---

## OUTPUT PARAMETERS

| Parameter | Type | Default | Description |
|---|---|---|---|
| `OUTPUT.zotero.enabled` | bool | true | Write to Zotero. Requires `zotero-mcp` configured and Zotero desktop running. |
| `OUTPUT.zotero.collection_name` | string | "SpaceAutonomy_Review_2026" | Top-level Zotero collection. Subcollections are created automatically. |
| `OUTPUT.zotero.add_abstract_note` | bool | true | Add abstract + scoring metadata as a Zotero note. Includes Kunze dimension, technique cluster, scores, and agent notes. |
| `OUTPUT.excel.enabled` | bool | true | Write Excel output. |
| `OUTPUT.excel.path` | path | "./outputs/sourcing_results.xlsx" | Output path. |
| `OUTPUT.progress_file` | path | "./outputs/sourcing-progress.txt" | Checkpoint file for resumption. |
| `OUTPUT.log_file` | path | "./outputs/sourcing-log.txt" | Full run log. |
| `OUTPUT.query_log` | path | "./outputs/query-strings.txt" | Exact query strings for Methods section reproducibility. |

### Excel sheet reference

| Sheet | Contents |
|---|---|
| "All Papers" | All records with full column set including Kunze dimension, cluster, and all boolean flags. Colour-coded by inclusion decision. |
| "Section Coverage" | One row per section. Target vs actual counts, coverage status, cluster confidence breakdown. |
| "Analytical Data" | Four sub-tables: S2 mission taxonomy, S2 deployment lag, S4 cluster summary, bibliometric trend (paper counts per Kunze dimension per year 2015–2026). |
| "PRISMA Flow" | PRISMA-stage counts per database. Required for paper Methods section. |

---

## EDGE CASE HANDLING PARAMETERS

| Parameter | Type | Default | Description |
|---|---|---|---|
| `EDGE_CASES.section_undercoverage.threshold` | float | 0.5 | Flag and run supplementary query if included count < 50% of section target lower bound. |
| `EDGE_CASES.cluster_underpopulation.minimum_papers_per_cluster` | int | 3 | Clusters with fewer papers are flagged for researcher review. |
| `EDGE_CASES.no_abstract_available.action` | enum | score_on_title_only | Score from title alone. Cap section_fit_score at 6.0. Exception: NASA/ESA technical reports are scored normally without abstract. |
| `EDGE_CASES.medium_low_confidence_clusters.action` | enum | flag_for_researcher_review | List all medium and low confidence cluster assignments in Section Coverage sheet. Researcher reviews before writing stage. |
| `EDGE_CASES.paywall_login_failure.action` | enum | skip_and_log | Skip the database and log the failure. Do not abort the run. |
| `EDGE_CASES.rate_limit_hit.backoff_seconds` | int | 30 | Wait time before retry after 429 response. |
| `EDGE_CASES.rate_limit_hit.max_retries` | int | 3 | Maximum retries before skipping the request and logging an error. |
| `EDGE_CASES.session_interrupted.action` | enum | resume_from_progress_file | On restart, read progress file and resume from the last successful checkpoint. |
| `EDGE_CASES.historical_paper_date_penalty.apply` | bool | false | S2 papers must not receive a recency penalty. This is enforced in the scoring prompt. |

---

## ENVIRONMENT VARIABLES (set in `.env`, never in CONTEXT.md)

| Variable | Required For | Description |
|---|---|---|
| `ZOTERO_API_KEY` | Zotero output | From zotero.org/settings/keys |
| `ZOTERO_LIBRARY_ID` | Zotero output | Your Zotero user or group ID |
| `ZOTERO_LOCAL` | Zotero output | Set to `"true"` to use local Zotero desktop API |
| `S2_API_KEY` | Semantic Scholar | Optional. Raises rate limit from 10 to 100 req/sec. Request at semanticscholar.org |
| `IEEE_USERNAME` | IEEE Xplore | Institutional login username |
| `IEEE_PASSWORD` | IEEE Xplore | Institutional login password |
| `IEEE_PROXY_URL` | IEEE Xplore | Institutional proxy URL |
| `WOS_USERNAME` | Web of Science | Institutional login username |
| `WOS_PASSWORD` | Web of Science | Institutional login password |
| `WOS_PROXY_URL` | Web of Science | Institutional proxy URL |
| `SCOPUS_USERNAME` | Scopus | Institutional login username |
| `SCOPUS_PASSWORD` | Scopus | Institutional login password |
| `SCOPUS_PROXY_URL` | Scopus | Institutional proxy URL |
| `ACM_USERNAME` | ACM Digital Library | Institutional login username |
| `ACM_PASSWORD` | ACM Digital Library | Institutional login password |
| `ACM_PROXY_URL` | ACM Digital Library | Institutional proxy URL |

Note: NASA NTRS is a public API — no credentials required.
Note: `NCBI_API_KEY` and `WOS_USERNAME`/`WOS_PASSWORD` from earlier versions
are replaced. PubMed is disabled for this project (low yield for CS/robotics).
