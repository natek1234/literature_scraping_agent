# /score-pending — Score Deferred Papers Interactively

Score all papers tagged `PENDING_MANUAL_SCORING` in `outputs/papers-scored.jsonl`.
These papers were deferred because `ANTHROPIC_API_KEY` was absent when the pipeline ran.
You (Claude Code) apply the same scoring rubric directly — no API key required,
because you are the model doing the scoring.

Work through every step below in order. After each batch, apply the scores to disk
immediately so progress is preserved if the session is interrupted.

---

## Step 0 — Pre-flight checks

### 0a — Verify required files exist

Check that all of these exist and are non-empty. Stop and report if any are missing:
- `CONTEXT.md`
- `outputs/papers-scored.jsonl`
- `src/sourcing_agent/pipeline/scorer.py`

### 0b — Count pending papers

```python
import json, sys
sys.path.insert(0, "src")

records = []
with open("outputs/papers-scored.jsonl", encoding="utf-8") as f:
    for line in f:
        if line.strip():
            records.append(json.loads(line))

pending = [
    r for r in records
    if r.get("agent_notes") == "PENDING_MANUAL_SCORING"
    and r.get("inclusion_decision") != "exclude"
]

print(f"Total records in cache : {len(records)}")
print(f"Pending manual scoring : {len(pending)}")
print(f"Already scored         : {len(records) - len(pending)}")
```

If pending count is 0, print "No papers pending scoring — done." and stop.

### 0c — Load configuration and print weights

```python
import sys
sys.path.insert(0, "src")
from dotenv import load_dotenv; load_dotenv()
from sourcing_agent.config import Config

config = Config.from_file("CONTEXT.md")
dims = config.relevance_scoring.dimensions
thresh = config.relevance_scoring.thresholds

print(f"Project:    {config.project_title}")
print(f"Weights:    section_fit={dims.section_fit.weight}  "
      f"contribution={dims.contribution_quality.weight}  "
      f"recency={dims.recency_and_relevance.weight}")
print(f"Thresholds: include >= {thresh.include}   maybe >= {thresh.maybe}")
```

Note the weights and thresholds — you will need them in Step 3 when checking
whether a weighted score lands in include / maybe / exclude. The weighted score
formula is:
  weighted = section_fit × w_sf + contribution × w_cq + recency × w_rr
(auto-rules are applied by the Python step, not by you manually)

---

## Step 1 — Build batch manifest

```python
import json, os

BATCH_SIZE = 20

all_records = []
with open("outputs/papers-scored.jsonl", encoding="utf-8") as f:
    for line in f:
        if line.strip():
            all_records.append(json.loads(line))

pending_indices = [
    i for i, r in enumerate(all_records)
    if r.get("agent_notes") == "PENDING_MANUAL_SCORING"
    and r.get("inclusion_decision") != "exclude"
]

batches = [
    pending_indices[i : i + BATCH_SIZE]
    for i in range(0, len(pending_indices), BATCH_SIZE)
]

os.makedirs("outputs/scoring-session", exist_ok=True)
manifest = {
    "total_pending": len(pending_indices),
    "batch_count": len(batches),
    "batch_size": BATCH_SIZE,
    "batches": batches,  # list of lists of record indices
}
with open("outputs/scoring-session/manifest.json", "w", encoding="utf-8") as f:
    json.dump(manifest, f, indent=2)

print(f"Manifest written: {len(batches)} batch(es) of up to {BATCH_SIZE} papers each.")
print("outputs/scoring-session/manifest.json")
```

---

## Step 2 — Scoring rubric (read this section in full before scoring)

You will apply this rubric to every paper. It is identical to the pipeline scorer's
`_USER_TEMPLATE`. Read CONTEXT.md to confirm weights and thresholds, but use the
taxonomy below — it is the authoritative version.

### Section taxonomy

```
S1:introduction        Stakes, communication latency, autonomy motivation
S2:history             Historical space missions, capability evolution (pre-2010)
S3:ai-in-space         Deployed or near-deployment AI in space systems
  S3a:ai-space-robotics  Rovers, arms, onboard science autonomy
  S3b:ai-spacecraft      Fault detection, scheduling, onboard compute
S4a:navigation    (D1) SLAM, visual odometry, path planning, terrain traversability
S4b:perception    (D2) Object recognition, VLMs, 3D scene understanding, sensor fusion
S4c:reasoning     (D3) PDDL, behaviour trees, LLM task planning, knowledge graphs
S4d:planning      (D4) Hierarchical planning, LLM policy generation, MPC
S4e:interaction   (D5) Shared autonomy, HRI, delayed teleoperation, safety
S4f:learning      (D6) RL, imitation learning, sim-to-real, continual learning
S4g:alignment          AI alignment in robotic systems (spec. gaming, goal misgeneralisation,
                        proxy collapse, compositional misalignment, scalable oversight)
S5a:multimodality      Foundation models for robotics (RT-2, PaLM-E, VLAs)
S5b:machine-brain      Cognitive architectures, SNNs, embodied cognition
S5c:integration-protocols  ROS/ROS2 middleware, MCP, A2A, inter-module comms
S6:future-directions   Roadmaps, safety/alignment gaps, evaluation frameworks
```

### Scoring dimensions (all 1.0–10.0, one decimal place)

**section_fit** — Does this paper directly serve at least one section?
- 10 = serves a specific section with a citable claim or data point
- 7  = clearly relevant, will likely be cited
- 5  = generally related, no clear section fit
- 3  = tangentially relevant
- 1  = not relevant; assign exclude via low score

**contribution_quality** — Substantive empirical, architectural, or analytical contribution?
- 10 = real robot experiments + strong results; or confirmed space deployment
- 8  = solid benchmark results on standard datasets
- 7  = well-cited survey that anchors a section
- 5  = position paper, workshop paper
- 3  = opinion or speculative
- 1  = no technical contribution

**recency_score** — Is the paper current enough for its purpose?
- S2:history papers: always 10.0 if historically significant regardless of age
- 2025–2026: 10  |  2023–2024: 9  |  2021–2022: 7
- 2019–2020: 5   |  2017–2018: 4  |  pre-2017: 3

### Auto-exclusion signals (assign section_fit ≤ 2.0 for any of these)
- Pure mechanical/hardware engineering with no AI component
- Autonomous road vehicles (self-driving cars) with no transferable robotics contribution
- UAVs/drones without ground robotics or space application
- Medical robotics unless HRI or shared autonomy is the primary contribution
- NLP/LLM papers with no physical robot application

### Kunze dimension (for S4 papers only; null for all other sections)
D1 Navigation & Mapping | D2 Perception | D3 Knowledge Representation & Reasoning
D4 Planning | D5 Interaction | D6 Learning | alignment (for S4g) | null

### Technique clusters (for S4 and S4g papers only; null otherwise)
```
D1: visual_odometry | lidar_slam | learning_based_navigation |
    terrain_traversability | path_planning_classical | multi_sensor_fusion_nav
D2: object_recognition_deep_learning | visual_language_models |
    3d_scene_understanding | sensor_fusion_perception | anomaly_detection
D3: classical_planning_pddl | behaviour_trees | llm_task_planning |
    neuro_symbolic_reasoning | knowledge_graphs_robotics
D4: llm_policy_generation | hierarchical_task_planning |
    evolutionary_policy_search | model_predictive_control | behaviour_tree_llm_hybrid
D5: shared_autonomy_frameworks | natural_language_hri |
    delayed_teleoperation | adaptive_autonomy | robot_safety_ethics
D6: reinforcement_learning_control | imitation_learning |
    sim_to_real_transfer | continual_lifelong_learning |
    meta_learning | online_learning_deployment
alignment: specification_gaming_reward_hacking | goal_misgeneralisation |
           proxy_collapse | compositional_misalignment_modular |
           scalable_oversight_robotics | inter_module_diagnostic_oversight |
           embodied_ai_safety_evaluation | alignment_space_robotics
```

---

## Step 3 — Score each batch

Process every batch in order (batch 0, 1, 2, …). For each batch, follow
sub-steps 3a → 3b → 3c before moving to the next batch.

### 3a — Read batch papers (run for each batch_n)

Replace `batch_n` with the current batch number (0-indexed) and run:

```python
import json, sys
sys.path.insert(0, "src")

batch_n = 0  # <-- change this for each batch

all_records = []
with open("outputs/papers-scored.jsonl", encoding="utf-8") as f:
    for line in f:
        if line.strip():
            all_records.append(json.loads(line))

with open("outputs/scoring-session/manifest.json") as f:
    manifest = json.load(f)

indices = manifest["batches"][batch_n]
batch_papers = [all_records[i] for i in indices]

print(f"\n{'='*72}")
print(f"Batch {batch_n + 1} of {manifest['batch_count']}  "
      f"({len(batch_papers)} papers)")
print(f"{'='*72}")
for i, p in enumerate(batch_papers):
    abstract = (p.get("abstract") or "[no abstract]")[:400]
    print(f"\n[{i:02d}] {p['title'][:110]}")
    print(f"     Year={p.get('year')}  Venue={str(p.get('venue',''))[:60]}")
    print(f"     Source={p.get('source_database')}  Citations={p.get('citation_count')}")
    print(f"     Abstract: {abstract}")
```

### 3b — Score the batch (YOU do this step — no Python)

After reading the papers printed above, apply the rubric from Step 2 to each
paper. Do this carefully — read every abstract, consider the venue and year,
and assign scores that reflect the paper's actual relevance to the review.

For papers with `[no abstract]`: cap section_fit at 6.0 unless the source
is "NASA Technical Reports Server" (which gets no cap).

Produce a JSON array — one object per paper — and write it to:
`outputs/scoring-session/batch-{batch_n}.json`

Each object must match this schema exactly:
```json
{
  "title": "<EXACT paper title — used for matching>",
  "primary_section": "<section_tag from taxonomy>",
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
  "agent_notes": "<one sentence: why this primary section and what the scores reflect>"
}
```

Write the complete JSON array to disk using the Write tool before running 3c.

### 3c — Apply scoring to JSONL (run immediately after writing batch-N.json)

```python
import json, sys
sys.path.insert(0, "src")
from dotenv import load_dotenv; load_dotenv()
from sourcing_agent.config import Config
from sourcing_agent.pipeline.scorer import apply_session_scores

batch_n = 0  # <-- same batch_n as 3a

config = Config.from_file("CONTEXT.md")

with open(f"outputs/scoring-session/batch-{batch_n}.json", encoding="utf-8") as f:
    results = json.load(f)

updated = apply_session_scores("outputs/papers-scored.jsonl", results, config)
print(f"Batch {batch_n}: {updated} records updated in papers-scored.jsonl")
```

If `updated` is less than `len(results)`, some titles did not match. Print
the unmatched titles and fix them by editing the JSON file so the titles
exactly match the JSONL records, then re-run 3c.

### 3d — Repeat

Increment batch_n by 1 and repeat Steps 3a → 3b → 3c until all batches
are complete.

---

## Step 4 — Verify completion

```python
import json

records = []
with open("outputs/papers-scored.jsonl", encoding="utf-8") as f:
    for line in f:
        if line.strip():
            records.append(json.loads(line))

still_pending = [r for r in records if r.get("agent_notes") == "PENDING_MANUAL_SCORING"]
n_inc = sum(1 for r in records if r.get("inclusion_decision") == "include")
n_may = sum(1 for r in records if r.get("inclusion_decision") == "maybe")
n_exc = sum(1 for r in records if r.get("inclusion_decision") == "exclude")

print(f"\nVerification:")
print(f"  Still pending : {len(still_pending)}")
print(f"  Include       : {n_inc}")
print(f"  Maybe         : {n_may}")
print(f"  Exclude       : {n_exc}")
print(f"  Total         : {len(records)}")

for r in still_pending[:10]:
    print(f"  UNMATCHED: {r['title'][:90]}")
```

If papers are still pending after all batches: check for title truncation or
whitespace differences between the JSON you wrote and the JSONL titles.
Edit the relevant `outputs/scoring-session/batch-N.json` file to fix the
title field, then re-run Step 3c for that batch.

---

## Step 5 — Regenerate Excel output

```python
import sys
sys.path.insert(0, "src")
from dotenv import load_dotenv; load_dotenv()
from sourcing_agent.config import Config
from sourcing_agent.models import PaperRecord
from sourcing_agent.output.excel_writer import write_to_excel

config = Config.from_file("CONTEXT.md")
records = []
with open("outputs/papers-scored.jsonl", encoding="utf-8") as f:
    for line in f:
        if line.strip():
            records.append(PaperRecord.model_validate_json(line))

write_to_excel(records, config)
print(f"Excel regenerated — {len(records)} papers written")
```

---

## Step 6 — Update Zotero (if credentials available)

```python
import os, sys
sys.path.insert(0, "src")
from dotenv import load_dotenv; load_dotenv()

if not (os.environ.get("ZOTERO_API_KEY") and os.environ.get("ZOTERO_LIBRARY_ID")):
    print("Zotero credentials not set — skipping Zotero update.")
    print("Add ZOTERO_API_KEY and ZOTERO_LIBRARY_ID to .env to enable.")
else:
    from sourcing_agent.config import Config
    from sourcing_agent.models import PaperRecord
    from sourcing_agent.output.zotero_writer import write_to_zotero

    config = Config.from_file("CONTEXT.md")
    records = []
    with open("outputs/papers-scored.jsonl", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(PaperRecord.model_validate_json(line))

    written = write_to_zotero(records, config)
    print(f"Zotero: {written} papers written/updated")
```

---

## Step 7 — Print completion summary and clean up

```python
import json, os, shutil

records = []
with open("outputs/papers-scored.jsonl", encoding="utf-8") as f:
    for line in f:
        if line.strip():
            records.append(json.loads(line))

n_inc = sum(1 for r in records if r.get("inclusion_decision") == "include")
n_may = sum(1 for r in records if r.get("inclusion_decision") == "maybe")
n_exc = sum(1 for r in records if r.get("inclusion_decision") == "exclude")
n_pen = sum(1 for r in records if r.get("agent_notes") == "PENDING_MANUAL_SCORING")

# Archive batch files
archive_dir = "outputs/scoring-session/archive"
session_dir = "outputs/scoring-session"
os.makedirs(archive_dir, exist_ok=True)
for fname in os.listdir(session_dir):
    if fname.endswith(".json"):
        shutil.move(
            os.path.join(session_dir, fname),
            os.path.join(archive_dir, fname),
        )

print(f"""
{'━'*44}
  /score-pending complete
{'━'*44}
  Include       : {n_inc}
  Maybe         : {n_may}
  Exclude       : {n_exc}
  Still pending : {n_pen}
  Total         : {len(records)}
{'━'*44}
  Batch files archived to:
  outputs/scoring-session/archive/
{'━'*44}
  Next steps:
  1. Review 'maybe' papers in _MaybeReview Zotero collection
  2. Run /save-progress to commit scored outputs
{'━'*44}
""")
```

Tell the user: "Scoring session complete. Run `/save-progress` to commit."
