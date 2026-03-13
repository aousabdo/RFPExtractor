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
   Executive Summary: 400-600 words. Major technical sections: 800-1500 words. \
   Supporting sections: 400-800 words.

Required sections (at minimum):
- Executive Summary
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

    logger.info(
        "Outline generated: %d sections, total target words: %d",
        len(result.sections),
        sum(s.target_word_count for s in result.sections),
    )
    return result
