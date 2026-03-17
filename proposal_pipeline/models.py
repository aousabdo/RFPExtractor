"""Pydantic models for the proposal generation pipeline."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


# ── RFP Analysis Models ──


class TaskItem(BaseModel):
    title: str
    description: str
    page: int = 0


class Requirement(BaseModel):
    category: str  # Security, Compliance, IT Standards, Personnel
    description: str
    page: int = 0


class DateItem(BaseModel):
    event: str
    date: str
    page: int = 0


class RFPAnalysis(BaseModel):
    customer: str
    scope: str
    tasks: List[TaskItem] = Field(default_factory=list)
    requirements: List[Requirement] = Field(default_factory=list)
    dates: List[DateItem] = Field(default_factory=list)


# ── Proposal Outline Models ──


class SectionOutline(BaseModel):
    number: str  # e.g. "3.1"
    title: str  # e.g. "Technical Approach"
    guidance: str  # What this section should contain
    mapped_requirements: List[str] = Field(default_factory=list)
    target_word_count: int = 500
    max_word_count: int = 0  # 0 means no max enforced


class ProposalOutline(BaseModel):
    sections: List[SectionOutline]


# ── Compliance Matrix Models ──


class ComplianceRow(BaseModel):
    requirement_id: str  # e.g. "REQ-SEC-001"
    requirement_description: str
    category: str
    source_page: int = 0
    proposal_section: str  # Which section addresses this
    compliance_status: str  # Full, Partial, Gap
    notes: str = ""


class ComplianceMatrix(BaseModel):
    rows: List[ComplianceRow] = Field(default_factory=list)
    gap_count: int = 0
    coverage_percentage: float = 0.0


# ── Section Writing Models ──


class ProposalSection(BaseModel):
    number: str
    title: str
    content: str  # Full markdown text
    word_count: int = 0
    requirements_addressed: List[str] = Field(default_factory=list)


class QualityGateResult(BaseModel):
    passed: bool
    word_count_ok: bool
    no_placeholders: bool
    requirements_covered: bool
    feedback: str = ""


# ── Scoring Models ──


class SectionScore(BaseModel):
    section_number: str
    section_title: str
    score: int  # 0-100
    strengths: List[str] = Field(default_factory=list)
    weaknesses: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    requires_rewrite: bool = False


# ── Pipeline Context (for future extensibility) ──


class PastPerformanceEntry(BaseModel):
    """A single past performance / relevant experience entry."""
    contract_name: str
    customer: str
    contract_number: str = ""
    period_of_performance: str = ""
    contract_value: str = ""
    description: str  # What you did
    relevance: str = ""  # How it relates to this RFP
    key_outcomes: List[str] = Field(default_factory=list)
    cpars_rating: str = ""  # e.g. "Exceptional", "Very Good"
    reference_name: str = ""
    reference_contact: str = ""


class CompanyProfile(BaseModel):
    """Company identity and differentiators for weaving into the proposal."""
    company_name: str = ""
    tagline: str = ""
    founded: str = ""
    headquarters: str = ""
    cage_code: str = ""
    duns: str = ""
    uei: str = ""
    naics_codes: List[str] = Field(default_factory=list)
    certifications: List[str] = Field(default_factory=list)  # e.g. ISO 9001, CMMI
    clearance_level: str = ""  # e.g. "Top Secret Facility Clearance"
    employee_count: str = ""
    differentiators: List[str] = Field(default_factory=list)
    core_competencies: List[str] = Field(default_factory=list)


class PipelineContext(BaseModel):
    """Optional context for enriching proposals. Fields added as features mature."""

    win_themes: List[str] = Field(default_factory=list)
    reference_proposals: List[str] = Field(default_factory=list)
    company_style_guide: str = ""
    company_profile: Optional[CompanyProfile] = None
    past_performance: List[PastPerformanceEntry] = Field(default_factory=list)


# ── Full Proposal Package ──


class ProposalPackage(BaseModel):
    rfp_analysis: RFPAnalysis
    outline: ProposalOutline
    compliance_matrix: ComplianceMatrix
    sections: List[ProposalSection] = Field(default_factory=list)
    scores: List[SectionScore] = Field(default_factory=list)
    overall_score: float = 0.0
    generation_metadata: dict = Field(default_factory=dict)
