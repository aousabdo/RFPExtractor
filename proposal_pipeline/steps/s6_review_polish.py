"""Step 6: Review and polish — grammar, clarity, tone harmonization in one pass."""

from __future__ import annotations

import logging
from typing import Callable, List, Optional

from openai import OpenAI

from ..models import PipelineContext, ProposalSection
from ..openai_helpers import chat_completion

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are a senior proposal editor for a government/enterprise IT services company. \
Review and polish the provided proposal section for:

1. **Grammar & Spelling**: Fix all errors. Use American English.
2. **Clarity**: Simplify convoluted sentences. Ensure each paragraph has a clear point.
3. **Professional Tone**: Formal but readable. Confident, not arrogant. \
   Active voice preferred. Avoid jargon without explanation.
4. **Persuasiveness**: Strengthen value propositions. Add transition phrases. \
   Ensure the section builds a compelling case.
5. **Consistency**: Match the tone and style of other sections in the proposal.
6. **Flow**: Ensure logical progression within the section. \
   Each paragraph should connect to the next.

CRITICAL RULES:
- Do NOT reduce the content length. Maintain or increase word count.
- Do NOT remove technical details or specific information.
- Do NOT add placeholder text or TODO markers.
- PRESERVE all compliance-related language and requirement references.

Output ONLY the polished section content in markdown format.\
"""


def review_and_polish(
    client: OpenAI,
    sections: List[ProposalSection],
    model: str = "gpt-5",
    context: PipelineContext | None = None,
    progress_callback: Optional[Callable[[str, float], None]] = None,
) -> List[ProposalSection]:
    """Review and polish all proposal sections.

    Combines grammar, clarity, and tone review into a single pass per section.
    Rejects polished versions that shrink content below 80% of original.

    Args:
        client: OpenAI client.
        sections: List of drafted proposal sections.
        model: Model ID.
        context: Optional pipeline context with style guide.
        progress_callback: Optional progress callback.

    Returns:
        List of polished ProposalSection objects.
    """
    polished: List[ProposalSection] = []
    total = len(sections)

    for i, section in enumerate(sections):
        if progress_callback:
            pct = (i / total) * 0.05 + 0.87  # Map to 87%-92%
            progress_callback(
                f"Polishing section {section.number}: {section.title}",
                pct,
            )

        logger.info("Polishing section %s: %s", section.number, section.title)

        system = SYSTEM_PROMPT
        if context and context.company_style_guide:
            system += (
                f"\n\n## Company Style Guide (follow these conventions):\n"
                f"{context.company_style_guide}"
            )

        user_prompt = (
            f"Polish this proposal section:\n\n"
            f"**Section {section.number}: {section.title}**\n\n"
            f"{section.content}"
        )

        polished_content = chat_completion(
            client=client,
            system_prompt=system,
            user_prompt=user_prompt,
            model=model,
            max_tokens=8192,
            temperature=0.2,
        )

        polished_word_count = len(polished_content.split())
        original_word_count = section.word_count or len(section.content.split())

        # Safety check: reject polish if it significantly reduced content
        if original_word_count > 0 and polished_word_count < original_word_count * 0.8:
            logger.warning(
                "Section %s polish rejected: %d → %d words (%.0f%% reduction). "
                "Keeping original.",
                section.number,
                original_word_count,
                polished_word_count,
                (1 - polished_word_count / original_word_count) * 100,
            )
            polished.append(section)
        else:
            polished.append(
                ProposalSection(
                    number=section.number,
                    title=section.title,
                    content=polished_content,
                    word_count=polished_word_count,
                    requirements_addressed=section.requirements_addressed,
                )
            )

    return polished
