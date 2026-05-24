---
name: resume-run
description: >
  Resume an interrupted sourcing run from the last saved checkpoint.
  Use when a previous /source-papers run was interrupted mid-session.
  Reads sourcing-progress.txt to determine where to restart.
allowed-tools: Read, Write, Edit, Bash, Glob
---

# /resume-run — Resume Interrupted Pipeline

Read `outputs/sourcing-progress.txt`. If it does not exist, tell the user:
"No interrupted run found. Use /source-papers to start a new run."

If it exists, parse the file and display the current state:

```
Interrupted run found:
  Project:   <PROJECT_TITLE>
  Run ID:    <RUN_ID>
  Started:   <timestamp>
  Status:    in_progress

Completed steps:
  ✓ context_loaded
  ✓ queries_built
  ✓ query_log_written
  ✓ semantic_scholar_queried (201 results)
  ✓ arxiv_queried (143 results)
  ✗ nasa_ntrs_queried          ← will resume here
  ✗ ieee_queried
  ✗ wos_queried
  ✗ scopus_queried
  ✗ acm_queried
  ✗ normalised
  ✗ deduplicated
  ✗ scored
  ✗ coverage_checked
  ✗ zotero_written
  ✗ excel_written

Papers collected so far: 344
Scoring progress: 0 / 344
```

Ask the user: "Resume from `<RESUME_FROM>` step? (yes / no — 'no' will
start a fresh run and overwrite the existing progress file)"

If yes: load all already-retrieved paper records from the progress state,
skip completed database queries, and continue from the first incomplete step.
If resuming mid-scoring, use `last_batch_index` from the progress file to
skip already-scored records and continue from the correct batch.

If the progress file shows `coverage_checked: true` but `zotero_written: false`,
display the section coverage summary before resuming so the user can see
whether supplementary queries were triggered and their outcome.

If the progress file shows any `cluster_confidence: medium` or
`cluster_confidence: low` counts in `CLUSTER_CONFIDENCE`, remind the user:
"Note: <N> medium and <N> low confidence cluster assignments are flagged
for your review in the Section Coverage sheet before handing to the writing agent."

If no: delete `outputs/sourcing-progress.txt` and invoke the full
`/source-papers` flow from Phase 0.
