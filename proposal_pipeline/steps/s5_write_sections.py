"""Step 5: Write proposal sections — one at a time with quality gates and retry."""

from __future__ import annotations

import logging
from typing import Callable, Dict, List, Optional

from openai import OpenAI

from ..models import (
    ComplianceMatrix,
    ComplianceRow,
    PipelineContext,
    ProposalOutline,
    ProposalSection,
    RFPAnalysis,
    SectionOutline,
)
from ..openai_helpers import chat_completion
from ..quality_gates import run_quality_gate

logger = logging.getLogger(__name__)

SECTION_SYSTEM_PROMPT = """\
You are an expert proposal writer for a government/enterprise IT services company. \
You write compelling, detailed, submission-ready proposal sections.

Write a COMPLETE, DETAILED proposal section based on the provided brief. Your output must be:

1. **Substantive**: Include specific methodologies, tools, processes, timelines, and deliverables. \
   Never use vague language like "we will leverage best practices" without explaining what those are.
2. **Compliant**: Explicitly address every mapped RFP requirement. Reference the requirement \
   and explain HOW you will meet it.
3. **Persuasive**: Highlight differentiators, relevant experience, and value propositions. \
   Use active voice and confident language.
4. **Professional**: Government proposal tone — formal but readable. \
   Use clear headings, bullet points for lists, and structured paragraphs.
5. **Complete**: Meet or exceed the target word count. Every paragraph should add value. \
   No placeholder text, no "[INSERT]" markers, no TODO items.

Output ONLY the section content in markdown format. Do not include the section number or title \
as a heading — those are added by the system.\
"""

REWRITE_SYSTEM_PROMPT = """\
You are an expert proposal writer. The previous draft of this section did not pass quality checks. \
Rewrite the section to address the specific feedback below.

You must:
- Fix ALL issues identified in the feedback
- Maintain or increase the level of detail
- Keep all content that was already good
- Meet the target word count
- Use no placeholder text whatsoever

Output ONLY the revised section content in markdown format.\
"""


def write_all_sections(
    client: OpenAI,
    rfp: RFPAnalysis,
    outline: ProposalOutline,
    compliance: ComplianceMatrix,
    tech_research: Dict[str, str],
    model: str = "gpt-5",
    context: PipelineContext | None = None,
    progress_callback: Optional[Callable[[str, float], None]] = None,
) -> List[ProposalSection]:
    """Write all proposal sections one by one with quality gates.

    Each section gets its own API call with full context from prior steps
    and summaries of previously written sections for consistency.

    Args:
        client: OpenAI client.
        rfp: RFP analysis.
        outline: Proposal outline with section briefs.
        compliance: Compliance matrix.
        tech_research: Technology research by area.
        model: Model ID.
        context: Optional pipeline context (win themes, style guide, etc.).
        progress_callback: Optional callback for progress reporting.

    Returns:
        List of written ProposalSection objects.
    """
    written_sections: List[ProposalSection] = []
    total = len(outline.sections)

    for i, section_outline in enumerate(outline.sections):
        if progress_callback:
            pct = (i / total) * 0.55 + 0.30  # Map to 30%-85% of total progress
            progress_callback(
                f"Writing section {section_outline.number}: {section_outline.title} "
                f"({i + 1}/{total})",
                pct,
            )

        logger.info(
            "Writing section %s: %s (target: %d words)",
            section_outline.number,
            section_outline.title,
            section_outline.target_word_count,
        )

        section = _write_single_section(
            client=client,
            rfp=rfp,
            section_outline=section_outline,
            compliance=compliance,
            tech_research=tech_research,
            prior_sections=written_sections,
            model=model,
            context=context,
        )

        # Quality gate with retry (max 2 retries)
        for retry in range(3):
            gate = run_quality_gate(section, section_outline)
            if gate.passed:
                logger.info(
                    "Section %s passed quality gate (%d words)",
                    section_outline.number,
                    section.word_count,
                )
                break
            if retry < 2:
                logger.warning(
                    "Section %s failed quality gate (attempt %d): %s",
                    section_outline.number,
                    retry + 1,
                    gate.feedback,
                )
                section = _rewrite_section(
                    client=client,
                    section=section,
                    feedback=gate.feedback,
                    section_outline=section_outline,
                    model=model,
                )
            else:
                logger.warning(
                    "Section %s still failing after retries, proceeding anyway",
                    section_outline.number,
                )

        written_sections.append(section)

    return written_sections


def _write_single_section(
    client: OpenAI,
    rfp: RFPAnalysis,
    section_outline: SectionOutline,
    compliance: ComplianceMatrix,
    tech_research: Dict[str, str],
    prior_sections: List[ProposalSection],
    model: str,
    context: PipelineContext | None = None,
) -> ProposalSection:
    """Write a single proposal section with full context."""

    # Gather relevant compliance rows for this section
    relevant_compliance = _get_relevant_compliance(compliance, section_outline)

    # Gather relevant tech research
    relevant_tech = _get_relevant_tech(tech_research, section_outline)

    # Build prior sections summary for consistency
    prior_summary = _build_prior_summary(prior_sections)

    # Build the section brief
    user_prompt = _build_section_brief(
        rfp=rfp,
        section_outline=section_outline,
        relevant_compliance=relevant_compliance,
        relevant_tech=relevant_tech,
        prior_summary=prior_summary,
        context=context,
    )

    content = chat_completion(
        client=client,
        system_prompt=SECTION_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        model=model,
        max_tokens=8192,
        temperature=0.4,
    )

    word_count = len(content.split())

    return ProposalSection(
        number=section_outline.number,
        title=section_outline.title,
        content=content,
        word_count=word_count,
        requirements_addressed=[
            r.requirement_description for r in relevant_compliance
        ],
    )


def _rewrite_section(
    client: OpenAI,
    section: ProposalSection,
    feedback: str,
    section_outline: SectionOutline,
    model: str,
) -> ProposalSection:
    """Rewrite a section that failed quality gates."""
    user_prompt = f"""## Section to Rewrite
**{section_outline.number}. {section_outline.title}**
Target word count: {section_outline.target_word_count}

## Current Draft
{section.content}

## Quality Gate Feedback (MUST FIX)
{feedback}

## Section Guidance
{section_outline.guidance}

Rewrite the section to fix ALL issues above. Maintain all good content \
and expand where needed."""

    content = chat_completion(
        client=client,
        system_prompt=REWRITE_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        model=model,
        max_tokens=8192,
        temperature=0.3,
    )

    return ProposalSection(
        number=section.number,
        title=section.title,
        content=content,
        word_count=len(content.split()),
        requirements_addressed=section.requirements_addressed,
    )


def _get_relevant_compliance(
    compliance: ComplianceMatrix, section_outline: SectionOutline
) -> List[ComplianceRow]:
    """Get compliance rows mapped to this section."""
    return [
        row
        for row in compliance.rows
        if row.proposal_section == section_outline.number
        or section_outline.number in row.proposal_section
    ]


def _get_relevant_tech(
    tech_research: Dict[str, str], section_outline: SectionOutline
) -> str:
    """Get tech research relevant to this section based on keyword matching."""
    title_lower = section_outline.title.lower()
    guidance_lower = section_outline.guidance.lower()
    combined = title_lower + " " + guidance_lower

    relevant_parts = []
    for area, findings in tech_research.items():
        area_lower = area.lower()
        # Check if the tech area is relevant to this section
        area_words = [w for w in area_lower.split() if len(w) > 3]
        if any(w in combined for w in area_words):
            relevant_parts.append(f"### {area}\n{findings}")

    return "\n\n".join(relevant_parts) if relevant_parts else ""


def _build_prior_summary(prior_sections: List[ProposalSection]) -> str:
    """Build a summary of previously written sections for context consistency."""
    if not prior_sections:
        return ""

    # Include summaries of the last 3 sections
    recent = prior_sections[-3:]
    summaries = []
    for s in recent:
        # Take first 200 words as summary
        words = s.content.split()[:200]
        summary = " ".join(words)
        if len(s.content.split()) > 200:
            summary += "..."
        summaries.append(f"**Section {s.number} — {s.title}:** {summary}")

    return "\n\n".join(summaries)


def _build_section_brief(
    rfp: RFPAnalysis,
    section_outline: SectionOutline,
    relevant_compliance: List[ComplianceRow],
    relevant_tech: str,
    prior_summary: str,
    context: PipelineContext | None = None,
) -> str:
    """Build the full context prompt for writing a single section."""

    parts = [
        f"## Section Brief: {section_outline.number}. {section_outline.title}",
        f"**Target Word Count:** {section_outline.target_word_count} words (minimum)",
        f"\n## Guidance\n{section_outline.guidance}",
        f"\n## RFP Context\n**Customer:** {rfp.customer}\n**Scope:** {rfp.scope}",
    ]

    # Add mapped requirements
    if section_outline.mapped_requirements:
        reqs = "\n".join(f"- {r}" for r in section_outline.mapped_requirements)
        parts.append(f"\n## Requirements This Section MUST Address\n{reqs}")

    # Add compliance rows
    if relevant_compliance:
        compliance_text = "\n".join(
            f"- [{r.requirement_id}] {r.requirement_description} "
            f"(Status: {r.compliance_status})"
            for r in relevant_compliance
        )
        parts.append(f"\n## Compliance Requirements\n{compliance_text}")

    # Add relevant technology research
    if relevant_tech:
        parts.append(f"\n## Technology Research (incorporate where relevant)\n{relevant_tech}")

    # Add prior sections for consistency
    if prior_summary:
        parts.append(
            f"\n## Previously Written Sections (maintain consistency)\n{prior_summary}"
        )

    # Add win themes if available
    if context and context.win_themes:
        themes = "\n".join(f"- {t}" for t in context.win_themes)
        parts.append(f"\n## Win Themes (weave throughout)\n{themes}")

    # Add company style guide if available
    if context and context.company_style_guide:
        parts.append(
            f"\n## Writing Style Guide\n{context.company_style_guide}"
        )

    return "\n".join(parts)
