"""Tests for proposal pipeline Pydantic models."""

import pytest
from pydantic import ValidationError

from proposal_pipeline.models import (
    ComplianceMatrix,
    ComplianceRow,
    DateItem,
    PipelineContext,
    ProposalOutline,
    ProposalPackage,
    ProposalSection,
    QualityGateResult,
    Requirement,
    RFPAnalysis,
    SectionOutline,
    SectionScore,
    TaskItem,
)


class TestTaskItem:
    def test_valid(self):
        t = TaskItem(title="Build API", description="Develop REST API", page=5)
        assert t.title == "Build API"
        assert t.page == 5

    def test_default_page(self):
        t = TaskItem(title="Test", description="Run tests")
        assert t.page == 0

    def test_missing_required_fields(self):
        with pytest.raises(ValidationError):
            TaskItem(title="No description")


class TestRequirement:
    def test_valid(self):
        r = Requirement(category="Security", description="Must use TLS 1.3", page=10)
        assert r.category == "Security"

    def test_missing_category(self):
        with pytest.raises(ValidationError):
            Requirement(description="Missing category")


class TestRFPAnalysis:
    def test_valid_full(self):
        rfp = RFPAnalysis(
            customer="DHS",
            scope="Modernize legacy systems",
            tasks=[TaskItem(title="Migrate DB", description="Move to cloud")],
            requirements=[Requirement(category="Security", description="FedRAMP")],
            dates=[DateItem(event="Submission", date="2025-01-15")],
        )
        assert rfp.customer == "DHS"
        assert len(rfp.tasks) == 1
        assert len(rfp.requirements) == 1
        assert len(rfp.dates) == 1

    def test_empty_lists_default(self):
        rfp = RFPAnalysis(customer="DOD", scope="Build portal")
        assert rfp.tasks == []
        assert rfp.requirements == []
        assert rfp.dates == []


class TestSectionOutline:
    def test_valid(self):
        s = SectionOutline(
            number="2.1",
            title="Technical Approach",
            guidance="Describe methodology",
            mapped_requirements=["Must use TLS", "FedRAMP required"],
            target_word_count=1000,
        )
        assert s.number == "2.1"
        assert len(s.mapped_requirements) == 2
        assert s.target_word_count == 1000

    def test_defaults(self):
        s = SectionOutline(number="1", title="Summary", guidance="Overview")
        assert s.mapped_requirements == []
        assert s.target_word_count == 500


class TestProposalOutline:
    def test_valid(self):
        outline = ProposalOutline(
            sections=[
                SectionOutline(number="1", title="Exec Summary", guidance="Overview"),
                SectionOutline(number="2", title="Tech Approach", guidance="Details"),
            ]
        )
        assert len(outline.sections) == 2


class TestComplianceMatrix:
    def test_valid(self):
        cm = ComplianceMatrix(
            rows=[
                ComplianceRow(
                    requirement_id="REQ-001",
                    requirement_description="Use TLS",
                    category="Security",
                    proposal_section="3.1",
                    compliance_status="Full",
                )
            ],
            gap_count=0,
            coverage_percentage=100.0,
        )
        assert len(cm.rows) == 1
        assert cm.coverage_percentage == 100.0

    def test_empty_default(self):
        cm = ComplianceMatrix()
        assert cm.rows == []
        assert cm.gap_count == 0


class TestProposalSection:
    def test_valid(self):
        s = ProposalSection(
            number="1",
            title="Executive Summary",
            content="We propose to deliver...",
            word_count=5,
        )
        assert s.word_count == 5


class TestSectionScore:
    def test_valid(self):
        s = SectionScore(
            section_number="1",
            section_title="Summary",
            score=85,
            strengths=["Clear"],
            weaknesses=["Short"],
            recommendations=["Add detail"],
            requires_rewrite=False,
        )
        assert s.score == 85
        assert not s.requires_rewrite

    def test_defaults(self):
        s = SectionScore(section_number="1", section_title="Test", score=50)
        assert s.strengths == []
        assert s.requires_rewrite is False


class TestPipelineContext:
    def test_defaults(self):
        ctx = PipelineContext()
        assert ctx.win_themes == []
        assert ctx.reference_proposals == []
        assert ctx.company_style_guide == ""

    def test_with_data(self):
        ctx = PipelineContext(
            win_themes=["Cost savings", "Innovation"],
            company_style_guide="Use active voice",
        )
        assert len(ctx.win_themes) == 2


class TestProposalPackage:
    def test_minimal(self):
        pkg = ProposalPackage(
            rfp_analysis=RFPAnalysis(customer="Test", scope="Test scope"),
            outline=ProposalOutline(sections=[]),
            compliance_matrix=ComplianceMatrix(),
        )
        assert pkg.overall_score == 0.0
        assert pkg.sections == []

    def test_serialization_roundtrip(self):
        pkg = ProposalPackage(
            rfp_analysis=RFPAnalysis(customer="DHS", scope="Modernize"),
            outline=ProposalOutline(
                sections=[
                    SectionOutline(number="1", title="Summary", guidance="Overview")
                ]
            ),
            compliance_matrix=ComplianceMatrix(coverage_percentage=95.0),
            sections=[
                ProposalSection(
                    number="1",
                    title="Summary",
                    content="We propose...",
                    word_count=3,
                )
            ],
            overall_score=88.5,
        )
        json_str = pkg.model_dump_json()
        restored = ProposalPackage.model_validate_json(json_str)
        assert restored.overall_score == 88.5
        assert restored.rfp_analysis.customer == "DHS"
        assert len(restored.sections) == 1
