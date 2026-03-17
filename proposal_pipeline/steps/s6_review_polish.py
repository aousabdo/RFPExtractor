"""Step 6: Review and polish — grammar, clarity, tone harmonization, redundancy removal."""

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
7. **Redundancy**: If this section repeats content from other sections in the proposal \
   (listed under "Other Section Topics"), replace the repeated content with a brief \
   cross-reference like "as detailed in Section X" and use the freed space for \
   new, section-specific content.

CRITICAL RULES:
- Do NOT reduce the content length below 80% of original. Maintain or increase word count.
- Do NOT remove technical details or specific information.
- Do NOT add placeholder text or TODO markers.
- PRESERVE all compliance-related language and requirement references.
- REMOVE redundant content that duplicates other sections, replacing with cross-references.

Output ONLY the polished section content in markdown format.\
"""


def review_and_polish(
    client: OpenAI,
    sections: List[ProposalSection],
    model: str = "gpt-5",
    context: PipelineContext | None = None,
    progress_callback: Optional[Callable[[str, float], None]] = None,
) -> List[ProposalSection]:
    """Review and polish all proposal sections with cross-section awareness.

    Each section gets context about what other sections cover, enabling
    the editor to remove redundancy and add cross-references.

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

    # Build a topic map of all sections for cross-reference awareness
    topic_map = _build_topic_map(sections)

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

        # Build cross-section context (what other sections cover)
        other_topics = _get_other_topics(topic_map, section.number)

        user_prompt = (
            f"Polish this proposal section:\n\n"
            f"**Section {section.number}: {section.title}**\n\n"
            f"{section.content}"
        )

        if other_topics:
            user_prompt += (
                f"\n\n## Other Section Topics (remove redundancy, cross-reference instead)\n"
                f"{other_topics}"
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


def _build_topic_map(sections: List[ProposalSection]) -> dict[str, str]:
    """Build a map of section number → key topics covered (first 50 words)."""
    topic_map = {}
    for s in sections:
        # Extract key topics: headings and first sentence of each paragraph
        lines = s.content.split("\n")
        topics = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith("**"):
                topics.append(stripped.lstrip("#*").strip())
        # Also add first 50 words as context
        first_words = " ".join(s.content.split()[:50])
        topic_map[s.number] = (
            f"Section {s.number} ({s.title}): "
            f"Topics: {', '.join(topics[:8])}. "
            f"Preview: {first_words}..."
        )
    return topic_map


def _get_other_topics(topic_map: dict[str, str], current_number: str) -> str:
    """Get topic summaries for all sections except the current one."""
    other = [
        desc for num, desc in topic_map.items()
        if num != current_number
    ]
    return "\n".join(other[:15])  # Cap at 15 to manage token count
