"""Step 2: Generate proposal outline with guidance, mapped requirements, and word targets."""

from __future__ import annotations

import logging

from openai import OpenAI

from ..models import PipelineContext, ProposalOutline, RFPAnalysis
from ..openai_helpers import structured_output

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are an expert proposal architect for a government/enterprise IT services company.

Given the structured RFP analysis, generate a detailed proposal outline. For EACH section:

1. **number**: Hierarchical section number (e.g., "1", "1.1", "2", "2.1").
2. **title**: Clear, professional section title.
3. **guidance**: Detailed guidance (3-5 sentences) on what content this section should contain, \
   what points to make, what evidence to include, and how to address the evaluators' concerns.
4. **mapped_requirements**: List the specific RFP requirement descriptions that this section \
   MUST address. Copy the exact requirement text from the analysis.
5. **target_word_count**: Target word count proportional to section importance. \
   Use these ranges as BOTH the target AND maximum:
   - Executive Summary: 600-800 words (concise, high-level, NO deep technical detail)
   - Understanding of Requirements: 800-1200 words
   - Major technical sections (3.x): 1000-1500 words
   - Supporting sections (Personnel, Security, QA, etc.): 600-1000 words
   - Past Performance: 800-1200 words
6. **max_word_count**: Hard upper limit. Set to 1.6x the target_word_count. \
   Sections that exceed this will be flagged for trimming.

CRITICAL RULES for avoiding redundancy:
- Each section must have a DISTINCT scope. Do NOT let multiple sections cover the same topic.
- The Executive Summary should ONLY summarize — it must NOT contain detailed technical approach, \
  SLA numbers, tool lists, or architecture details. Those belong in their respective sections.
- If a topic (e.g., "project management") has its own section, other sections should \
  cross-reference it ("See Section X") rather than re-explaining it.
- The guidance field should explicitly state what this section should NOT cover \
  (because it's covered elsewhere).

Required sections (at minimum):
- Executive Summary (written LAST — the pipeline will handle ordering)
- Understanding of Requirements / Problem Statement
- Technical Approach (with sub-sections per major task area)
- Personnel / Staffing Plan
- Security Approach
- Compliance
- Management Plan / Project Management
- Transition / Implementation Plan
- Past Performance (if applicable)
- Quality Assurance

Map EVERY requirement from the RFP analysis to at least one section. \
No requirement should be left unaddressed.\
"""


def generate_outline(
    client: OpenAI,
    rfp: RFPAnalysis,
    model: str = "gpt-5",
    context: PipelineContext | None = None,
) -> ProposalOutline:
    """Generate a detailed proposal outline from the RFP analysis.

    Args:
        client: OpenAI client instance.
        rfp: Structured RFP analysis from Step 1.
        model: Model ID to use.
        context: Optional pipeline context (win themes, etc.).

    Returns:
        ProposalOutline with sections, guidance, mapped requirements, and word targets.
    """
    logger.info("Step 2: Generating proposal outline")

    # Build the user prompt with full RFP details
    requirements_text = "\n".join(
        f"- [{r.category}] {r.description}" for r in rfp.requirements
    )
    tasks_text = "\n".join(f"- {t.title}: {t.description}" for t in rfp.tasks)
    dates_text = "\n".join(f"- {d.event}: {d.date}" for d in rfp.dates)

    user_prompt = f"""Generate a proposal outline for this RFP:

**Customer:** {rfp.customer}
**Scope:** {rfp.scope}

**Tasks:**
{tasks_text}

**Requirements:**
{requirements_text}

**Key Dates:**
{dates_text}"""

    if context and context.win_themes:
        themes = "\n".join(f"- {t}" for t in context.win_themes)
        user_prompt += f"\n\n**Win Themes to weave throughout:**\n{themes}"

    result = structured_output(
        client=client,
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
        response_model=ProposalOutline,
        model=model,
    )

    # Enforce max_word_count defaults if the model didn't set them
    for section in result.sections:
        if section.max_word_count == 0:
            section.max_word_count = int(section.target_word_count * 1.6)

    logger.info(
        "Outline generated: %d sections, total target words: %d",
        len(result.sections),
        sum(s.target_word_count for s in result.sections),
    )
    return result
