# Literature Sourcing Agent — Research Context
# Systematic Review: "Surveying AI in Robotics: Towards Autonomous Space Systems"
# Target venue: MDPI Robotics (or equivalent peer-reviewed robotics/AI journal)
# Version: 3.0 — Final analytical framework incorporated

# ═══════════════════════════════════════════════════════════════════════════════
# AGENT OPERATING INSTRUCTIONS
# ═══════════════════════════════════════════════════════════════════════════════
# This CONTEXT.md configures you as a systematic literature sourcing agent for
# a structured academic review paper. Your job is NOT merely to find papers on
# a broad topic. Your job is to:
#
#   (a) Find papers that map to specific sections of a known paper structure,
#       so that the downstream writing agent has a section-ready, organised
#       library to work from.
#
#   (b) Extract and record structured metadata from each paper that feeds
#       directly into two primary analytical contributions:
#       — Section 2: A capability taxonomy heatmap of space missions, using
#         the Kunze et al. (2018) six-dimension framework.
#       — Section 4: A capability-readiness matrix assessing terrestrial AI
#         techniques against space-deployment constraints, with each technique
#         characterised using the four-level Autonomy Characterisation Scale
#         derived from Sheridan & Verplank (1978) and Parasuraman et al. (2000).
#
#   (c) Pre-group S4 papers by technique cluster to enable the writing agent
#       to construct the readiness matrix without re-reading every paper.
#
# Read the PAPER_STRUCTURE and ANALYTICAL_FRAMEWORK blocks before querying
# any database. The REVIEW_METHODOLOGY block is a procedural requirement,
# not a suggestion.
# ═══════════════════════════════════════════════════════════════════════════════


## Project Metadata
# ─────────────────────────────────────────────────────────────────────────────

PROJECT_ID: "proj_space_autonomy_review_2026"
PROJECT_TITLE: "Surveying AI in Robotics: Towards Autonomous Space Systems"
REVIEW_TYPE: "structured_narrative_systematic_review"
TARGET_JOURNAL: "MDPI Robotics (or equivalent robotics/AI journal)"
LEAD_RESEARCHER: "[Your Name]"
INSTITUTION: "University of Arizona"
ZOTERO_COLLECTION: "SpaceAutonomy_Review_2026"
DATE_INITIATED: "2026-05-20"
OUTPUT_EXCEL_PATH: "./outputs/sourcing_results.xlsx"


## Review Methodology
# ─────────────────────────────────────────────────────────────────────────────

REVIEW_METHODOLOGY:

  review_type: "Structured narrative systematic review"
  rationale: >
    This review follows a structured narrative approach rather than a
    meta-analysis or Cochrane-style protocol. Quantitative pooling of results
    is not applicable given the heterogeneity of methods and evaluation metrics
    across robotics and AI literature. Evidence is synthesised qualitatively
    by theme and mapped to a predefined paper structure, with two primary
    quantitative/structured analytical contributions embedded within the
    narrative (see ANALYTICAL_FRAMEWORK).

  prisma_tracking: true
  prisma_stages:
    - "(1) Records identified per database and query"
    - "(2) Records after deduplication"
    - "(3) Records screened on title and abstract"
    - "(4) Records excluded with primary reason code"
    - "(5) Full-text assessed (writing agent stage)"
    - "(6) Studies included in final review"
  note: >
    These counts are mandatory for the Methods section. The query_log file
    records exact query strings and search dates, also required for reproducibility.

  inclusion_criteria:
    - "Paper addresses AI, machine learning, or autonomy in robotics or space systems"
    - "Paper is a peer-reviewed journal article or peer-reviewed conference paper"
    - "OR paper is an arXiv preprint satisfying the citation quality rule below"
    - "Paper makes an empirical, architectural, or analytical contribution"
    - "Surveys and reviews of sub-fields are in scope for S2 and S3 context sections"
    - "Published 1960–2026; historical papers explicitly required for Section 2"
    - "English language or English abstract available"

  preprint_citation_quality_rule:
    # Rationale: raw citation count is a biased proxy for quality — it
    # systematically disadvantages recent work. This rule decouples quality
    # assessment from paper age. Declare in Methods section as quoted below.
    method: "citations_per_year"
    threshold: 5                     # >= 5 citations/year → eligible (loose first-pass gate)
    calculation: "total_citations / max(years_since_publication, 0.5)"
    methods_declaration: >
      "Non-peer-reviewed preprints were included if they achieved a citation
      rate of five or more citations per year. Preprints published within
      18 months of the search date were included without a citation-rate
      floor, given the rapid publication cycle in AI and robotics research."
    recency_exception:
      apply: true
      window_months: 18
      rule: >
        Papers published within the last 18 months are evaluated on
        section_fit and contribution_quality scores alone. Citation floor
        does not apply.
    historical_exception:
      apply: true
      note: >
        For papers assigned to S2 (history), citation rate is not used as
        a quality gate. Historical significance is assessed by section_fit only.

  exclusion_criteria:
    - "Pure hardware or mechanical engineering with no AI or autonomy component"
    - "Purely theoretical mathematics with no demonstrated robotics application"
    - "Duplicate of a more complete or published version of the same work"
    - "Abstract not available AND venue not in tier_1 or tier_2 venue lists"
    - "Exclusively about autonomous road vehicles with no transferable robotics contribution"
    - "Exclusively about UAVs or drones with no ground robotics or space application"
    - "Medical or surgical robotics unless HRI or shared autonomy is the primary contribution"

  search_transparency:
    record_query_strings: true
    record_search_dates: true
    record_result_counts: true
    output_file: "./outputs/query-strings.txt"
    note: >
      Required for Methods section reproducibility. Every query string used,
      the date it was executed, and the raw result count are logged verbatim.


## Analytical Framework
# ─────────────────────────────────────────────────────────────────────────────
# This block defines the two primary analytical contributions embedded in the
# review and specifies exactly what metadata the sourcing agent must collect
# to enable them. Read this block before tagging any paper.
# ─────────────────────────────────────────────────────────────────────────────

ANALYTICAL_FRAMEWORK:

  # ── ANALYTICAL CONTRIBUTION 1: Section 2 ────────────────────────────────────
  # Capability Taxonomy Heatmap of Space Missions
  # Backbone: Kunze et al. (2018) six-dimension framework
  # ────────────────────────────────────────────────────────────────────────────

  S2_CAPABILITY_TAXONOMY:
    framework_source: "Kunze, L., Hawes, N., Duckett, T., Hanheide, M., & Krajnik, T. (2018).
      Artificial intelligence for long-term robot autonomy: A survey.
      IEEE Robotics and Automation Letters, 3(4), 4023-4030."
    rationale: >
      Kunze et al. (2018) provides the most widely cited capability decomposition
      for long-term robot autonomy in the literature, decomposing the problem
      into six functional dimensions. Using this established framework as the
      backbone of the S2 taxonomy ensures methodological defensibility and
      creates a direct analytical bridge between the historical analysis in S2
      and the current-state survey in S4, both of which are assessed against
      the same six dimensions.

    six_dimensions:
      D1_navigation_mapping:
        label: "Navigation & Mapping"
        description: >
          Ability of the system to localise itself and build or use representations
          of its environment for autonomous movement. In space: terrain traversal
          without per-command uplink.
      D2_perception:
        label: "Perception"
        description: >
          Ability to interpret sensor data to identify objects, conditions, or
          events of interest. In space: onboard classification of science targets,
          hazards, and system state.
      D3_knowledge_reasoning:
        label: "Knowledge Representation & Reasoning"
        description: >
          Ability to represent and reason over knowledge about the world and the
          system's own state. In space: onboard semantic understanding, contextual
          inference, and symbolic reasoning.
      D4_planning:
        label: "Planning"
        description: >
          Ability to generate sequences of actions to achieve goals, adapt plans
          to new information, and schedule tasks under constraints.
      D5_interaction:
        label: "Interaction"
        description: >
          Ability to receive intent from and communicate state to human operators.
          In space: asynchronous, delay-tolerant HRI under communication blackouts.
      D6_learning:
        label: "Learning"
        description: >
          Ability to improve performance during operation through experience.
          In space: online adaptation without ground-side retraining or updates.

    mission_mapping_task: >
      For each S2 paper, record which space mission or system is described and
      which of the six dimensions are addressed. The writing agent will use this
      to construct a heatmap or structured comparison table showing capability
      coverage across the historical mission record. Papers that provide
      specific operational descriptions, capability limits, or quantitative
      performance data for a mission are most valuable.

    missions_to_cover_minimum:
      - "Mercury/Gemini/Apollo guidance computers"
      - "Viking landers"
      - "Voyager probes"
      - "Sojourner rover"
      - "Spirit and Opportunity rovers"
      - "Mars Reconnaissance Orbiter"
      - "Curiosity rover (incl. AEGIS, AutoNav)"
      - "Perseverance rover (incl. Ingenuity)"
      - "Canadarm2 / Dextre / SSRMS (ISS)"
      - "CIMON (ISS AI assistant)"
      - "Artemis/Gateway robotic systems (planned)"

    deployment_lag_task: >
      Secondary analytical output for S2. For each AI sub-capability that has
      appeared in a deployed space system, record:
        - ai_capability: name of the technique (e.g. "visual odometry")
        - terrestrial_first_publication_year: year of first major venue paper
        - space_deployment_year: year of confirmed operational use in space
        - deployment_lag_years: difference
        - evidence_paper: key citation for each date
      The deployment lag analysis quantifies how long AI capabilities take to
      transition from terrestrial research to space deployment. TRL discussion
      can accompany this in-text, but the primary measure is calendar-year lag
      between first significant publication and confirmed space operation.
      NOTE: Do NOT attempt to assign TRL levels — this requires expert judgment
      applied during the writing stage, not automated scoring.

    sourcing_metadata_to_collect_per_S2_paper:
      - "mission_or_system_name"
      - "primary_kunze_dimension"        # D1 through D6
      - "secondary_kunze_dimensions"     # list, up to 3
      - "operational_description_present"  # bool: does paper describe what system CAN and CANNOT do?
      - "performance_data_present"       # bool: quantitative performance reported
      - "space_heritage"                 # bool: confirmed deployed in space


  # ── ANALYTICAL CONTRIBUTION 2: Section 4 ────────────────────────────────────
  # Capability-Readiness Matrix with ACS Autonomy Characterisation
  # Backbone: Sheridan & Verplank (1978) / Parasuraman et al. (2000) / Beer et al. (2014)
  # ────────────────────────────────────────────────────────────────────────────

  S4_READINESS_MATRIX:
    rationale: >
      Section 4 surveys terrestrial AI capabilities using the same six Kunze et al.
      dimensions as Section 2, enabling direct comparison between what has been
      demonstrated in space (S3) and what terrestrial AI can currently do (S4).
      Each technique cluster within a Kunze dimension is assessed on two axes:
      (A) its current autonomy level using the four-level ACS, and
      (B) its space-deployment readiness using the four-level readiness rubric.
      Together these produce the paper's central analytical finding: the gap
      between terrestrial AI maturity and space deployability across each dimension.

    autonomy_characterisation_scale:
      name: "Autonomy Characterisation Scale (ACS)"
      derived_from:
        - "Sheridan, T.B. & Verplank, W.L. (1978). Human and computer control of
           undersea teleoperators. MIT Man-Machine Systems Laboratory Technical Report."
        - "Parasuraman, R., Sheridan, T.B., & Wickens, C.D. (2000). A model for types
           and levels of human interaction with automation. IEEE Transactions on Systems,
           Man, and Cybernetics—Part A, 30(3), 286-297."
        - "Beer, J.M., Fisk, A.D., & Rogers, W.A. (2014). Toward a framework for levels
           of robot autonomy in human-robot interaction. Journal of Human-Robot
           Interaction, 3(2), 74-99."
      compression_rationale: >
        The original Sheridan-Verplank 10-level scale and its successors were designed
        to characterise human-machine systems, not technique classes. This four-level
        compression, grounded in Parasuraman et al.'s four automation function types
        (information acquisition, information analysis, decision and action selection,
        action implementation), adapts the scale for capability-level assessment.
        Beer et al. (2014) provide the robotics-specific justification for this
        adaptation. Each ACS level is defined by observable evidence in the paper corpus,
        not by expert judgment alone, making assignments reproducible.

      levels:
        ACS_1:
          label: "Human-Operated"
          definition: >
            The technique requires continuous human input to function within its domain.
            The human performs information acquisition, analysis, decision-selection,
            and implementation. The technique assists or augments one step but does not
            close any functional loop independently.
          parasuraman_coverage: "Information acquisition only"
          observable_evidence: >
            Papers show technique operates only under direct teleoperation, explicit
            per-step commands, or continuous human supervision. No autonomous action
            sequences demonstrated.

        ACS_2:
          label: "Human-Supervised"
          definition: >
            The technique autonomously handles information acquisition and analysis,
            and executes defined action sequences, but the human sets goals, approves
            high-stakes decisions, or corrects errors. Routine sub-task loops are
            closed; the goal-selection loop remains open.
          parasuraman_coverage: "Information acquisition + information analysis"
          observable_evidence: >
            Papers demonstrate autonomous execution of scripted or parameterised
            sequences with human goal-setting or periodic approval checkpoints.
            Examples: scripted rover drives, conditional autonomy with uplink approval.

        ACS_3:
          label: "Conditionally Autonomous"
          definition: >
            The technique selects its own intermediate goals or adapts behaviour based
            on sensed conditions, operating without human input in known or expected
            conditions. Human input is requested only on edge cases or decisions above
            a defined risk threshold.
          parasuraman_coverage: "All four function types in nominal conditions"
          observable_evidence: >
            Papers demonstrate real-time goal selection, replanning, or behavioural
            adaptation without human approval in nominal conditions. May require human
            escalation for novel situations. Examples: AEGIS science targeting,
            LLM task planning in constrained domains.

        ACS_4:
          label: "Fully Autonomous"
          definition: >
            The technique completes end-to-end operation within its domain including
            goal selection, replanning on failure, and recovery from unexpected
            conditions — without requiring human input even in edge cases.
          parasuraman_coverage: "All four function types including failure handling"
          observable_evidence: >
            Papers demonstrate sustained, uninterrupted closed-loop operation over
            extended periods with no human intervention required, including failure
            recovery. This level is rare in the current literature for any single
            technique in isolation.

      assignment_rule: >
        Assign the ACS level routinely demonstrated in the best published empirical
        results within the technique cluster's corpus — not the theoretical ceiling,
        not the average paper. Where papers within a cluster span multiple ACS levels,
        report the modal level and note the spread in the evidence column.
        The assignment is made by the writing agent during synthesis, not the sourcing
        agent. The sourcing agent records the metadata that enables this assignment.

    space_deployment_readiness_rubric:
      name: "Space Deployment Readiness Rubric (SDRR)"
      levels:
        SDRR_3:
          label: "Space-Ready"
          criteria: >
            Published evidence of the technique operating on space-qualified hardware
            (RAD750/SpaceCube class or demonstrated equivalent), OR confirmed
            operational deployment on a space mission, OR demonstrated in a
            formally recognised space-analogous environment (Antarctic long-duration
            deployment, deep subsea, NASA HERA human analog). Evidence must be cited.

        SDRR_2:
          label: "Deployment-Candidate"
          criteria: >
            Published results on edge or embedded hardware with resource constraints
            comparable to space-qualified compute; AND at least one published work
            addressing radiation, thermal, or long-duration reliability for this
            capability class; AND communication-delay compatibility discussed in at
            least one paper in the cluster. All three criteria must be met.

        SDRR_1:
          label: "Research-Mature"
          criteria: >
            State of the art clearly established at ICRA/IROS/CoRL/NeurIPS tier venues
            with real-robot demonstrations on physical systems. No published work
            directly addressing space-specific deployment constraints.

        SDRR_0:
          label: "Pre-Deployment"
          criteria: >
            Primarily simulation results or proof-of-concept demonstrations.
            Physical robot deployment limited or absent. Space applicability
            not discussed in the literature.

      assignment_rule: >
        Assignments are made by the writing agent during synthesis, not the sourcing
        agent. The sourcing agent records the boolean metadata flags
        (deployment_constraints_discussed, compute_requirements_noted, space_heritage,
        radiation_robustness_discussed) that enable these assignments.
        A paper must provide cited evidence for SDRR_3; the rubric is not a judgment
        call but an evidence-based classification.

    technique_cluster_list:
      # Pre-defined technique clusters per Kunze et al. dimension.
      # The sourcing agent assigns each S4 paper to one primary cluster.
      # Final cluster definitions are confirmed by the researcher after
      # first-pass sourcing — clusters with fewer than 3 included papers
      # may be merged at that stage.
      D1_navigation_mapping:
        - "visual_odometry"
        - "lidar_slam"
        - "learning_based_navigation"
        - "terrain_traversability"
        - "path_planning_classical"
        - "multi_sensor_fusion_nav"
      D2_perception:
        - "object_recognition_deep_learning"
        - "visual_language_models"
        - "3d_scene_understanding"
        - "sensor_fusion_perception"
        - "anomaly_detection"
      D3_knowledge_reasoning:
        - "classical_planning_pddl"
        - "behaviour_trees"
        - "llm_task_planning"
        - "neuro_symbolic_reasoning"
        - "knowledge_graphs_robotics"
      D4_planning:
        - "llm_policy_generation"
        - "hierarchical_task_planning"
        - "evolutionary_policy_search"
        - "model_predictive_control"
        - "behaviour_tree_llm_hybrid"
      D5_interaction:
        - "shared_autonomy_frameworks"
        - "natural_language_hri"
        - "delayed_teleoperation"
        - "adaptive_autonomy"
        - "robot_safety_ethics"
      D6_learning:
        - "reinforcement_learning_control"
        - "imitation_learning"
        - "sim_to_real_transfer"
        - "continual_lifelong_learning"
        - "meta_learning"
        - "online_learning_deployment"
      ALIGNMENT:
        - "specification_gaming_reward_hacking"
        - "goal_misgeneralisation"
        - "proxy_collapse"
        - "compositional_misalignment_modular"
        - "scalable_oversight_robotics"
        - "inter_module_diagnostic_oversight"
        - "embodied_ai_safety_evaluation"
        - "alignment_space_robotics"

      cluster_assignment_confidence:
        levels: ["high", "medium", "low"]
        rules:
          high: "Abstract clearly describes a single technique matching one cluster"
          medium: "Paper spans two clusters or uses hybrid approach"
          low: "No clear cluster match from abstract alone; needs full-text review"
        note: >
          The researcher reviews all medium and low confidence assignments
          after sourcing before handing to the writing agent. This is a
          required human stage between sourcing and writing.

    bibliometric_trend_data:
      purpose: >
        Descriptive support for the S4 narrative. Publication volume per
        Kunze dimension per year (2015–2025) characterises how research
        emphasis has shifted. This is presented as a descriptive figure
        supporting the narrative, not as a primary analytical claim.
        It requires only the year and primary_section fields already
        collected for every S4 paper — no additional sourcing is needed.
      output_format: "raw counts per year per Kunze dimension, suitable for
        plotting as line chart, bar chart, or heat map at writing stage"
      note: >
        The writing agent selects the most appropriate visualisation form
        after reviewing the data distribution. The sourcing agent does not
        prescribe chart type.


## Paper Structure & Section Mapping
# ─────────────────────────────────────────────────────────────────────────────

PAPER_STRUCTURE:

  S1_INTRODUCTION:
    title: "Introduction"
    kunze_dimensions_relevant: []
    purpose: >
      Establishes the operational case for autonomous space systems. Argues that
      growing space exploration ambitions combined with communication latency
      constraints (20+ minutes one-way to Mars) make robotic autonomy not merely
      desirable but operationally necessary. Introduces the review structure and
      motivates the Kunze et al. framework as the analytical backbone.
    papers_needed:
      - "Mission architecture documents quantifying communication delay constraints"
      - "High-level autonomy surveys framing the integration problem"
      - "Papers on the cost or limitation of human-in-the-loop at planetary distances"
    section_tag: "S1:introduction"
    target_paper_count: 10-20

  S2_SPACE_AUTONOMY_HISTORY:
    title: "Space Autonomy Through History"
    kunze_dimensions_relevant: ["D1", "D2", "D3", "D4", "D5", "D6"]
    purpose: >
      Analytical account of how autonomy capability has grown across the six
      Kunze et al. dimensions over the history of space systems. NOT a
      chronological catalogue of missions — a structured assessment of which
      capabilities have developed, which remain primitive, and the trajectory
      this implies. Provides the historical baseline against which S3 and S4
      are compared.
    papers_needed:
      - "Apollo guidance computer and early spacecraft automation"
      - "Viking, Voyager, and probe autonomy systems"
      - "Mars rover systems: Sojourner, Spirit/Opportunity, Curiosity, Perseverance"
      - "AEGIS and AutoNav operational documentation"
      - "ISS robotic systems: Canadarm2, Dextre, CIMON"
      - "Surveys of space robotics autonomy history"
      - "NASA/ESA technical reports with operational capability descriptions"
    section_tag: "S2:history"
    target_paper_count: 25-40
    date_range_override:
      start_year: 1960
      end_year: 2026
      strict: false
      note: "Historical papers must not be penalised for age or citation rate"
    analytical_outputs:
      primary: "Capability taxonomy heatmap — missions × Kunze dimensions (see ANALYTICAL_FRAMEWORK.S2_CAPABILITY_TAXONOMY)"
      secondary: "Deployment lag analysis — terrestrial first publication vs space deployment year"

  S3_AI_IN_SPACE:
    title: "Artificial Intelligence in Space"
    kunze_dimensions_relevant: ["D1", "D2", "D3", "D4", "D5"]
    purpose: >
      Surveys AI actually deployed or in near-deployment in space systems.
      Positioned BEFORE S4 to establish what has made it to space — the
      baseline against which terrestrial capability (S4) is compared.
      Shows that space AI adoption has been narrow and module-specific,
      with individual capabilities applied in isolation and no integration
      of the kind S5 advocates. The key standard is DEPLOYMENT or
      NEAR-DEPLOYMENT with mission heritage — not theoretical proposals.
    subsections:
      S3a_AI_SPACE_ROBOTICS:
        title: "Artificial Intelligence in Space Robotics"
        purpose: >
          AI in robotic systems operating in space: rover perception and
          navigation, autonomous science targeting (AEGIS), arm manipulation
          (Canadarm, Dextre), and upcoming lunar/Mars systems.
        section_tag: "S3a:ai-space-robotics"
        target_paper_count: 20-30
      S3b_AI_SPACECRAFT:
        title: "Artificial Intelligence in Spacecraft Systems"
        purpose: >
          Spacecraft-level AI beyond robotics: fault detection and diagnosis,
          autonomous scheduling, onboard science processing. Demonstrates that
          AI adoption is narrow across the full discipline.
        section_tag: "S3b:ai-spacecraft"
        target_paper_count: 10-20
    section_tag: "S3:ai-in-space"
    target_paper_count: 30-50

  S4_AI_IN_ROBOTICS:
    title: "Artificial Intelligence in Robotics"
    kunze_dimensions_relevant: ["D1", "D2", "D3", "D4", "D5", "D6"]
    purpose: >
      Reviews terrestrial AI capabilities using the same six Kunze et al.
      dimensions. Positioned after S3 so the section functions as a capability
      baseline revealing the gap between what has gone to space (S3) and what
      terrestrial AI can do. Each subsection corresponds to one Kunze dimension.
      Each subsection concludes with an assessment using the ACS and SDRR
      frameworks. The gap between S3 and S4 motivates S5.
    subsections:
      S4a_NAVIGATION_MAPPING:
        title: "Navigation and Mapping"
        kunze_dimension: "D1"
        section_tag: "S4a:navigation"
        target_paper_count: 15-25
      S4b_PERCEPTION:
        title: "Perception"
        kunze_dimension: "D2"
        section_tag: "S4b:perception"
        target_paper_count: 15-25
      S4c_KNOWLEDGE_REASONING:
        title: "Knowledge Representation and Reasoning"
        kunze_dimension: "D3"
        section_tag: "S4c:reasoning"
        target_paper_count: 20-30
      S4d_PLANNING:
        title: "Planning"
        kunze_dimension: "D4"
        section_tag: "S4d:planning"
        target_paper_count: 20-30
      S4e_INTERACTION:
        title: "Human-Robot Interaction"
        kunze_dimension: "D5"
        section_tag: "S4e:interaction"
        target_paper_count: 15-25
      S4f_LEARNING:
        title: "Learning"
        kunze_dimension: "D6"
        section_tag: "S4f:learning"
        target_paper_count: 15-25

      S4g_ALIGNMENT:
        title: "AI Alignment in Robotic Systems"
        kunze_dimension: "cross-cutting (D5/D6 boundary)"
        purpose: >
          Reviews the AI alignment problem as it applies specifically to robotic
          systems. Covers three main areas: (1) canonical misalignment mechanisms
          in robotic contexts — specification gaming, goal misgeneralisation,
          reward hacking/proxy collapse — drawing on both the general alignment
          literature and robotics-specific instantiations; (2) compositional
          misalignment in modular robotic architectures, where separately trained
          architecturally distinct modules (SLAM, LLM planners, RL controllers)
          are composed through typed interfaces, and the assumption that
          individually aligned modules compose into a globally aligned system is
          empirically untested; (3) oversight and scalable alignment mechanisms
          adapted to robotic deployment constraints (communication delays, limited
          human bandwidth, physical irreversibility). The space robotics context
          is treated as a particularly high-stakes and analytically valuable
          model organism for alignment research.
        papers_needed:
          - "General alignment problem framing relevant to robotic systems"
          - "Specification gaming and reward hacking in RL and robotics"
          - "Goal misgeneralisation under distributional shift in embodied agents"
          - "Compositional safety and safety-is-not-compositional in embodied AI"
          - "Embodied AI security and module-level vs system-level evaluation"
          - "Scalable oversight mechanisms: debate, weak-to-strong, AI control"
          - "Hierarchical oversight in robotic and multi-agent systems"
          - "Inter-module diagnostic protocols and alignment signalling"
          - "AI alignment implications for space robotics specifically"
          - "Emergent misalignment and proxy collapse in deployed systems"
        section_tag: "S4g:alignment"
        target_paper_count: 20-30
        note: >
          This subsection is cross-cutting: alignment draws on D6 (learning
          dynamics produce misalignment), D5 (interaction/oversight mechanisms
          address it), and D4 (planning misspecification is a core failure mode).
          Tag papers with their primary Kunze dimension AND the alignment tag.
          Papers from the broader AI alignment literature (not robotics-specific)
          are in scope if they have direct implications for robotic or embodied
          deployment — flag these as secondary_source_context:true.
          The proposal by the lead researcher (Schmidt Sciences Tier 1, 2026) on
          compositional misalignment in hierarchical robotic systems provides the
          primary framing for the compositional alignment subsection.
    section_tag: "S4:ai-in-robotics"
    target_paper_count: 120-190
    analytical_outputs:
      primary: >
        Capability-readiness matrix: technique clusters × space-deployment
        constraints, rated on SDRR (0–3), with ACS level per cluster.
        Visualisation format (table, heatmap, radar chart) determined at
        writing stage based on data volume and distribution.
      secondary: >
        Bibliometric trend: publication volume per Kunze dimension per year
        (2015–2025). Descriptive support for narrative; visualisation format
        determined at writing stage.
    note_on_section_mapping: >
      NOTE: The previous version of this file used S4a=HRI, S4b=Perception, etc.
      This version realigns subsections to Kunze et al. dimensions:
      S4a=Navigation&Mapping, S4b=Perception, S4c=KR&Reasoning,
      S4d=Planning, S4e=Interaction, S4f=Learning.
      Update keyword clusters and Zotero subcollection names accordingly.

  S5_NEW_PARADIGMS:
    title: "New Paradigms in Artificial Intelligence for Autonomous Robotics"
    kunze_dimensions_relevant: ["D1", "D2", "D3", "D4", "D5", "D6"]
    purpose: >
      Discusses emerging integrative approaches that go beyond individual AI
      modules. Argues that the next step is not better individual capabilities
      in any single Kunze dimension but better integration across all six —
      exactly the gap Kunze et al. identified in 2018 and confirmed in S3/S4.
    subsections:
      S5a_MULTIMODALITY:
        title: "Multi-modality and Foundation Models"
        purpose: >
          Large multimodal models (VLAs), foundation models for robotics
          (RT-2, PaLM-E, Gato), the PPA paradigm. How does multi-modality
          begin to address integration across Kunze dimensions?
        section_tag: "S5a:multimodality"
        target_paper_count: 15-25
      S5b_MACHINE_BRAIN:
        title: "Bio-inspiration and Cognitive Architectures"
        purpose: >
          Brain-inspired approaches to the integration problem: whole brain
          probabilistic generative models, spiking neural networks (BrainCog),
          cognitive architectures (ACT-R, SOAR), embodied cognition. The machine
          brain concept as a unifying design principle across Kunze dimensions.
        section_tag: "S5b:machine-brain"
        target_paper_count: 20-30
      S5c_INTEGRATION_PROTOCOLS:
        title: "Standardisation and Inter-Module Communication"
        purpose: >
          Can a standardised communication protocol for AI modules in robots
          (analogous to MCP for LLMs) address the integration problem?
          ROS/ROS2 as existing middleware; MCP and A2A as emerging AI-native
          protocols; multi-agent coordination architectures.
        section_tag: "S5c:integration-protocols"
        target_paper_count: 10-20
    section_tag: "S5:new-paradigms"
    target_paper_count: 45-75

  S6_FUTURE_DIRECTIONS:
    title: "Future Directions for Space Autonomy"
    kunze_dimensions_relevant: ["D1", "D2", "D3", "D4", "D5", "D6"]
    purpose: >
      Synthesises gaps identified across S2–S5 and maps them to research
      priorities. Structured around the Kunze dimensions: for each dimension,
      what is the current space readiness (from S3/S4 matrix) and what
      research is needed to close the gap? Includes evaluation and benchmarking
      gaps, AI safety and alignment implications of increasing autonomy, and
      security considerations for autonomous space systems.
    papers_needed:
      - "Gap analyses and roadmaps for space robotics autonomy"
      - "AI safety and alignment in autonomous systems"
      - "Security of autonomous space systems"
      - "Agency roadmaps: NASA, ESA, JAXA autonomy plans"
      - "Evaluation and benchmarking frameworks for long-term autonomy"
    section_tag: "S6:future-directions"
    target_paper_count: 15-25


## Research Question
# ─────────────────────────────────────────────────────────────────────────────

RESEARCH_QUESTION: |
  What is the current state of artificial intelligence across the six functional
  dimensions of long-term robot autonomy identified by Kunze et al. (2018) —
  navigation and mapping, perception, knowledge representation and reasoning,
  planning, interaction, and learning — how has capability in each dimension
  evolved within space systems specifically, and what emerging integrative AI
  paradigms are best positioned to advance autonomous space robotics toward
  the sustained, independent operation required for future planetary exploration?

  Operational framing: Given that space robotic systems have demonstrated
  narrow AI capability in individual dimensions (notably navigation and
  perception) but consistently lack integration across dimensions and in
  particular the interaction and learning dimensions, what does the terrestrial
  AI literature reveal about the path from narrow capability to integrated
  autonomy, and what constraints specific to space deployment limit that path?


## Extended Research Context
# ─────────────────────────────────────────────────────────────────────────────

EXTENDED_CONTEXT: |
  ## REVIEW FRAMING

  This review is motivated by two converging pressures: (1) rapidly expanding
  space exploration ambitions — crewed Mars missions, sustained lunar surface
  operations, deep-space science probes — that impose communication latency
  constraints (20+ minutes one-way to Mars) making real-time teleoperation
  impractical; and (2) rapid advances in AI capability that have not yet been
  systematically applied to the space robotics domain, particularly in the
  dimensions of knowledge reasoning, interaction, and learning.

  The review's analytical backbone is the Kunze et al. (2018) finding that
  AI sub-disciplines have developed techniques that, when re-integrated within
  an autonomous system, can enable long-term autonomy — but that this
  re-integration has not been achieved, particularly for interaction and
  learning, even where individual sub-disciplines have matured considerably.
  This review assesses how much progress has been made since 2018, what the
  state of the art looks like in each dimension, and how far that state of the
  art is from space deployment.

  ## SECTION-SERVING PAPER GUIDANCE

  S1 (Introduction): Papers establishing the operational stakes — communication
  latency analyses, mission architecture constraints, high-level surveys framing
  the autonomy problem. Must support a specific quantitative or qualitative claim.

  S2 (History — analytical): Papers describing operational capabilities of
  specific space missions or systems. Older papers are often more valuable than
  recent ones for this section. Prioritise papers containing operational
  descriptions, performance limits, or mission documentation. NASA technical
  reports are primary sources. Do NOT penalise for age.

  S3 (AI in Space): DEPLOYMENT or NEAR-DEPLOYMENT only. Real systems with
  mission heritage. Blue-sky proposals score lower. This section establishes
  the space-side baseline that S4 is compared against.

  S4 (AI in Robotics — analytical): Organised by Kunze dimension. Tag every
  paper with its primary Kunze dimension (D1–D6) and a technique cluster
  from the predefined list. Record deployment_constraints_discussed,
  compute_requirements_noted, radiation_robustness_discussed, and space_heritage
  boolean flags — these are essential for the writing agent to assign SDRR
  ratings. Year and citation_count are required for the bibliometric trend.

  S5 (New Paradigms): Forward-looking integrative approaches. Papers arguing
  for or demonstrating integration across multiple Kunze dimensions are
  particularly valuable. Cognitive architecture and multimodal foundation
  model papers are highest priority.

  S6 (Future Directions): Gap analyses, roadmaps, safety/alignment papers.
  Papers that identify specific research needs at the intersection of space
  constraints and Kunze dimension gaps are most useful.

  ## KEY KNOWN PAPERS (AUTO-INCLUDE)

  - Kunze et al. (2018) — AI for Long-Term Robot Autonomy: A Survey
    [S1, S4 cross-cutting backbone — all six Kunze dimensions]
  - Sheridan & Verplank (1978) — Human and Computer Control of Undersea Teleoperators
    [Methods — ACS framework foundation]
  - Parasuraman, Sheridan & Wickens (2000) — A Model for Types and Levels of
    Human Interaction with Automation [Methods — ACS framework]
  - Beer, Fisk & Rogers (2014) — Toward a Framework for Levels of Robot Autonomy
    in HRI [Methods — ACS robotics adaptation]
  - Reddy et al. (2018) — Shared Autonomy via Deep Reinforcement Learning
    [S4e:interaction, S4f:learning]
  - He et al. (2022) — Human-Centered AI for Trustworthy Robots [S4e:interaction]

  AI Alignment papers (S4g — auto-include):
  - Ngo et al. (2022) — The Alignment Problem from a Deep Learning Perspective
    [S4g — general alignment framing; primary theoretical anchor]
  - Hubinger et al. (2019) — Risks from Learned Optimization in Advanced ML Systems
    [S4g — mesa-optimisation and inner alignment; reward hacking framing]
  - Langosco et al. (2022) — Goal Misgeneralisation in Deep Reinforcement Learning
    [S4g — canonical goal misgeneralisation; ICML 2022]
  - Shah et al. (2022) — Goal Misgeneralisation: Why Correct Specs Aren't Enough
    [S4g — goal misgeneralisation under distributional shift]
  - Skalse et al. (2022) — Defining and Characterizing Reward Gaming [NeurIPS 2022]
    [S4g — specification gaming taxonomy]
  - Chan et al. (2023) — Harms from Increasingly Agentic AI
    [S4g, S6 — agentic AI risks and oversight]
  - Hammond et al. (2025) — Multi-Agent Risks from Advanced AI [arXiv:2502.14143]
    [S4g — multi-agent misalignment; homogeneous LLM collectives; boundary reference]
  - Embodied AI Security Survey (2025) — arXiv:2502.13175
    [S4g — 'safety is not compositional'; module isolation gap; primary compositional framing]
  - Greenblatt et al. (2023) — AI Control [arXiv:2312.06942]
    [S4g — AI control framework for oversight under capability gaps]
  - Khan et al. (2024) — Debating with More Persuasive LLMs [NeurIPS 2024]
    [S4g — scalable oversight via debate mechanism]
  - Kenton et al. (2024) — On Scalable Oversight with Weak LLMs [NeurIPS 2024]
    [S4g — weak-to-strong generalisation for oversight]
  - Baker et al. (2025) — Specification Gaming in Reward Models [arXiv:2503.11926]
    [S4g — reward model proxy collapse; recent]
  - Betley et al. (2025) — Emergent Misalignment [arXiv:2502.17424]
    [S4g — emergent misalignment from narrow finetuning; recent]
  - Microsoft AI Red Team (2025) — Taxonomy of Failure Modes in Agentic AI
    [S4g — agentic failure taxonomy; boundary reference for compositional gap]

  ## FRAMEWORKS CONSIDERED BUT NOT ADOPTED AS PRIMARY

  The following were evaluated and discussed but not adopted as the primary
  analytical framework. They should be cited and discussed in the Methods section:

  - Clough (2002) ACL: 11-level OODA-based scale, designed for UAV defence
    applications. OODA framing maps naturally onto Kunze dimensions but the scale
    was designed for system-level rather than technique-level characterisation,
    and its defence/UAV context requires justification for robotics application.
    Cited as a considered alternative.

  - Hobbs et al. (2022) STARLs: Two-dimensional scale (Autonomy Readiness Level +
    Trust Readiness Level) developed by NASA/USSF/NRO partnership. Highly relevant
    provenance for a space-focused review. Too recent for primary adoption (2022
    conference preprint, limited adoption outside originating organisations).
    Cited as corroborating motivation for the need for space-specific autonomy
    assessment frameworks.

  - Baker & Phillips (2025) Spacecraft Autonomy Levels: Six-level SAE-parallel
    scale for spacecraft systems specifically. Very recent (March 2025 preprint),
    no citation history yet. Cited as a contemporary parallel validating the
    ACS approach and extending it toward the spacecraft systems perspective.

  - Endsley & Kaber (1999) ten-level LOA taxonomy: Uses the same four cognitive
    functions (monitoring, generating, selecting, implementing) as Parasuraman
    et al. and offers richer granularity. Not adopted as primary because the
    full 10-level scale does not compress cleanly to 4 levels without losing
    distinction between key adjacent levels. Cited as a predecessor framework.

  - Option C (Kunze-derived reactive/deliberative/integrated scale): Internally
    consistent with the Kunze backbone and maps directly onto the integration
    argument. Adopted for in-text discussion and as the conceptual language for
    describing capability maturity, but not as the formal scored dimension in
    the readiness matrix — the ACS provides a more established and citable basis
    for the formal assessment.

  ## KNOWN EXCLUSIONS

  - Pure hardware/mechanical engineering without AI or autonomy component
  - Autonomous road vehicles without transferable robotics contribution
  - UAVs/drones without ground robotics or space application
  - Medical/surgical robotics unless HRI or shared autonomy is primary
  - NLP/LLM papers without physical robot application
  - General AI ethics papers without robotics-specific alignment content
  - Reviews and meta-analyses are IN SCOPE for S2/S3 but must be tagged
    secondary_source:true to distinguish from primary research contributions


## Search Keywords
# ─────────────────────────────────────────────────────────────────────────────
# Aligned to Kunze et al. dimensions and paper sections.
# ─────────────────────────────────────────────────────────────────────────────

KEYWORDS:
  tier_1:
    - "autonomous robot OR robotic autonomy OR autonomous robotics"
    - "artificial intelligence OR machine learning OR deep learning"

  tier_2:
    clusters:

      # ── S1/S2: Space history and motivation ──────────────────────────────
      space_history_cluster:
        - "space robotics history"
        - "Mars rover autonomy"
        - "planetary rover autonomous navigation"
        - "Apollo guidance computer"
        - "spacecraft autonomy history"
        - "AEGIS autonomous science"
        - "AutoNav rover navigation"
        - "ISS robotic systems"
        - "Canadarm Dextre space manipulator"
        - "deep space probe autonomy"
        - "Perseverance Curiosity rover AI"
        - "long-term robot autonomy space"

      # ── S3: AI in space (deployed) ────────────────────────────────────────
      ai_space_cluster:
        - "artificial intelligence space mission deployed"
        - "onboard AI spacecraft"
        - "autonomous science detection space"
        - "fault detection diagnosis spacecraft"
        - "autonomous scheduling space mission"
        - "CIMON space AI"
        - "onboard machine learning satellite"
        - "AI lunar robotics"

      # ── S4a: D1 Navigation & Mapping ─────────────────────────────────────
      navigation_cluster:
        - "SLAM simultaneous localisation mapping robot"
        - "autonomous navigation unstructured environment"
        - "terrain traversability planetary rover"
        - "LiDAR mapping robot"
        - "visual odometry robot"
        - "path planning autonomous robot"
        - "robot navigation learning deep"

      # ── S4b: D2 Perception ───────────────────────────────────────────────
      perception_cluster:
        - "robot perception deep learning"
        - "visual language model robot"
        - "sensor fusion robotics"
        - "object recognition robot"
        - "scene understanding autonomous robot"
        - "3D perception point cloud robot"
        - "vision language action model robotics"

      # ── S4c: D3 Knowledge Representation & Reasoning ────────────────────
      reasoning_cluster:
        - "knowledge representation robotics"
        - "neuro-symbolic robot reasoning"
        - "large language model robot planning"
        - "behaviour tree robot"
        - "PDDL robot planning"
        - "semantic reasoning autonomous robot"
        - "foundation model robot reasoning"

      # ── S4d: D4 Planning ─────────────────────────────────────────────────
      planning_cluster:
        - "robot task planning LLM"
        - "hierarchical task planning robot"
        - "LLM policy robot"
        - "evolutionary algorithm robot policy"
        - "model predictive control robot"
        - "long-horizon planning robot"

      # ── S4e: D5 Interaction ──────────────────────────────────────────────
      interaction_cluster:
        - "human robot interaction"
        - "shared autonomy robot"
        - "shared control robot"
        - "teleoperation autonomous robot delay"
        - "natural language robot interface"
        - "LLM human robot interaction"
        - "trustworthy autonomous robot"
        - "robot safety framework"
        - "adaptive autonomy level"

      # ── S4f: D6 Learning ─────────────────────────────────────────────────
      learning_cluster:
        - "reinforcement learning robot control"
        - "sim-to-real transfer robot"
        - "imitation learning robot"
        - "continual learning robotics"
        - "online learning autonomous robot"
        - "long-term robot autonomy learning"
        - "meta-learning robotics"

      # ── S5: New paradigms ────────────────────────────────────────────────
      multimodal_cluster:
        - "multimodal foundation model robot"
        - "vision language action model"
        - "RT-2 PaLM-E robotics transformer"
        - "embodied AI multimodal"
        - "Gato generalist robot agent"
        - "perceive plan act robot"

      machine_brain_cluster:
        - "cognitive architecture robot"
        - "brain-inspired AI robot"
        - "whole brain architecture AI"
        - "spiking neural network robot"
        - "neuromorphic computing robot"
        - "embodied cognition robot"
        - "ACT-R SOAR cognitive architecture robotics"
        - "probabilistic generative model cognitive robot"

      integration_cluster:
        - "modular robot architecture interoperability"
        - "robot middleware ROS"
        - "AI module communication robot"
        - "multi-agent robot system"
        - "model context protocol AI agent"
        - "standardisation AI robotics"

      # ── S4g: AI Alignment ────────────────────────────────────────────────
      alignment_cluster:
        - "AI alignment robotic systems"
        - "reward hacking specification gaming robotics"
        - "goal misgeneralisation distributional shift robot"
        - "compositional safety modular AI robot"
        - "embodied AI safety evaluation system-level"
        - "scalable oversight robot autonomy"
        - "inter-module alignment diagnostic robot"
        - "proxy objective collapse robot deployment"
        - "corrigibility safe autonomous robot"
        - "AI alignment space robotics"
        - "value alignment embodied agent"
        - "robustness misalignment hierarchical robot"

      # ── S6: Future directions ────────────────────────────────────────────
      future_cluster:
        - "space robotics roadmap future autonomy"
        - "AI alignment autonomous robot"
        - "security autonomous space system"
        - "robot autonomy evaluation benchmark"
        - "NASA ESA autonomy roadmap"

  tier_3:
    - "Perseverance rover"
    - "Curiosity rover"
    - "AEGIS"
    - "AutoNav"
    - "CIMON"
    - "RT-2"
    - "PaLM-E"
    - "Gato"
    - "ROS2"
    - "BrainCog"
    - "SayCan SayPlan"
    - "behavior tree"
    - "PDDL"
    - "sim-to-real"
    - "long-term autonomy"
    - "communication delay teleoperation"
    - "Mars communication latency"
    - "RAD750"
    - "SpaceCube"
    - "radiation hardened compute"


## Source Databases
# ─────────────────────────────────────────────────────────────────────────────

DATABASES:
  - name: "Semantic Scholar"
    type: "open_access_api"
    priority: 1
    enabled: true
    api: "SemanticScholar_Graph_v1"
    max_results_per_query: 200

  - name: "arXiv"
    type: "open_access_api"
    priority: 2
    enabled: true
    api: "arXiv_REST"
    categories: ["cs.RO", "cs.AI", "cs.LG", "cs.SY"]
    max_results_per_query: 150

  - name: "IEEE Xplore"
    type: "paywalled_browser"
    priority: 3
    enabled: true
    login_method: "institutional_sso"
    credential_env_vars:
      username: "IEEE_USERNAME"
      password: "IEEE_PASSWORD"
      proxy_url: "IEEE_PROXY_URL"
    max_results_per_query: 150
    note: "Critical: ICRA, IROS, AERO, RA-L, T-RO. IEEE AERO for space papers."

  - name: "Web of Science"
    type: "paywalled_browser"
    priority: 4
    enabled: true
    login_method: "institutional_sso"
    credential_env_vars:
      username: "WOS_USERNAME"
      password: "WOS_PASSWORD"
      proxy_url: "WOS_PROXY_URL"
    max_results_per_query: 150

  - name: "Scopus"
    type: "paywalled_browser"
    priority: 5
    enabled: true
    login_method: "institutional_sso"
    credential_env_vars:
      username: "SCOPUS_USERNAME"
      password: "SCOPUS_PASSWORD"
      proxy_url: "SCOPUS_PROXY_URL"
    max_results_per_query: 150

  - name: "ACM Digital Library"
    type: "paywalled_browser"
    priority: 6
    enabled: true
    login_method: "institutional_sso"
    credential_env_vars:
      username: "ACM_USERNAME"
      password: "ACM_PASSWORD"
      proxy_url: "ACM_PROXY_URL"
    max_results_per_query: 100
    note: "HRI conference proceedings (ACM/IEEE HRI)"

  - name: "NASA Technical Reports Server"
    type: "open_access_api"
    priority: 7
    enabled: true
    api: "NASA_NTRS_REST"
    max_results_per_query: 100
    note: "Essential for S2 and S3. Mission operations reports are primary sources."

  - name: "PubMed"
    type: "open_access_api"
    priority: 8
    enabled: false
    note: "Disabled — biomedical focus, near-zero yield for this topic"

  - name: "JSTOR"
    type: "paywalled_browser"
    priority: 9
    enabled: false
    note: "Disabled — low yield for CS/engineering"


## Date & Publication Filters
# ─────────────────────────────────────────────────────────────────────────────

FILTERS:
  date:
    default_start_year: 2015
    default_end_year: 2026
    section_overrides:
      S2_history:
        start_year: 1960
        end_year: 2026
        strict: false
      S3_ai_in_space:
        start_year: 2000
        end_year: 2026
        strict: false
    strict: false
    note: "Flag out-of-range rather than hard-exclude. Important historical papers must not be lost."

  publication_types:
    include:
      - "Journal Article"
      - "Conference Paper"
      - "Workshop Paper"
      - "Technical Report"
      - "Preprint"
    exclude:
      - "Editorial"
      - "Letter"
      - "Thesis"

  publication_venues_priority:
    tier_1:
      - "ICRA"
      - "IROS"
      - "CoRL"
      - "Science Robotics"
      - "IEEE Transactions on Robotics"
      - "IEEE Robotics and Automation Letters"
      - "Journal of Field Robotics"
      - "Autonomous Robots"
      - "NeurIPS"
      - "ICLR"
      - "ICML"
    tier_2:
      - "AERO"
      - "HRI"
      - "IJCAI"
      - "AAAI"
      - "RSS"
      - "MDPI Robotics"
      - "Frontiers in Robotics and AI"
      - "Journal of Human-Robot Interaction"

  language:
    include: ["English"]
    exclude_if_no_english_abstract: true

  open_access_only: false

  secondary_source_flag:
    enabled: true
    note: "Tag survey and review papers as secondary_source:true"


## Relevance Scoring Parameters
# ─────────────────────────────────────────────────────────────────────────────

RELEVANCE_SCORING:
  dimensions:
    section_fit:
      weight: 0.55
      description: >
        Does this paper clearly serve at least one paper section? Can the
        writing agent use it to make a specific, citable claim or provide
        data for the analytical frameworks?

    contribution_quality:
      weight: 0.30
      description: >
        Does the paper make a substantive empirical, architectural, or analytical
        contribution with physical robot experiments or mission heritage?

    recency_and_relevance:
      weight: 0.15
      description: >
        Current enough to represent state of the art? S2 historical papers
        are assessed on historical significance, not recency.

  thresholds:
    include: 7.0
    maybe: 5.0
    exclude: 0.0

  scoring_basis: "title_and_abstract"
  parallel_batch_size: 10

  section_assignment_instructions: |
    For every paper scored above the exclude threshold:
    1. Assign a PRIMARY section tag
    2. Assign up to 2 SECONDARY section tags
    3. For S4 papers: assign primary Kunze dimension (D1–D6) AND
       technique cluster from the predefined cluster list
    4. Record cluster_assignment_confidence (high/medium/low)
    5. Flag secondary_source:true if paper is itself a survey/review
    6. Flag cross_cutting:true if paper serves 3 or more sections
    7. Record boolean metadata: deployment_constraints_discussed,
       compute_requirements_noted, radiation_robustness_discussed,
       space_heritage, operational_description_present

  venue_bonus:
    apply: true
    venues: ["ICRA", "IROS", "CoRL", "Science Robotics",
             "IEEE Transactions on Robotics", "NeurIPS", "ICLR", "AERO"]
    bonus: 0.5
    cap_at: 10.0

  auto_include_rules:
    - condition: "paper is a known seed paper listed in EXTENDED_CONTEXT"
      action: "include"
    - condition: "cited > 200 times AND section_fit >= 7 AND venue in tier_1"
      action: "bump_to_include"
    - condition: "paper is NASA or ESA technical report on rover/spacecraft autonomy"
      action: "bump_to_include"

  auto_exclude_rules:
    - condition: "paper is purely about UAV flight with no ground robot or space application"
      action: "exclude"
    - condition: "paper is about autonomous road vehicles with no transferable claim"
      action: "exclude"
    - condition: "no abstract AND venue not in tier_1 or tier_2"
      action: "exclude"


## Deduplication
# ─────────────────────────────────────────────────────────────────────────────

DEDUPLICATION:
  primary_key: "DOI"
  fallback_key: "title_fuzzy_match"
  fuzzy_threshold: 0.92
  on_duplicate: "keep_highest_scoring_source"
  arxiv_published_handling:
    action: "keep_published_version"
    note: "Store arXiv ID as secondary field when published version exists"


## Output Configuration
# ─────────────────────────────────────────────────────────────────────────────

OUTPUT:
  zotero:
    enabled: true
    collection_name: "SpaceAutonomy_Review_2026"
    subcollections:
      - "S1_Introduction"
      - "S2_SpaceAutonomyHistory"
      - "S3_AIinSpace"
      - "S3a_AISpaceRobotics"
      - "S3b_AISpacecraft"
      - "S4_AIinRobotics"
      - "S4a_D1_NavigationMapping"
      - "S4b_D2_Perception"
      - "S4c_D3_KnowledgeReasoning"
      - "S4d_D4_Planning"
      - "S4e_D5_Interaction"
      - "S4f_D6_Learning"
      - "S4g_Alignment"
      - "S5a_Multimodality"
      - "S5b_MachineBrain"
      - "S5c_IntegrationProtocols"
      - "S6_FutureDirections"
      - "_CrossCutting"
      - "_MaybeReview"
    tag_schema:
      section: ["S1", "S2", "S3", "S3a", "S3b",
                "S4a", "S4b", "S4c", "S4d", "S4e", "S4f", "S4g",
                "S5a", "S5b", "S5c", "S6"]
      kunze_dimension: ["D1:nav_mapping", "D2:perception", "D3:kr_reasoning",
                        "D4:planning", "D5:interaction", "D6:learning"]
      technique_cluster: []           # populated from cluster list above
      cluster_confidence: ["confidence:high", "confidence:medium", "confidence:low"]
      source_type: ["primary_research", "secondary_source", "technical_report",
                    "mission_document", "roadmap"]
      inclusion: ["status:included", "status:maybe", "status:excluded"]
      venue_tier: ["venue:tier1", "venue:tier2", "venue:tier3"]
      source_db: ["source:semantic_scholar", "source:arxiv", "source:ieee",
                  "source:wos", "source:scopus", "source:acm", "source:nasa_ntrs"]
      flags: ["cross_cutting", "seed_paper", "historical", "space_heritage",
              "deployment_constraints_discussed", "compute_requirements_noted",
              "radiation_robustness_discussed", "operational_description_present",
              "alignment_paper", "compositional_alignment",
              "general_alignment_not_robotics_specific"]
    add_abstract_note: true

  excel:
    enabled: true
    path: "./outputs/sourcing_results.xlsx"
    sheets:
      main_sheet:
        name: "All Papers"
        columns:
          - "title"
          - "authors"
          - "year"
          - "venue"
          - "doi"
          - "arxiv_id"
          - "primary_section"
          - "secondary_sections"
          - "kunze_dimension"               # D1 through D6
          - "technique_cluster"             # from predefined list
          - "cluster_assignment_confidence" # high / medium / low
          - "source_type"
          - "section_fit_score"
          - "contribution_score"
          - "recency_score"
          - "weighted_score"
          - "inclusion_decision"
          - "venue_tier"
          - "citation_count"
          - "open_access_pdf_url"
          - "source_database"
          - "is_cross_cutting"
          - "is_historical"
          - "space_heritage"
          - "deployment_constraints_discussed"
          - "compute_requirements_noted"
          - "radiation_robustness_discussed"
          - "operational_description_present"
          - "alignment_paper"                    # bool: primary topic is AI alignment
          - "compositional_alignment"            # bool: addresses module-level composition
          - "general_alignment_robotics_context" # bool: general alignment with robotic framing
          - "mission_or_system_name"        # S2 papers only
          - "agent_notes"
          - "abstract_snippet"

      section_summary_sheet:
        name: "Section Coverage"
        description: >
          One row per section. Columns: section name, Kunze dimension,
          target count, included count, maybe count, coverage status.

      analytical_data_sheet:
        name: "Analytical Data"
        description: >
          Raw structured data for the writing agent's analytical outputs.
          This sheet contains the sourced data — the writing agent applies
          the ACS and SDRR frameworks to produce the final tables/figures.

          Tab 1 — S2 Mission Taxonomy:
            Columns: mission_name, year_deployed, D1_nav, D2_perc, D3_kr,
            D4_plan, D5_interact, D6_learn, reference_paper.
            Cells: brief operational description of capability present/absent.
            NOTE: ACS level assignment is a writing-stage task, not sourcing.

          Tab 2 — S2 Deployment Lag:
            Columns: ai_capability, terrestrial_first_pub_year,
            space_deployment_year, deployment_lag_years, evidence_paper.
            Populated from sourced papers where space_heritage=true.

          Tab 3 — S4 Technique Clusters:
            Columns: kunze_dimension, technique_cluster, paper_count,
            space_heritage_count, deployment_constraints_count,
            compute_noted_count, radiation_noted_count.
            One row per cluster. Summarises the boolean flags for writing agent.

          Tab 4 — Bibliometric Trend:
            Columns: year (2015–2025), then one column per Kunze dimension.
            Cells: count of included S4 papers in that dimension for that year.
            Writing agent selects visualisation form from this raw data.

      prisma_sheet:
        name: "PRISMA Flow"
        description: >
          Counts at each PRISMA stage per database and overall.
          Required for Methods section of the paper.

  progress_file: "./outputs/sourcing-progress.txt"
  log_file: "./outputs/sourcing-log.txt"
  query_log: "./outputs/query-strings.txt"


## Edge Case Handling
# ─────────────────────────────────────────────────────────────────────────────

EDGE_CASES:
  section_undercoverage:
    check_after_scoring: true
    threshold: 0.5
    action: "run_supplementary_query"

  cluster_underpopulation:
    check_after_scoring: true
    minimum_papers_per_cluster: 3
    action: "flag_for_researcher_review"
    note: >
      Clusters with fewer than 3 included papers are flagged. The researcher
      decides whether to merge the cluster, run a supplementary query, or
      note the gap in the paper's limitations.

  no_abstract_available:
    action: "score_on_title_only"
    cap_score_at: 6.0
    exception: "NASA/ESA technical reports — score normally without abstract"

  medium_low_confidence_clusters:
    action: "flag_for_researcher_review"
    note: >
      All papers assigned with medium or low cluster confidence are listed
      in the Section Coverage sheet for researcher review before writing stage.

  paywall_login_failure:
    action: "skip_and_log"
    notify: true

  rate_limit_hit:
    action: "backoff_and_retry"
    backoff_seconds: 30
    max_retries: 3

  session_interrupted:
    action: "resume_from_progress_file"

  historical_paper_date_penalty:
    apply: false
    note: "S2 papers must not be penalised for age. See inclusion_criteria."
