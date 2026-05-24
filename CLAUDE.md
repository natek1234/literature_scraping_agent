# Literature Sourcing Agent — Project Instructions
# Systematic Review: "Surveying AI in Robotics: Towards Autonomous Space Systems"
# Version: 2.0 — updated for Kunze dimension alignment and S4g addition

## What this project is

This is a two-phase academic literature pipeline for a structured systematic
review. This repository contains Phase 1: the **sourcing agent**, which
retrieves, scores, tags, deduplicates, and stores candidate papers from multiple
academic databases.

Phase 2 (the writing agent) is a separate project that reads from the Zotero
library this agent populates and constructs the review paper.

The review's analytical backbone is the six-dimension framework of Kunze et al.
(2018): navigation & mapping (D1), perception (D2), knowledge representation &
reasoning (D3), planning (D4), interaction (D5), and learning (D6). Section 4
of the paper is structured around these six dimensions, with a seventh
subsection (S4g) covering the AI alignment problem in robotic systems.
Every paper retrieved must be tagged with the section and Kunze dimension
it serves. Read `CONTEXT.md` and `PIPELINE_SPEC.md` before writing any code.

## Slash commands available

| Command | When to use |
|---|---|
| `/setup-env` | Once, on a new machine before first run |
| `/source-papers` | Start a new full sourcing run |
| `/resume-run` | Resume an interrupted sourcing session |
| `/save-progress` | After completing any meaningful unit of work |
| `/open-pr` | When a feature branch is ready for review |

## Project structure

```
.
├── CLAUDE.md                        ← you are here (read at every session start)
├── CONTEXT.md                       ← research config and analytical framework
├── PIPELINE_SPEC.md                 ← pipeline implementation spec (was SKILL.md)
├── PARAMETERS.md                    ← parameter reference guide
├── pyproject.toml                   ← Python dependencies and tool config
├── .env                             ← credentials (never commit)
├── .mcp.json                        ← MCP server config (Zotero)
├── .gitignore
├── .claude/
│   └── skills/
│       ├── source-papers/SKILL.md   ← /source-papers slash command
│       ├── setup-env/SKILL.md       ← /setup-env slash command
│       ├── resume-run/SKILL.md      ← /resume-run slash command
│       ├── save-progress/SKILL.md   ← /save-progress slash command
│       └── open-pr/SKILL.md         ← /open-pr slash command
├── src/
│   └── sourcing_agent/
│       ├── __init__.py
│       ├── config.py                ← parses CONTEXT.md into Config dataclass
│       ├── models.py                ← PaperRecord dataclass (canonical schema)
│       ├── progress.py              ← checkpoint read/write
│       ├── main.py                  ← pipeline orchestration entry point
│       ├── databases/
│       │   ├── __init__.py
│       │   ├── semantic_scholar.py
│       │   ├── arxiv.py
│       │   ├── nasa_ntrs.py         ← NASA Technical Reports Server client
│       │   └── browser_scraper.py   ← IEEE, WoS, Scopus, ACM via Playwright
│       ├── pipeline/
│       │   ├── __init__.py
│       │   ├── query_builder.py     ← tier-1/tier-2 → database-native queries
│       │   ├── normalizer.py        ← source formats → PaperRecord
│       │   ├── deduplicator.py      ← DOI + fuzzy title deduplication
│       │   └── scorer.py            ← Claude API scoring + field extraction
│       └── output/
│           ├── __init__.py
│           ├── zotero_writer.py     ← writes to Zotero subcollections with tags
│           └── excel_writer.py      ← writes all sheets including analytical data
└── tests/
    ├── conftest.py
    ├── test_config.py
    ├── test_models.py
    ├── databases/
    │   ├── test_semantic_scholar.py
    │   ├── test_arxiv.py
    │   └── test_nasa_ntrs.py
    ├── pipeline/
    │   ├── test_query_builder.py
    │   ├── test_deduplicator.py
    │   └── test_scorer.py
    └── output/
        ├── test_zotero_writer.py
        └── test_excel_writer.py
```

## Section and Zotero subcollection reference

The Zotero library is organised into subcollections that map directly to paper
sections and Kunze dimensions. Claude Code must use these exact names when
writing to Zotero and when logging section assignments.

```
SpaceAutonomy_Review_2026/
├── S1_Introduction
├── S2_SpaceAutonomyHistory
├── S3_AIinSpace
│   ├── S3a_AISpaceRobotics
│   └── S3b_AISpacecraft
├── S4_AIinRobotics
│   ├── S4a_D1_NavigationMapping       ← Kunze D1
│   ├── S4b_D2_Perception              ← Kunze D2
│   ├── S4c_D3_KnowledgeReasoning      ← Kunze D3
│   ├── S4d_D4_Planning                ← Kunze D4
│   ├── S4e_D5_Interaction             ← Kunze D5
│   ├── S4f_D6_Learning                ← Kunze D6
│   └── S4g_Alignment                  ← AI alignment (cross-cutting D5/D6)
├── S5_NewParadigms
│   ├── S5a_Multimodality
│   ├── S5b_MachineBrain
│   └── S5c_IntegrationProtocols
├── S6_FutureDirections
├── _CrossCutting
└── _MaybeReview
```

## PaperRecord field reference

Every paper in the pipeline is represented as a `PaperRecord`. The fields
below are the canonical schema — `models.py` must implement all of them.
Fields marked (scoring) are populated by `scorer.py`. Fields marked (S2)
are populated only for history-section papers. Fields marked (S4) are
populated only for AI-in-robotics section papers.

```
Identifiers:
  doi, pmid, arxiv_id, s2_paper_id, nasa_ntrs_id

Core metadata:
  title, abstract, authors, year, venue,
  volume, issue, pages, publication_type

Sourcing:
  source_database, retrieved_at, open_access_pdf_url

Section assignment (scoring):
  primary_section          # e.g. "S4c:reasoning"
  secondary_sections       # list, up to 2
  kunze_dimension          # "D1" through "D6", or "alignment" for S4g
  technique_cluster        # from predefined cluster list in CONTEXT.md
  cluster_assignment_confidence  # "high" | "medium" | "low"
  source_type              # "primary_research" | "secondary_source" |
                           # "technical_report" | "mission_document" | "roadmap"

Scoring dimensions (scoring):
  section_fit_score        # 1.0–10.0
  contribution_score       # 1.0–10.0
  recency_score            # 1.0–10.0
  weighted_score           # computed from weights in CONTEXT.md
  inclusion_decision       # "include" | "maybe" | "exclude"
  agent_notes              # one-sentence scoring rationale

Metadata flags (scoring):
  is_cross_cutting         # bool: serves 3+ sections
  is_historical            # bool: assigned to S2
  space_heritage           # bool: confirmed deployed in space
  deployment_constraints_discussed  # bool
  compute_requirements_noted        # bool
  radiation_robustness_discussed    # bool
  operational_description_present   # bool (S2)
  alignment_paper                   # bool: primary topic is AI alignment
  compositional_alignment           # bool: addresses modular composition safety
  general_alignment_robotics_context  # bool: general alignment with robotic framing

S2-specific:
  mission_or_system_name   # e.g. "Curiosity rover (AEGIS)"

Citation metrics:
  citation_count
  citations_per_year       # computed: citation_count / max(years_since_pub, 0.5)

Enrichment:
  abstract_snippet         # first 300 chars of abstract
```

## Git workflow — branch model

```
main                    ← stable, protected
  └── develop           ← integration branch
        ├── feat/...    ← new features
        ├── fix/...     ← bug fixes
        └── chore/...   ← config, deps, tooling
```

**Rules Claude Code must follow:**
- Never commit directly to `main` or `develop`
- Every new feature or fix starts on its own branch off `develop`
- Branch names use the pattern: `<type>/<short-slug>`
- Commits follow Conventional Commits format (see below)
- Run `/save-progress` at the end of every meaningful work session
- Open a PR with `/open-pr` when a branch is complete

## Git workflow — commit conventions

```
<type>(<scope>): <description>

[optional body]

Co-Authored-By: Claude <noreply@anthropic.com>
```

**Types:** `feat`, `fix`, `refactor`, `test`, `docs`, `chore`, `perf`

**Scopes** map to modules: `semantic-scholar`, `arxiv`, `nasa-ntrs`,
`browser-scraper`, `query-builder`, `normalizer`, `deduplicator`, `scorer`,
`zotero-writer`, `excel-writer`, `config`, `models`, `progress`, `pipeline`,
`output`, `cli`

**Examples:**
```
feat(scorer): add kunze_dimension and technique_cluster extraction
fix(scorer): handle alignment papers with no Kunze dimension assignment
feat(excel-writer): add S4g alignment rows to analytical data sheet
test(scorer): add tests for boolean flag extraction from Claude response
chore(models): add citations_per_year computed field to PaperRecord
```

## Code quality rules

1. **Credentials:** Never write to any file. Only `os.environ`. If a
   credential is needed, instruct the user to add it to `.env`.

2. **No PDF downloads:** Abstract and metadata only in the sourcing agent.

3. **Checkpoints:** Write to `outputs/sourcing-progress.txt` after every
   major pipeline step. This enables resumption without re-querying databases.

4. **Rate limits:** Respect all database rate limits — see `PIPELINE_SPEC.md`
   for exact values. Use `tenacity` for retry logic with exponential backoff.

5. **Type hints:** Every function signature. Pydantic for `PaperRecord` and
   `Config`. `dataclasses` for simple internal structs.

6. **Error handling:** All errors are caught and logged. A failed database
   source is skipped, not a reason to abort the run. Use `loguru`.

7. **Logging:** Use `loguru` throughout. INFO for progress, WARNING for
   skipped items, ERROR for failures. Log to console and
   `outputs/sourcing-log.txt` simultaneously.

8. **Formatting:** Black (88 chars), Ruff lint, mypy strict mode.
   `/save-progress` enforces these automatically before every commit.

9. **Tests:** Write tests for every public function. Use `pytest` with
   `pytest-asyncio`. Mock all external API calls with `respx`/`responses`.
   Minimum coverage target: 80%.

10. **No force-push:** Never `git push --force`. Use `git push --force-with-lease`
    only if absolutely necessary and explain why in the commit message.

11. **Section consistency:** Every paper that passes the include/maybe
    threshold must have a non-null `primary_section` and, for S4 papers,
    a non-null `kunze_dimension`. Null values in these fields are a bug
    in `scorer.py`, not acceptable output.
