# Literature Review Sourcing Agent — Research Context

## Project Metadata
# ─────────────────────────────────────────────────────────────────────────────
# These fields identify the project and help the agent organize Zotero outputs.
# ─────────────────────────────────────────────────────────────────────────────

PROJECT_ID: "proj_001"
PROJECT_TITLE: "The Role of Gut Microbiome Dysbiosis in Neuroinflammation and Neurodegenerative Disease"
LEAD_RESEARCHER: "Dr. Jane Smith"
INSTITUTION: "University of Arizona"
ZOTERO_COLLECTION: "GutBrain_NeuroDegen_2025"
DATE_INITIATED: "2025-03-29"
OUTPUT_EXCEL_PATH: "./outputs/sourcing_results.xlsx"


## Research Question
# ─────────────────────────────────────────────────────────────────────────────
# Write this as clearly as possible. The agent uses this as its primary
# relevance anchor. Be specific about the population, intervention/exposure,
# and outcome of interest (PICO format recommended for clinical topics).
# Aim for 1–4 sentences.
# ─────────────────────────────────────────────────────────────────────────────

RESEARCH_QUESTION: |
  What is the mechanistic relationship between gut microbiome dysbiosis and
  neuroinflammatory processes in humans, and how does this relationship
  contribute to the onset or progression of neurodegenerative diseases,
  specifically Alzheimer's disease, Parkinson's disease, and ALS?
  Secondary interest: which microbial genera or metabolites are most
  consistently implicated across multiple studies?


## Extended Research Context
# ─────────────────────────────────────────────────────────────────────────────
# This is the richest input for the agent. Write as much as you need.
# Include: background knowledge, prior literature you already know about,
# theoretical framing, controversies in the field, what you are NOT looking
# for, and what methodological approaches are most credible for this topic.
# The agent reads this in full before scoring any paper.
# ─────────────────────────────────────────────────────────────────────────────

EXTENDED_CONTEXT: |
  The gut-brain axis has emerged as a major focus of neuroscience and
  microbiology research over the past decade. There is now substantial evidence
  that the gut microbiome communicates bidirectionally with the central nervous
  system via the vagus nerve, immune signaling, and metabolite production
  (e.g. short-chain fatty acids, tryptophan metabolites, LPS).

  Neuroinflammation — characterized by microglial activation, elevated
  cytokines (IL-1β, TNF-α, IL-6), and disrupted blood-brain barrier integrity
  — is a hallmark of Alzheimer's (AD), Parkinson's (PD), and ALS. Several
  recent human cohort studies and animal model experiments suggest that
  microbiome composition significantly differs in patients with these
  conditions compared to healthy controls.

  Key controversies:
  - Causality vs. correlation: most human studies are cross-sectional. We
    want to prioritize longitudinal cohort studies and mechanistic animal
    models that demonstrate directionality.
  - Confounders: diet, medication (especially antibiotics and PPIs), age,
    and BMI heavily influence microbiome composition. Studies that do not
    control for at least diet and medication should be flagged.
  - Reproducibility: many microbiome findings fail to replicate across
    populations and sequencing platforms (16S vs. WGS).

  We are particularly interested in:
  - Human studies (patient cohorts, clinical trials)
  - Mouse/rat models where germ-free or antibiotic-treated animals are used
  - Metabolomic studies linking specific microbial metabolites to
    neuroinflammatory markers
  - Fecal microbiota transplant (FMT) studies as mechanistic evidence

  We are NOT looking for:
  - Purely in vitro cell culture studies with no in vivo validation
  - Studies on psychiatric conditions (depression, anxiety, schizophrenia)
    unless they also include a neurodegeneration angle
  - Nutrition/diet intervention studies that do not measure microbiome
    composition directly
  - Reviews and meta-analyses (these will be handled in a separate pass)


## Search Keywords
# ─────────────────────────────────────────────────────────────────────────────
# Provide keywords in tiers. Tier 1 = must appear (conceptually) in abstract.
# Tier 2 = should appear in at least one of the keyword clusters.
# Tier 3 = bonus — increases relevance score but not required.
# Boolean operators (AND/OR) are interpreted by the agent when constructing
# database-specific query strings.
# ─────────────────────────────────────────────────────────────────────────────

KEYWORDS:
  tier_1:
    - "gut microbiome OR gut microbiota"
    - "neuroinflammation OR neurodegeneration"

  tier_2:
    clusters:
      disease_cluster:
        - "Alzheimer's disease"
        - "Parkinson's disease"
        - "amyotrophic lateral sclerosis"
        - "ALS"
        - "dementia"
      mechanism_cluster:
        - "gut-brain axis"
        - "blood-brain barrier"
        - "microglial activation"
        - "short-chain fatty acids"
        - "SCFA"
        - "lipopolysaccharide"
        - "LPS"
        - "vagus nerve"
        - "dysbiosis"
      method_cluster:
        - "fecal microbiota transplant"
        - "FMT"
        - "16S rRNA"
        - "whole genome sequencing"
        - "metabolomics"
        - "germ-free"

  tier_3:
    - "Lactobacillus"
    - "Bifidobacterium"
    - "Akkermansia"
    - "butyrate"
    - "tryptophan"
    - "serotonin"
    - "alpha-synuclein"
    - "amyloid"
    - "tau"


## Source Databases
# ─────────────────────────────────────────────────────────────────────────────
# List which databases the agent should query. Set priority order (1 = first).
# Set enabled: true/false to toggle without deleting.
# For paywalled sources, the agent will use browser automation + credentials.
# ─────────────────────────────────────────────────────────────────────────────

DATABASES:
  - name: "PubMed"
    type: "open_access_api"
    priority: 1
    enabled: true
    api: "NCBI_Entrez"
    max_results_per_query: 300

  - name: "Semantic Scholar"
    type: "open_access_api"
    priority: 2
    enabled: true
    api: "SemanticScholar_Graph_v1"
    max_results_per_query: 200

  - name: "Europe PMC"
    type: "open_access_api"
    priority: 3
    enabled: true
    api: "EuropePMC_REST"
    max_results_per_query: 200

  - name: "arXiv"
    type: "open_access_api"
    priority: 4
    enabled: false
    note: "Low yield for biomedical topics — enable for CS/ML-adjacent projects"

  - name: "Web of Science"
    type: "paywalled_browser"
    priority: 5
    enabled: true
    login_method: "institutional_sso"
    credential_env_vars:
      username: "WOS_USERNAME"
      password: "WOS_PASSWORD"
      proxy_url: "WOS_PROXY_URL"
    max_results_per_query: 150

  - name: "Scopus"
    type: "paywalled_browser"
    priority: 6
    enabled: true
    login_method: "institutional_sso"
    credential_env_vars:
      username: "SCOPUS_USERNAME"
      password: "SCOPUS_PASSWORD"
      proxy_url: "SCOPUS_PROXY_URL"
    max_results_per_query: 150

  - name: "JSTOR"
    type: "paywalled_browser"
    priority: 7
    enabled: false
    note: "Low biomedical yield — enable for humanities or social science projects"


## Date & Publication Filters
# ─────────────────────────────────────────────────────────────────────────────

FILTERS:
  date:
    start_year: 2015
    end_year: 2025
    strict: true                     # Reject papers outside range entirely

  publication_types:
    include:
      - "Journal Article"
      - "Clinical Trial"
      - "Randomized Controlled Trial"
      - "Observational Study"
      - "Case-Control Study"
      - "Cohort Study"
      - "Animal Study"
    exclude:
      - "Review"
      - "Systematic Review"
      - "Meta-Analysis"
      - "Editorial"
      - "Letter"
      - "Comment"
      - "Conference Abstract"

  language:
    include: ["English"]
    exclude_if_no_english_abstract: true

  open_access_only: false            # Set true to restrict to freely available full text

  sample_size:
    minimum_human_n: 20              # Flag (not exclude) human studies with n < 20
    flag_small_samples: true


## Relevance Scoring Parameters
# ─────────────────────────────────────────────────────────────────────────────
# The agent scores each paper 1–10 on two dimensions.
# Papers are bucketed into include / maybe / exclude.
# ─────────────────────────────────────────────────────────────────────────────

RELEVANCE_SCORING:
  dimensions:
    topical_relevance:
      weight: 0.6
      description: "How directly does this paper address the research question and key concepts?"
    methodological_fit:
      weight: 0.4
      description: "Does the study design and methodology match what we are looking for?"

  thresholds:
    include:  7.0      # Weighted score ≥ 7.0 → include automatically
    maybe:    5.0      # Weighted score 5.0–6.9 → flag for human review
    exclude:  0.0      # Weighted score < 5.0 → exclude

  scoring_basis: "title_and_abstract"   # Options: title_only | title_and_abstract | full_text

  parallel_batch_size: 10              # Papers scored in parallel per API call batch

  auto_include_rules:
    - condition: "paper is cited > 100 times AND score >= 6.0"
      action: "bump_to_include"
      note: "Highly cited papers get a lower threshold"

  auto_exclude_rules:
    - condition: "abstract contains 'in vitro only' AND no in vivo mention"
      action: "exclude"
    - condition: "no abstract available AND journal impact factor < 2"
      action: "exclude"


## Deduplication
# ─────────────────────────────────────────────────────────────────────────────

DEDUPLICATION:
  primary_key: "DOI"
  fallback_key: "title_fuzzy_match"
  fuzzy_threshold: 0.92              # Levenshtein similarity — flag if > 0.92 as likely duplicate
  on_duplicate: "keep_highest_scoring_source"


## Output Configuration
# ─────────────────────────────────────────────────────────────────────────────

OUTPUT:
  zotero:
    enabled: true
    collection_name: "{{ZOTERO_COLLECTION}}"
    tag_schema:
      relevance: ["relevance:high", "relevance:medium", "relevance:low"]
      source_db: ["source:pubmed", "source:semantic_scholar", "source:wos", "source:scopus"]
      review_status: ["status:included", "status:maybe", "status:excluded"]
      study_type: ["type:human", "type:animal", "type:rct", "type:cohort"]
    add_abstract_note: true          # Store abstract as a Zotero note on each item

  excel:
    enabled: true
    path: "{{OUTPUT_EXCEL_PATH}}"
    columns:
      - "title"
      - "authors"
      - "year"
      - "journal"
      - "doi"
      - "pmid"
      - "abstract_snippet"          # First 300 chars of abstract
      - "relevance_score"
      - "topical_score"
      - "methodological_score"
      - "inclusion_decision"
      - "source_database"
      - "citation_count"
      - "open_access_pdf_url"
      - "study_type"
      - "sample_size_flag"
      - "agent_notes"               # Free-text from agent about why paper was scored as it was

  progress_file: "./outputs/sourcing-progress.txt"
  log_file: "./outputs/sourcing-log.txt"


## Flags & Edge Case Handling
# ─────────────────────────────────────────────────────────────────────────────

EDGE_CASES:
  no_abstract_available:
    action: "score_on_title_only"
    cap_score_at: 6.0               # Cannot score above 6 without abstract

  paywall_login_failure:
    action: "skip_and_log"
    notify: true

  rate_limit_hit:
    action: "backoff_and_retry"
    backoff_seconds: 30
    max_retries: 3

  session_interrupted:
    action: "resume_from_progress_file"
    note: "Agent reads sourcing-progress.txt to pick up where it left off"
