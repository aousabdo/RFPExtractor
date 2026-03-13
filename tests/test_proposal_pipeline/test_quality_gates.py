"""Tests for proposal pipeline quality gates."""

import pytest

from proposal_pipeline.models import ProposalSection, SectionOutline
from proposal_pipeline.quality_gates import (
    check_no_placeholders,
    check_requirements_coverage,
    check_word_count,
    run_quality_gate,
)


def _make_section(content: str, number: str = "1", title: str = "Test") -> ProposalSection:
    return ProposalSection(
        number=number,
        title=title,
        content=content,
        word_count=len(content.split()),
    )


def _make_outline(
    target_word_count: int = 500,
    mapped_requirements: list | None = None,
) -> SectionOutline:
    return SectionOutline(
        number="1",
        title="Test Section",
        guidance="Test guidance",
        mapped_requirements=mapped_requirements or [],
        target_word_count=target_word_count,
    )


class TestCheckWordCount:
    def test_meets_target(self):
        section = _make_section("word " * 500)
        outline = _make_outline(target_word_count=500)
        assert check_word_count(section, outline) is True

    def test_meets_minimum_ratio(self):
        # 300 words vs 500 target, ratio = 0.6 → exactly at threshold
        section = _make_section("word " * 300)
        outline = _make_outline(target_word_count=500)
        assert check_word_count(section, outline, min_ratio=0.6) is True

    def test_below_minimum(self):
        section = _make_section("word " * 100)
        outline = _make_outline(target_word_count=500)
        assert check_word_count(section, outline) is False

    def test_exceeds_target(self):
        section = _make_section("word " * 1000)
        outline = _make_outline(target_word_count=500)
        assert check_word_count(section, outline) is True


class TestCheckNoPlaceholders:
    def test_clean_content(self):
        section = _make_section(
            "We will implement a secure, scalable architecture using AWS GovCloud."
        )
        assert check_no_placeholders(section) == []

    def test_insert_placeholder(self):
        section = _make_section("Our team will [INSERT company name here] deliver...")
        found = check_no_placeholders(section)
        assert len(found) > 0

    def test_tbd_placeholder(self):
        section = _make_section("Timeline is [TBD] pending approval.")
        found = check_no_placeholders(section)
        assert len(found) > 0

    def test_todo_placeholder(self):
        section = _make_section("Security approach: [TODO: fill in details]")
        found = check_no_placeholders(section)
        assert len(found) > 0

    def test_lorem_ipsum(self):
        section = _make_section("Lorem ipsum dolor sit amet, consectetur adipiscing elit.")
        found = check_no_placeholders(section)
        assert len(found) > 0

    def test_company_name_placeholder(self):
        section = _make_section("[Company Name] will deliver the solution.")
        found = check_no_placeholders(section)
        assert len(found) > 0

    def test_xx_placeholder(self):
        section = _make_section("We will deliver within XX days.")
        found = check_no_placeholders(section)
        assert len(found) > 0

    def test_curly_brace_placeholder(self):
        section = _make_section("The {fill in technology} stack includes...")
        found = check_no_placeholders(section)
        assert len(found) > 0


class TestCheckRequirementsCoverage:
    def test_full_coverage(self):
        section = _make_section(
            "We will implement FedRAMP authorization using continuous monitoring. "
            "Our security controls include encryption at rest and in transit."
        )
        reqs = ["FedRAMP authorization required", "encryption at rest"]
        ok, coverage = check_requirements_coverage(section, reqs)
        assert ok is True
        assert coverage >= 0.7

    def test_no_requirements(self):
        section = _make_section("Some content here.")
        ok, coverage = check_requirements_coverage(section, [])
        assert ok is True
        assert coverage == 1.0

    def test_partial_coverage(self):
        section = _make_section("We will implement FedRAMP controls.")
        reqs = [
            "FedRAMP authorization required",
            "Must support biometric authentication",
            "Quantum-resistant cryptography needed",
        ]
        ok, coverage = check_requirements_coverage(section, reqs, min_coverage=0.7)
        # Only 1 of 3 requirements covered
        assert coverage < 0.7

    def test_short_requirements_assumed_covered(self):
        section = _make_section("Some content")
        reqs = ["TLS"]  # All words <= 4 chars → assumed covered
        ok, coverage = check_requirements_coverage(section, reqs)
        assert ok is True


class TestRunQualityGate:
    def test_passes_all(self):
        content = (
            "We will implement FedRAMP authorization using continuous monitoring "
            "and automated security scanning. Our encryption strategy covers both "
            "data at rest and data in transit using AES-256 and TLS 1.3. "
        ) * 20  # ~300 words

        section = _make_section(content)
        outline = _make_outline(
            target_word_count=400,
            mapped_requirements=["FedRAMP authorization", "encryption strategy"],
        )
        result = run_quality_gate(section, outline)
        assert result.passed is True
        assert result.word_count_ok is True
        assert result.no_placeholders is True
        assert result.requirements_covered is True
        assert result.feedback == ""

    def test_fails_word_count(self):
        section = _make_section("Short content.")
        outline = _make_outline(target_word_count=500)
        result = run_quality_gate(section, outline)
        assert result.passed is False
        assert result.word_count_ok is False
        assert "Word count too low" in result.feedback

    def test_fails_placeholder(self):
        section = _make_section("word " * 500 + " [INSERT details here]")
        outline = _make_outline(target_word_count=500)
        result = run_quality_gate(section, outline)
        assert result.passed is False
        assert result.no_placeholders is False
        assert "Placeholder text found" in result.feedback

    def test_multiple_failures(self):
        section = _make_section("Short [TBD].")
        outline = _make_outline(
            target_word_count=500,
            mapped_requirements=["Complex requirement description here"],
        )
        result = run_quality_gate(section, outline)
        assert result.passed is False
        assert result.word_count_ok is False
        assert result.no_placeholders is False
