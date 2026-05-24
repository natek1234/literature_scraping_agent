from __future__ import annotations

import datetime

from pydantic import BaseModel, model_validator


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
    volume: str | None = None
    issue: str | None = None
    pages: str | None = None
    publication_type: str | None = None

    # Sourcing
    source_database: str
    retrieved_at: str  # ISO 8601
    open_access_pdf_url: str | None = None
    citation_count: int | None = None
    citations_per_year: float | None = None

    # Section assignment (populated by scorer)
    primary_section: str | None = None
    secondary_sections: list[str] = []
    kunze_dimension: str | None = None  # "D1"-"D6" | "alignment" | None
    technique_cluster: str | None = None
    cluster_assignment_confidence: str | None = None  # high|medium|low
    source_type: str | None = None  # primary_research|secondary_source|
    # technical_report|mission_document|roadmap

    # Scoring (populated by scorer)
    section_fit_score: float | None = None
    contribution_score: float | None = None
    recency_score: float | None = None
    weighted_score: float | None = None
    inclusion_decision: str | None = None  # include|maybe|exclude
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
    abstract_snippet: str | None = None  # first 300 chars of abstract

    @model_validator(mode="after")
    def compute_derived_fields(self) -> PaperRecord:
        if self.citation_count is not None and self.year is not None:
            age = max(datetime.date.today().year - self.year + 0.5, 0.5)
            self.citations_per_year = round(self.citation_count / age, 1)
        if self.abstract and not self.abstract_snippet:
            self.abstract_snippet = self.abstract[:300]
        return self
