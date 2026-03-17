"""Step 6b: Compress proposal to fit page limits (runs after scoring).

This step only runs when the RFP specifies a page limit. It takes the
full-length, polished, scored proposal and compresses each section
proportionally to hit the total word budget — informed by scoring
feedback so high-value content is preserved and weak filler is cut.

The full-length version is always saved separately as proposal_full.*
"""

from __future__ import annotations

import logging
from typing import Callable, List, Optional

from openai import OpenAI

from ..models import ProposalSection, SectionScore
from ..openai_helpers import chat_completion

logger = logging.getLogger(__name__)

COMPRESS_SYSTEM_PROMPT = """\
You are a senior proposal editor specializing in page-limited government submissions. \
Your job is to compress the provided proposal section to fit within a strict word budget \
while preserving ALL substantive content that matters to evaluators.

COMPRESSION RULES:
1. PRESERVE: All specific commitments, SLAs, deliverables, tool names, requirement \
   references, and compliance language. These are what evaluators score on.
2. PRESERVE: Content identified as "strengths" in the scoring feedback below.
3. CUT FIRST: Filler phrases ("it is important to note that", "we are committed to"), \
   redundant bullet points that say the same thing twice, and any content that \
   restates what another section covers (replace with "see Section X").
4. CUT: Overly detailed process descriptions that can be summarized in 1-2 sentences.
5. MERGE: Overlapping bullets into single, tighter statements.
6. CONVERT: Verbose paragraphs into concise bullet lists where appropriate.
7. ADDRESS: If scoring feedback identified weaknesses, try to fix them during \
   compression rather than just cutting around them.
8. Do NOT add new content. Do NOT change factual claims.
9. Do NOT include a section heading — just the body content.
10. You MUST stay within the target word count.\
"""


def compress_to_page_limit(
    client: OpenAI,
    sections: List[ProposalSection],
    scores: List[SectionScore],
    total_word_budget: int,
    model: str = "gpt-5.4",
    progress_callback: Optional[Callable[[str, float], None]] = None,
) -> List[ProposalSection]:
    """Compress all sections proportionally to fit within a total word budget.

    Uses scoring feedback to make smart decisions about what to preserve vs cut.

    Args:
        client: OpenAI client.
        sections: Full-length proposal sections.
        scores: Scoring results for each section (parallel list).
        total_word_budget: Maximum total words across all sections.
        model: Model ID for compression (recommend gpt-5.4 for judgment quality).
        progress_callback: Optional progress callback.

    Returns:
        List of compressed ProposalSection objects.
    """
    current_total = sum(s.word_count for s in sections)

    if current_total <= total_word_budget:
        logger.info(
            "Proposal already within budget (%d words ≤ %d). Skipping compression.",
            current_total,
            total_word_budget,
        )
        return sections

    logger.info(
        "Compressing proposal from %d to ≤%d words (%.0f%% reduction needed)",
        current_total,
        total_word_budget,
        (1 - total_word_budget / current_total) * 100,
    )

    # Allocate word budget proportionally to each section's current size
    section_budgets = _allocate_budgets(sections, total_word_budget)

    # Build score lookup
    score_map = {s.section_number: s for s in scores}

    compressed: List[ProposalSection] = []
    total = len(sections)

    for i, section in enumerate(sections):
        budget = section_budgets[i]

        if progress_callback:
            pct = (i / total) * 0.04 + 0.93  # Map to 93%-97%
            progress_callback(
                f"Compressing section {section.number}: {section.title} "
                f"({section.word_count} → {budget} words)",
                pct,
            )

        # Skip compression if section is already within budget
        if section.word_count <= budget:
            logger.info(
                "Section %s already within budget (%d ≤ %d), keeping as-is",
                section.number,
                section.word_count,
                budget,
            )
            compressed.append(section)
            continue

        # Get scoring feedback for this section
        score = score_map.get(section.number)
        scoring_context = _build_scoring_context(score) if score else ""

        logger.info(
            "Compressing section %s: %d → %d words",
            section.number,
            section.word_count,
            budget,
        )

        compressed_section = _compress_single_section(
            client=client,
            section=section,
            word_budget=budget,
            scoring_context=scoring_context,
            model=model,
        )

        logger.info(
            "Section %s compressed: %d → %d words (target: %d)",
            section.number,
            section.word_count,
            compressed_section.word_count,
            budget,
        )

        compressed.append(compressed_section)

    final_total = sum(s.word_count for s in compressed)
    logger.info(
        "Compression complete: %d → %d words (budget: %d)",
        current_total,
        final_total,
        total_word_budget,
    )

    return compressed


def _allocate_budgets(
    sections: List[ProposalSection],
    total_budget: int,
) -> List[int]:
    """Allocate word budgets proportionally based on current section sizes.

    Each section gets a budget proportional to its share of the total words,
    with a minimum of 200 words per section.
    """
    current_total = sum(s.word_count for s in sections)
    if current_total == 0:
        return [200] * len(sections)

    min_words = 200
    available = total_budget - (min_words * len(sections))
    if available < 0:
        # Budget is too small even for minimums — just distribute evenly
        return [total_budget // len(sections)] * len(sections)

    budgets = []
    for section in sections:
        proportion = section.word_count / current_total
        budget = min_words + int(available * proportion)
        budgets.append(budget)

    return budgets


def _build_scoring_context(score: SectionScore) -> str:
    """Build a compact scoring context string for the compressor."""
    parts = [f"**Evaluator Score: {score.score}/100**"]

    if score.strengths:
        strengths = "\n".join(f"  - {s}" for s in score.strengths[:3])
        parts.append(f"**Strengths (PRESERVE these):**\n{strengths}")

    if score.weaknesses:
        weaknesses = "\n".join(f"  - {w}" for w in score.weaknesses[:3])
        parts.append(f"**Weaknesses (fix or cut):**\n{weaknesses}")

    if score.recommendations:
        recs = "\n".join(f"  - {r}" for r in score.recommendations[:3])
        parts.append(f"**Recommendations:**\n{recs}")

    return "\n".join(parts)


def _compress_single_section(
    client: OpenAI,
    section: ProposalSection,
    word_budget: int,
    scoring_context: str,
    model: str,
) -> ProposalSection:
    """Compress a single section to fit within its word budget."""

    user_prompt = f"""## Task
Compress the following section from {section.word_count} words to UNDER {word_budget} words.

## Scoring Feedback (use to decide what to keep vs cut)
{scoring_context}

## Current Content ({section.word_count} words — must compress to ≤{word_budget})
{section.content}"""

    content = chat_completion(
        client=client,
        system_prompt=COMPRESS_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        model=model,
        max_tokens=8192,
        temperature=0.2,
    )

    # Strip any heading the model might add
    lines = content.split("\n")
    for i, line in enumerate(lines[:3]):
        stripped = line.strip()
        if stripped.startswith("#") or stripped.lower().startswith("section"):
            lines.pop(i)
            while i < len(lines) and not lines[i].strip():
                lines.pop(i)
            content = "\n".join(lines)
            break

    return ProposalSection(
        number=section.number,
        title=section.title,
        content=content,
        word_count=len(content.split()),
        requirements_addressed=section.requirements_addressed,
    )
