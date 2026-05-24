from __future__ import annotations

import asyncio
import json
import os
from typing import TYPE_CHECKING

import anthropic
from loguru import logger
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from ..models import PaperRecord

if TYPE_CHECKING:
    from ..config import Config
    from ..progress import ProgressTracker

_SYSTEM_PROMPT = """\
You are a research librarian screening papers for a systematic literature review.
Score and tag each paper based on the criteria below.
Return ONLY valid JSON — no preamble, no markdown fences, no trailing text."""

_USER_TEMPLATE = """\
REVIEW TITLE: {project_title}

RESEARCH QUESTION:
{research_question}

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

KUNZE DIMENSION (for S4 papers only -- assign D1-D6 or "alignment"):
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
  Title:          {title}
  Abstract:       {abstract}
  Year:           {year}
  Venue:          {venue}
  Source:         {source}
  Citation count: {citations}

SCORING INSTRUCTIONS:
Score each dimension 1.0-10.0 (one decimal place).

section_fit: Does this paper directly serve at least one section?
  10 = directly serves with a specific citable claim or data point.
  5  = generally relevant but no clear section fit.
  1  = not relevant.

contribution_quality: Substantive empirical, architectural, or analytical
  contribution? Real robot experiments or confirmed space mission heritage
  score highest (9-10). Position paper or opinion piece: 3-5.
  Highly cited survey that anchors a section: 7-8.

recency_score: Is this paper current enough for its purpose?
  For S2 (history) papers only: score 10.0 regardless of age if the paper
  contains historically significant operational data about a space mission.
  For all other sections: 2025-2026=10, 2023-2024=9, 2021-2022=7,
  2019-2020=5, 2017-2018=4, pre-2017=3.

Return ONLY this JSON (no other text):
{{
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
}}"""

_CLIENT: anthropic.AsyncAnthropic | None = None
_MODEL = "claude-sonnet-4-6"


def _get_client() -> anthropic.AsyncAnthropic:
    global _CLIENT
    if _CLIENT is None:
        _CLIENT = anthropic.AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    return _CLIENT


async def score_papers(
    records: list[PaperRecord],
    config: Config,
    progress: ProgressTracker,
) -> list[PaperRecord]:
    batch_size = config.relevance_scoring.parallel_batch_size
    all_scored: list[PaperRecord] = []
    start_idx = progress.last_batch_index

    logger.info(
        f"Scoring {len(records)} papers in batches of {batch_size}"
        + (f" (resuming from index {start_idx})" if start_idx else "")
    )

    # Pre-scored records (from a resumed run)
    all_scored.extend(records[:start_idx])

    for i in range(start_idx, len(records), batch_size):
        batch = records[i : i + batch_size]
        tasks = [_score_single(paper, config) for paper in batch]
        scored_batch = await asyncio.gather(*tasks, return_exceptions=False)
        all_scored.extend(scored_batch)
        progress.write_checkpoint(
            "scoring",
            {"last_batch_index": i + len(batch), "scored_so_far": len(all_scored)},
        )
        if (i // batch_size) % 5 == 0:
            logger.info(f"Scoring progress: {len(all_scored)}/{len(records)}")

    return all_scored


async def _score_single(paper: PaperRecord, config: Config) -> PaperRecord:
    abstract = paper.abstract or "[No abstract available]"
    # Cap section_fit for no-abstract non-NTRS papers — handled post-scoring
    prompt = _USER_TEMPLATE.format(
        project_title=config.project_title,
        research_question=config.research_question[:800],
        title=paper.title,
        abstract=abstract[:1200],
        year=paper.year or "unknown",
        venue=paper.venue or "unknown",
        source=paper.source_database,
        citations=(
            paper.citation_count if paper.citation_count is not None else "unknown"
        ),
    )

    try:
        raw_json = await _call_claude(prompt)
        scored = _apply_scoring(paper, raw_json, config)
    except Exception as e:
        logger.error(f"Scoring failed for '{paper.title[:60]}': {e}")
        scored = paper.model_copy(
            update={
                "section_fit_score": 0.0,
                "contribution_score": 0.0,
                "recency_score": 0.0,
                "weighted_score": 0.0,
                "inclusion_decision": "maybe",
                "agent_notes": f"SCORING_ERROR: {e}",
            }
        )

    return scored


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=2, min=5, max=60),
    retry=retry_if_exception_type(anthropic.RateLimitError),
    reraise=True,
)
async def _call_claude(prompt: str) -> dict:
    client = _get_client()
    resp = await client.messages.create(
        model=_MODEL,
        max_tokens=512,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    from anthropic.types import TextBlock

    text_block = next((b for b in resp.content if isinstance(b, TextBlock)), None)
    if text_block is None:
        raise ValueError("No TextBlock in Claude response")
    text = text_block.text.strip()
    # Strip markdown fences if Claude added them despite instructions
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text)


def _apply_scoring(paper: PaperRecord, data: dict, config: Config) -> PaperRecord:
    section_fit = float(data.get("section_fit_score") or 0.0)
    contribution = float(data.get("contribution_score") or 0.0)
    recency = float(data.get("recency_score") or 0.0)

    # Cap section_fit for no-abstract non-NTRS papers
    if not paper.abstract and paper.source_type not in (
        "technical_report",
        "mission_document",
    ):
        section_fit = min(section_fit, 6.0)

    weighted = _compute_weighted(section_fit, contribution, recency, paper, config)
    inclusion = _assign_inclusion_from_score(weighted, config)

    kunze_dim = data.get("kunze_dimension")
    if kunze_dim == "null" or kunze_dim == "":
        kunze_dim = None

    cluster = data.get("technique_cluster")
    if cluster == "null" or cluster == "":
        cluster = None

    confidence = data.get("cluster_assignment_confidence")
    if confidence == "null" or confidence == "":
        confidence = None

    secondary = data.get("secondary_sections") or []
    secondary = [s for s in secondary if s and s != "null"]

    is_cross_cutting = len({data.get("primary_section", ""), *secondary} - {""}) >= 3

    mission = data.get("mission_or_system_name")
    if mission == "null":
        mission = None

    source_type_raw = data.get("source_type")
    # Preserve source_type set at normalisation (e.g. "technical_report" for NTRS)
    source_type = paper.source_type or source_type_raw or None

    return paper.model_copy(
        update={
            "primary_section": data.get("primary_section"),
            "secondary_sections": secondary,
            "kunze_dimension": kunze_dim,
            "technique_cluster": cluster,
            "cluster_assignment_confidence": confidence,
            "source_type": source_type,
            "section_fit_score": round(section_fit, 1),
            "contribution_score": round(contribution, 1),
            "recency_score": round(recency, 1),
            "weighted_score": weighted,
            "inclusion_decision": inclusion,
            "agent_notes": data.get("agent_notes", ""),
            "is_cross_cutting": is_cross_cutting,
            "is_historical": bool(data.get("is_historical", False)),
            "space_heritage": bool(data.get("space_heritage", False)),
            "deployment_constraints_discussed": bool(
                data.get("deployment_constraints_discussed", False)
            ),
            "compute_requirements_noted": bool(
                data.get("compute_requirements_noted", False)
            ),
            "radiation_robustness_discussed": bool(
                data.get("radiation_robustness_discussed", False)
            ),
            "operational_description_present": bool(
                data.get("operational_description_present", False)
            ),
            "alignment_paper": bool(data.get("alignment_paper", False)),
            "compositional_alignment": bool(data.get("compositional_alignment", False)),
            "general_alignment_robotics_context": bool(
                data.get("general_alignment_robotics_context", False)
            ),
            "mission_or_system_name": mission,
        }
    )


def _compute_weighted(
    section_fit: float,
    contribution: float,
    recency: float,
    paper: PaperRecord,
    config: Config,
) -> float:
    dims = config.relevance_scoring.dimensions
    raw = (
        section_fit * dims.section_fit.weight
        + contribution * dims.contribution_quality.weight
        + recency * dims.recency_and_relevance.weight
    )
    vb = config.relevance_scoring.venue_bonus
    if vb.apply and paper.venue:
        if any(v.lower() in paper.venue.lower() for v in vb.venues):
            raw = min(raw + vb.bonus, vb.cap_at)
    return round(raw, 2)


def _assign_inclusion_from_score(score: float, config: Config) -> str:
    t = config.relevance_scoring.thresholds
    if score >= t.include:
        return "include"
    if score >= t.maybe:
        return "maybe"
    return "exclude"


def apply_auto_rules(records: list[PaperRecord], config: Config) -> list[PaperRecord]:
    """Apply auto-include and auto-exclude rules after scoring."""
    result = []
    for record in records:
        result.append(_apply_rules(record, config))
    return result


def _apply_rules(record: PaperRecord, config: Config) -> PaperRecord:
    # 1. Auto-exclude first
    for rule in config.relevance_scoring.auto_exclude_rules:
        cond = rule.get("condition", "")
        if _eval_condition(cond, record):
            return record.model_copy(
                update={
                    "inclusion_decision": "exclude",
                    "agent_notes": f"{record.agent_notes or ''} [AUTO-EXCLUDED: {cond}]".strip(),
                }
            )

    # 2. NASA/ESA NTRS technical reports — always include
    if record.source_database == "NASA Technical Reports Server":
        return record.model_copy(
            update={
                "inclusion_decision": "include",
                "agent_notes": f"{record.agent_notes or ''} [AUTO-INCLUDED: NASA NTRS mission document]".strip(),
            }
        )

    # 3. Auto-include rules
    for rule in config.relevance_scoring.auto_include_rules:
        cond = rule.get("condition", "")
        if _eval_condition(cond, record):
            return record.model_copy(
                update={
                    "inclusion_decision": "include",
                    "agent_notes": f"{record.agent_notes or ''} [AUTO-INCLUDED: {cond}]".strip(),
                }
            )

    return record


def _eval_condition(condition: str, record: PaperRecord) -> bool:
    condition = condition.lower()
    if "uav" in condition or "drone" in condition:
        # Auto-exclude if title contains UAV/drone without space/ground robot context
        title = record.title.lower()
        if any(w in title for w in ("uav ", "drone", "unmanned aerial")):
            if not any(
                w in title for w in ("space", "rover", "ground robot", "planetary")
            ):
                return True
    if "autonomous road" in condition or "road vehicle" in condition:
        title = record.title.lower()
        if any(
            w in title
            for w in ("autonomous driving", "self-driving car", "road vehicle")
        ):
            if not any(w in title for w in ("space", "robot", "planetary")):
                return True
    if "no abstract" in condition or "venue not in" in condition:
        if not record.abstract and record.venue not in (
            "ICRA",
            "IROS",
            "CoRL",
            "Science Robotics",
            "NeurIPS",
            "ICLR",
        ):
            return True
    return False
