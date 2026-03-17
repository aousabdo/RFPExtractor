"""Quality gate checks for proposal sections."""

from __future__ import annotations

import re
from typing import List, Tuple

from .models import ProposalSection, QualityGateResult, SectionOutline

PLACEHOLDER_PATTERNS = [
    r"\[.*?(?:insert|TBD|placeholder|TODO|fill in|to be determined).*?\]",
    r"\{.*?(?:insert|TBD|placeholder|TODO|fill in).*?\}",
    r"<.*?(?:insert|TBD|placeholder|TODO|fill in).*?>",
    r"Lorem ipsum",
    r"\[Company Name\]",
    r"\[Your Company\]",
    r"\[Client Name\]",
    r"\[Date\]",
    r"XX+",
]

# Past performance template markers are OK — don't flag them
PAST_PERF_PATTERN = r"\[COMPANY:.*?\]"


def check_word_count(
    section: ProposalSection, outline: SectionOutline, min_ratio: float = 0.6
) -> Tuple[bool, str]:
    """Check that section meets minimum word count and doesn't exceed max.

    Returns (passed, feedback_message).
    """
    actual = len(section.content.split())
    minimum = int(outline.target_word_count * min_ratio)

    if actual < minimum:
        return False, (
            f"Word count too low: {actual} words vs target {outline.target_word_count} "
            f"(minimum {minimum}). Expand with more specific detail."
        )

    if outline.max_word_count > 0 and actual > outline.max_word_count:
        return False, (
            f"Word count too high: {actual} words vs maximum {outline.max_word_count}. "
            f"Tighten the content: remove redundancy, consolidate bullet points, "
            f"and cross-reference other sections instead of restating content."
        )

    return True, ""


def check_no_placeholders(section: ProposalSection) -> List[str]:
    """Return list of placeholder strings found in the section content.

    Excludes [COMPANY: ...] markers which are intentional templates
    for Past Performance sections.
    """
    found = []
    for pattern in PLACEHOLDER_PATTERNS:
        matches = re.findall(pattern, section.content, re.IGNORECASE)
        found.extend(matches)

    # Filter out [COMPANY: ...] markers (these are intentional)
    found = [m for m in found if not re.match(PAST_PERF_PATTERN, m, re.IGNORECASE)]

    return found


def check_requirements_coverage(
    section: ProposalSection,
    mapped_requirements: List[str],
    min_coverage: float = 0.7,
) -> Tuple[bool, float]:
    """Check what fraction of mapped requirements are addressed in the section.

    Uses keyword overlap: for each requirement, checks if significant terms
    from the requirement description appear in the section content.
    """
    if not mapped_requirements:
        return True, 1.0

    content_lower = section.content.lower()
    covered = 0

    for req in mapped_requirements:
        # Extract significant words (length > 4 to skip articles/prepositions)
        key_terms = [w for w in req.lower().split() if len(w) > 4]
        if not key_terms:
            covered += 1  # Short requirements are assumed covered
            continue
        match_ratio = sum(1 for t in key_terms if t in content_lower) / len(key_terms)
        if match_ratio > 0.3:
            covered += 1

    coverage = covered / len(mapped_requirements)
    return coverage >= min_coverage, coverage


def run_quality_gate(
    section: ProposalSection, outline: SectionOutline
) -> QualityGateResult:
    """Run all quality checks on a section and return a combined result."""
    wc_ok, wc_feedback = check_word_count(section, outline)
    placeholders = check_no_placeholders(section)
    no_placeholders = len(placeholders) == 0
    req_ok, coverage = check_requirements_coverage(
        section, outline.mapped_requirements
    )

    feedback_parts = []
    if not wc_ok:
        feedback_parts.append(wc_feedback)
    if not no_placeholders:
        feedback_parts.append(
            f"Placeholder text found: {placeholders}. "
            f"Replace ALL placeholders with concrete, specific content."
        )
    if not req_ok:
        feedback_parts.append(
            f"Requirement coverage at {coverage:.0%}, needs >= 70%. "
            f"Explicitly address these requirements: {outline.mapped_requirements}"
        )

    return QualityGateResult(
        passed=wc_ok and no_placeholders and req_ok,
        word_count_ok=wc_ok,
        no_placeholders=no_placeholders,
        requirements_covered=req_ok,
        feedback="\n".join(feedback_parts),
    )
