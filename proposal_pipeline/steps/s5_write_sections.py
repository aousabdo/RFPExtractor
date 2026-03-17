"""Step 5: Write proposal sections — one at a time with quality gates and retry.

Key improvements:
- Commitment tracker prevents redundancy across sections
- Executive Summary is written LAST and synthesizes the full proposal
- Past Performance uses real data when provided, templates when not
"""

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


def _strip_leading_heading(content: str, section_number: str, section_title: str) -> str:
    """Strip duplicate section heading if the model included one at the top.

    The export layer adds headings, so we remove them from the model output
    to prevent duplication like:
        ## 2. Understanding of Requirements
        ## 2. Understanding of Requirements
    """
    lines = content.split("\n")
    # Check first few non-empty lines for a heading that matches
    for i, line in enumerate(lines[:5]):
        stripped = line.strip()
        if not stripped:
            continue
        # Match patterns like "## 2. Title", "Section 2: Title", "2. Title", "# Title"
        if stripped.startswith("#"):
            heading_text = stripped.lstrip("#").strip()
            # Check if it contains the section number or title
            if (section_number in heading_text
                    or section_title.lower() in heading_text.lower()
                    or heading_text.lower().startswith(section_title[:20].lower())):
                lines.pop(i)
                # Also remove a trailing blank line if present
                while i < len(lines) and not lines[i].strip():
                    lines.pop(i)
                return "\n".join(lines)
        elif (stripped.lower().startswith(f"section {section_number}")
              or stripped.lower().startswith(f"{section_number}.")
              or stripped.lower().startswith(f"{section_number}:")
              or stripped.lower().startswith(section_title[:20].lower())):
            lines.pop(i)
            while i < len(lines) and not lines[i].strip():
                lines.pop(i)
            return "\n".join(lines)
        else:
            break  # First non-empty, non-heading line — stop looking
    # Also strip bold section headers like "**Section 3: Title**"
    if lines:
        first_line = lines[0].strip()
        if first_line.startswith("**") and ("section" in first_line.lower()
                                             or section_number in first_line):
            lines.pop(0)
            while lines and not lines[0].strip():
                lines.pop(0)
    return "\n".join(lines)

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
5. **Complete**: Meet the target word count but do NOT exceed the maximum. \
   Every paragraph should add value. \
   No placeholder text, no "[INSERT]" markers, no TODO items.
6. **Non-redundant**: If a topic is covered in another section (listed under "Commitments Already Made"), \
   reference it briefly ("as detailed in Section X") rather than re-explaining it. \
   Add NEW information, not repetition.
7. **Credible**: Do NOT fabricate specific metrics, statistics, or numbers (e.g., "99.9999% uptime", \
   "86 runbooks", "120% backfill coverage") unless they appear in the Company Identity or Past Performance \
   data provided. Use general but confident language instead (e.g., "proven track record of high availability" \
   rather than inventing a precise uptime figure). Every bold claim must be defensible.

Output ONLY the section content in markdown format. Do NOT include the section number or title \
as a heading (e.g., do NOT start with "## 3.2 Data Management") — headings are added by the system. \
Do NOT start with a line like "Section X: Title" — that is also added by the system. \
Start directly with the substantive content.\
"""

EXEC_SUMMARY_SYSTEM_PROMPT = """\
You are an expert proposal writer creating the Executive Summary for a government proposal.

The Executive Summary must be a HIGH-LEVEL synthesis of the entire proposal. It should:
1. Open with a clear value proposition (1-2 sentences)
2. Summarize the overall approach in 2-3 paragraphs (NOT detailed technical content)
3. Highlight 3-5 key differentiators
4. State high-level compliance commitment
5. Close with a confident, forward-looking statement

CRITICAL RULES:
- Do NOT include detailed SLA numbers, tool lists, architecture diagrams, or technical deep dives
- Do NOT repeat content verbatim from other sections — summarize and reference
- Keep it to {max_words} words maximum — evaluators skim this section
- Think of it as the "elevator pitch" — compelling and concise
- Reference specific section numbers where details can be found
- Do NOT fabricate specific metrics or statistics. Only cite numbers that appear in the \
  Company Identity or section summaries provided. Use confident but general language \
  for claims that cannot be immediately verified.

Output ONLY the section content in markdown format.\
"""

PAST_PERFORMANCE_TEMPLATE_PROMPT = """\
You are an expert proposal writer. The company has not yet provided their actual past performance \
data. Generate a TEMPLATE section with clear markers showing where real data must be inserted.

Use this exact format for each entry:
---
**[COMPANY: Contract Name #1]**
- Customer: [COMPANY: Customer agency name]
- Contract Number: [COMPANY: Contract number]
- Period of Performance: [COMPANY: Start - End dates]
- Contract Value: [COMPANY: Dollar value]
- Description: [COMPANY: 2-3 sentences describing the work performed]
- Relevance to This RFP: [COMPANY: How this experience relates to the current SOW]
- Key Outcomes: [COMPANY: 3-4 measurable outcomes]
- CPARS Rating: [COMPANY: Rating if available]
- Reference: [COMPANY: Name, title, phone, email]
---

Generate 3-4 template entries with guidance comments explaining what type of experience \
would be most relevant based on the RFP requirements.

Start with a brief introduction explaining evaluation criteria, then the templates, \
then a closing paragraph about how past performance demonstrates capability.

Mark ALL company-specific content with [COMPANY: description of what to fill in].\
"""

PAST_PERFORMANCE_REAL_PROMPT = """\
You are an expert proposal writer. Using the REAL past performance data provided below, \
write a compelling Past Performance section that demonstrates the company's ability to \
perform this contract.

For each entry:
1. Lead with the most relevant aspects to THIS RFP
2. Highlight outcomes that map to RFP requirements
3. Show progression and lessons learned
4. Include all reference information

Write a brief introduction, then each past performance entry, then a summary paragraph \
linking the collective experience to this RFP's requirements.

Output ONLY the section content in markdown format. Use the real data exactly as provided — \
do NOT fabricate or embellish details.\
"""

REWRITE_SYSTEM_PROMPT = """\
You are an expert proposal writer. The previous draft of this section did not pass quality checks. \
Rewrite the section to address the specific feedback below.

You must:
- Fix ALL issues identified in the feedback
- If the feedback says word count is too HIGH: aggressively cut filler, merge overlapping bullets, \
  replace verbose explanations with concise statements, and remove content that belongs in other sections. \
  The MAXIMUM word count is a HARD ceiling — exceeding it is a failure.
- If the feedback says word count is too LOW: expand with more specific detail
- Keep all content that was already good
- Use no placeholder text whatsoever

Output ONLY the revised section content in markdown format. Do NOT include a section heading.\
"""


class CommitmentTracker:
    """Tracks key commitments made across sections to prevent redundancy.

    Records SLAs, tools, timelines, and approaches so subsequent sections
    can reference prior commitments instead of restating them.
    """

    def __init__(self):
        self._commitments: Dict[str, List[str]] = {}  # section_number -> list of commitments

    def record(self, section_number: str, section_title: str, content: str) -> None:
        """Extract and record key commitments from a written section."""
        # Extract key commitments (SLAs, tools, timelines, deliverables)
        commitments = []
        for line in content.split("\n"):
            line = line.strip()
            # Capture lines with specific metrics, SLAs, tool names, or timelines
            if any(marker in line.lower() for marker in [
                "≥", "≤", "99.", "sla", "within",
                "%", "days", "hours", "minutes",
                "we will", "we commit", "our approach",
            ]) and len(line) > 20 and len(line) < 300:
                commitments.append(line)

        if commitments:
            self._commitments[f"{section_number}. {section_title}"] = commitments[:10]

    def get_summary(self) -> str:
        """Return a compact summary of all commitments made so far."""
        if not self._commitments:
            return ""

        parts = ["## Commitments Already Made (reference these, do NOT restate)"]
        for section, items in self._commitments.items():
            parts.append(f"\n**{section}:**")
            for item in items[:5]:  # Top 5 per section to control token count
                parts.append(f"  - {item}")

        return "\n".join(parts)


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

    Executive Summary is always written LAST and synthesizes the full proposal.
    Past Performance uses real data when available, templates when not.

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
        List of written ProposalSection objects (in original outline order).
    """
    tracker = CommitmentTracker()
    written_sections: List[ProposalSection] = []
    exec_summary_outline: Optional[SectionOutline] = None
    exec_summary_index: int = 0

    # Separate exec summary from other sections
    other_sections: List[tuple[int, SectionOutline]] = []
    for i, section_outline in enumerate(outline.sections):
        if section_outline.title.lower().startswith("executive summary"):
            exec_summary_outline = section_outline
            exec_summary_index = i
        else:
            other_sections.append((i, section_outline))

    total = len(outline.sections)

    # Write all sections EXCEPT exec summary first
    section_by_index: Dict[int, ProposalSection] = {}

    for seq, (orig_index, section_outline) in enumerate(other_sections):
        if progress_callback:
            pct = (seq / total) * 0.55 + 0.30
            progress_callback(
                f"Writing section {section_outline.number}: {section_outline.title} "
                f"({seq + 1}/{total})",
                pct,
            )

        logger.info(
            "Writing section %s: %s (target: %d, max: %d words)",
            section_outline.number,
            section_outline.title,
            section_outline.target_word_count,
            section_outline.max_word_count,
        )

        # Check if this is Past Performance
        is_past_perf = any(kw in section_outline.title.lower()
                          for kw in ["past performance", "relevant experience"])

        if is_past_perf:
            section = _write_past_performance(
                client=client,
                rfp=rfp,
                section_outline=section_outline,
                compliance=compliance,
                model=model,
                context=context,
            )
        else:
            section = _write_single_section(
                client=client,
                rfp=rfp,
                section_outline=section_outline,
                compliance=compliance,
                tech_research=tech_research,
                tracker=tracker,
                model=model,
                context=context,
            )

        # Quality gate with retry (rewrite then condense)
        gate = run_quality_gate(section, section_outline)
        if gate.passed:
            logger.info(
                "Section %s passed quality gate (%d words)",
                section_outline.number,
                section.word_count,
            )
        else:
            logger.warning(
                "Section %s failed quality gate: %s",
                section_outline.number,
                gate.feedback,
            )
            # First attempt: rewrite
            section = _rewrite_section(
                client=client,
                section=section,
                feedback=gate.feedback,
                section_outline=section_outline,
                model=model,
            )
            gate = run_quality_gate(section, section_outline)
            if gate.passed:
                logger.info(
                    "Section %s passed quality gate on rewrite (%d words)",
                    section_outline.number,
                    section.word_count,
                )
            elif "too high" in gate.feedback.lower():
                # Second attempt: dedicated condensation call
                logger.warning(
                    "Section %s still over word limit (%d words), running condensation",
                    section_outline.number,
                    section.word_count,
                )
                section = _condense_section(
                    client=client,
                    section=section,
                    section_outline=section_outline,
                    model=model,
                )
                gate = run_quality_gate(section, section_outline)
                if gate.passed:
                    logger.info(
                        "Section %s passed after condensation (%d words)",
                        section_outline.number,
                        section.word_count,
                    )
                else:
                    logger.warning(
                        "Section %s still over after condensation (%d words), proceeding",
                        section_outline.number,
                        section.word_count,
                    )
            else:
                logger.warning(
                    "Section %s still failing after rewrite, proceeding (%d words)",
                    section_outline.number,
                    section.word_count,
                )

        # Record commitments for subsequent sections
        tracker.record(section.number, section.title, section.content)
        section_by_index[orig_index] = section

    # Write Executive Summary LAST with full proposal context
    if exec_summary_outline:
        if progress_callback:
            progress_callback("Writing Executive Summary (synthesizing full proposal)...", 0.83)

        logger.info("Writing Executive Summary LAST with full proposal context")
        all_other_sections = [section_by_index[i] for i, _ in other_sections]
        exec_section = _write_exec_summary(
            client=client,
            rfp=rfp,
            section_outline=exec_summary_outline,
            compliance=compliance,
            all_sections=all_other_sections,
            model=model,
            context=context,
        )
        section_by_index[exec_summary_index] = exec_section

    # Reassemble in original outline order
    result = []
    for i in range(len(outline.sections)):
        if i in section_by_index:
            result.append(section_by_index[i])

    return result


def _write_single_section(
    client: OpenAI,
    rfp: RFPAnalysis,
    section_outline: SectionOutline,
    compliance: ComplianceMatrix,
    tech_research: Dict[str, str],
    tracker: CommitmentTracker,
    model: str,
    context: PipelineContext | None = None,
) -> ProposalSection:
    """Write a single proposal section with full context and commitment awareness."""

    relevant_compliance = _get_relevant_compliance(compliance, section_outline)
    relevant_tech = _get_relevant_tech(tech_research, section_outline)
    commitment_summary = tracker.get_summary()

    user_prompt = _build_section_brief(
        rfp=rfp,
        section_outline=section_outline,
        relevant_compliance=relevant_compliance,
        relevant_tech=relevant_tech,
        commitment_summary=commitment_summary,
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

    content = _strip_leading_heading(content, section_outline.number, section_outline.title)
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


def _write_exec_summary(
    client: OpenAI,
    rfp: RFPAnalysis,
    section_outline: SectionOutline,
    compliance: ComplianceMatrix,
    all_sections: List[ProposalSection],
    model: str,
    context: PipelineContext | None = None,
) -> ProposalSection:
    """Write the Executive Summary LAST, synthesizing the full proposal."""

    max_words = section_outline.max_word_count or 800

    # Build a compact summary of all written sections
    section_summaries = []
    for s in all_sections:
        # First 100 words of each section
        words = s.content.split()[:100]
        summary = " ".join(words)
        if len(s.content.split()) > 100:
            summary += "..."
        section_summaries.append(f"**{s.number}. {s.title}** ({s.word_count} words): {summary}")

    sections_context = "\n\n".join(section_summaries)

    # Company info if available
    company_block = ""
    if context and context.company_profile:
        cp = context.company_profile
        company_block = f"""
## Company Identity (use in the summary)
**Company Name:** {cp.company_name}
**Differentiators:** {', '.join(cp.differentiators[:5])}
**Core Competencies:** {', '.join(cp.core_competencies[:5])}
**Clearance Level:** {cp.clearance_level}
"""

    system = EXEC_SUMMARY_SYSTEM_PROMPT.replace("{max_words}", str(max_words))

    user_prompt = f"""Write the Executive Summary for this proposal.

## RFP Context
**Customer:** {rfp.customer}
**Scope:** {rfp.scope}

## Target: {section_outline.target_word_count} words (MAX {max_words} words)

## Full Proposal Sections (summarize these, don't repeat them)
{sections_context}

## Compliance Coverage
{compliance.coverage_percentage:.0f}% coverage, {compliance.gap_count} gaps
{company_block}
## Guidance
{section_outline.guidance}

Synthesize the above into a compelling, concise Executive Summary."""

    if context and context.win_themes:
        themes = "\n".join(f"- {t}" for t in context.win_themes)
        user_prompt += f"\n\n## Win Themes\n{themes}"

    content = chat_completion(
        client=client,
        system_prompt=system,
        user_prompt=user_prompt,
        model=model,
        max_tokens=4096,
        temperature=0.3,
    )

    content = _strip_leading_heading(content, section_outline.number, section_outline.title)

    return ProposalSection(
        number=section_outline.number,
        title=section_outline.title,
        content=content,
        word_count=len(content.split()),
        requirements_addressed=[
            r.requirement_description
            for r in _get_relevant_compliance(compliance, section_outline)
        ],
    )


def _write_past_performance(
    client: OpenAI,
    rfp: RFPAnalysis,
    section_outline: SectionOutline,
    compliance: ComplianceMatrix,
    model: str,
    context: PipelineContext | None = None,
) -> ProposalSection:
    """Write Past Performance — uses real data if provided, template if not."""

    has_real_data = (
        context is not None
        and context.past_performance is not None
        and len(context.past_performance) > 0
    )

    if has_real_data:
        # Build prompt with REAL past performance data
        entries_text = []
        for pp in context.past_performance:
            entry = f"""**{pp.contract_name}**
- Customer: {pp.customer}
- Contract Number: {pp.contract_number}
- Period of Performance: {pp.period_of_performance}
- Contract Value: {pp.contract_value}
- Description: {pp.description}
- Relevance: {pp.relevance}
- Key Outcomes: {', '.join(pp.key_outcomes)}
- CPARS Rating: {pp.cpars_rating}
- Reference: {pp.reference_name} — {pp.reference_contact}"""
            entries_text.append(entry)

        pp_data = "\n\n".join(entries_text)

        user_prompt = f"""Write the Past Performance section using this REAL data.

## RFP Context
**Customer:** {rfp.customer}
**Scope:** {rfp.scope}
**Target Word Count:** {section_outline.target_word_count}

## Past Performance Data (USE EXACTLY — DO NOT FABRICATE)
{pp_data}

## Section Guidance
{section_outline.guidance}"""

        system = PAST_PERFORMANCE_REAL_PROMPT

    else:
        # Generate template with [COMPANY: ...] markers
        logger.warning(
            "No past performance data provided — generating template with placeholders"
        )

        user_prompt = f"""Generate a Past Performance TEMPLATE section.

## RFP Context
**Customer:** {rfp.customer}
**Scope:** {rfp.scope}
**Target Word Count:** {section_outline.target_word_count}

## Key RFP Requirements to Match Against
{', '.join(r.description[:80] for r in rfp.requirements[:10])}

## Section Guidance
{section_outline.guidance}

Generate 3-4 template entries showing what types of past performance would be most \
relevant for this RFP. Use [COMPANY: ...] markers for all company-specific data."""

        system = PAST_PERFORMANCE_TEMPLATE_PROMPT

    content = chat_completion(
        client=client,
        system_prompt=system,
        user_prompt=user_prompt,
        model=model,
        max_tokens=8192,
        temperature=0.3,
    )

    content = _strip_leading_heading(content, section_outline.number, section_outline.title)

    return ProposalSection(
        number=section_outline.number,
        title=section_outline.title,
        content=content,
        word_count=len(content.split()),
        requirements_addressed=[
            r.requirement_description
            for r in _get_relevant_compliance(compliance, section_outline)
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
Maximum word count: {section_outline.max_word_count}

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

    content = _strip_leading_heading(content, section.number, section.title)

    return ProposalSection(
        number=section.number,
        title=section.title,
        content=content,
        word_count=len(content.split()),
        requirements_addressed=section.requirements_addressed,
    )


CONDENSE_SYSTEM_PROMPT = """\
You are a professional proposal editor. Your ONLY job is to shorten the text below to fit \
within the specified word limit while preserving ALL substantive content.

Rules:
- KEEP all specific commitments, SLAs, tool names, requirement references, and deliverables.
- CUT filler phrases ("it is important to note that"), redundant bullet points, and any content \
  that restates what another section covers (replace with "see Section X").
- MERGE overlapping bullets into single, tighter statements.
- CONVERT verbose paragraphs into concise bullet lists where appropriate.
- Do NOT add new content. Do NOT change the meaning.
- Do NOT include a section heading — just the body content.
- You MUST hit the target word count. Count your words before responding.\
"""


def _condense_section(
    client: OpenAI,
    section: ProposalSection,
    section_outline: SectionOutline,
    model: str,
) -> ProposalSection:
    """Condense an over-length section to fit within the word limit.

    This is a dedicated compression call — different from rewrite because
    the instruction is purely "shorten this" rather than "fix these issues."
    """
    target = section_outline.max_word_count or section_outline.target_word_count
    user_prompt = f"""## Task
Condense the following section from {section.word_count} words to UNDER {target} words.

## Current Content ({section.word_count} words — must reduce to ≤{target})
{section.content}"""

    content = chat_completion(
        client=client,
        system_prompt=CONDENSE_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        model=model,
        max_tokens=8192,
        temperature=0.2,
    )

    content = _strip_leading_heading(content, section.number, section.title)

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


def _build_section_brief(
    rfp: RFPAnalysis,
    section_outline: SectionOutline,
    relevant_compliance: List[ComplianceRow],
    relevant_tech: str,
    commitment_summary: str,
    context: PipelineContext | None = None,
) -> str:
    """Build the full context prompt for writing a single section."""

    parts = [
        f"## Section Brief: {section_outline.number}. {section_outline.title}",
        f"**Target Word Count:** {section_outline.target_word_count} words",
        f"**Maximum Word Count:** {section_outline.max_word_count} words (do NOT exceed)",
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

    # Add commitment tracker to prevent redundancy
    if commitment_summary:
        parts.append(f"\n{commitment_summary}")

    # Add company profile if available
    if context and context.company_profile:
        cp = context.company_profile
        parts.append(f"\n## Company Identity (weave in naturally)")
        if cp.company_name:
            parts.append(f"**Company:** {cp.company_name}")
        if cp.differentiators:
            parts.append(f"**Differentiators:** {', '.join(cp.differentiators[:5])}")
        if cp.clearance_level:
            parts.append(f"**Clearance Level:** {cp.clearance_level}")
        if cp.certifications:
            parts.append(f"**Certifications:** {', '.join(cp.certifications[:5])}")

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
