"""Step 7: Score proposal sections and rewrite weak ones."""

from __future__ import annotations

import json
import logging
from typing import List, Tuple

from openai import OpenAI

from ..models import (
    ComplianceMatrix,
    ProposalSection,
    RFPAnalysis,
    SectionScore,
)
from ..openai_helpers import chat_completion, structured_output

logger = logging.getLogger(__name__)

SCORING_SYSTEM_PROMPT = """\
You are a harsh, experienced government source selection evaluator who has read \
hundreds of proposals. You score TOUGH — a 90+ means the section is genuinely \
exceptional and ready to submit with zero changes. Most AI-generated proposals \
score 65-80 in your experience.

Score the provided proposal section on a 0-100 scale across these criteria:
- **Compliance** (25%): Does it address ALL mapped RFP requirements with specificity? \
  Vague compliance claims score low. Must show HOW, not just assert compliance.
- **Completeness** (25%): Is the content thorough with specific tools, timelines, \
  metrics, and deliverables? Generic "best practices" language scores low.
- **Clarity** (25%): Is it well-organized and concise? Verbose repetition scores low. \
  Does each paragraph add new value?
- **Competitiveness** (25%): Does it differentiate from competitors? Would this win \
  against 4-5 other proposals? Generic government boilerplate scores low.

SCORING CALIBRATION:
- 90-100: Exceptional. Ready to submit. Specific, compelling, zero filler.
- 80-89: Very good. Minor improvements needed. Mostly specific and compelling.
- 70-79: Acceptable. Meets requirements but lacks specificity or differentiation.
- 60-69: Marginal. Significant gaps, vague language, or excessive boilerplate.
- Below 60: Unacceptable. Major rewrites needed.

Set requires_rewrite to true if score < 70.
Be brutally specific in weaknesses — quote the actual text that's weak. \
No generic feedback like "could be more detailed" — say exactly WHAT needs detail.\
"""

REWRITE_SYSTEM_PROMPT = """\
You are an expert proposal writer. Rewrite this proposal section to address the specific \
weaknesses and recommendations identified by the scoring evaluation.

You must:
- Address EVERY recommendation listed
- Fix EVERY weakness identified
- Maintain all existing strengths
- Keep or exceed the current word count
- Produce submission-ready content with no placeholders

Output ONLY the rewritten section content in markdown format.\
"""


def score_and_rewrite(
    client: OpenAI,
    sections: List[ProposalSection],
    rfp: RFPAnalysis,
    compliance: ComplianceMatrix,
    model: str = "gpt-5",
) -> Tuple[List[ProposalSection], List[SectionScore], float]:
    """Score all sections and rewrite any that fall below threshold.

    Args:
        client: OpenAI client.
        sections: List of polished proposal sections.
        rfp: RFP analysis for context.
        compliance: Compliance matrix for requirement checking.
        model: Model ID.

    Returns:
        Tuple of (updated sections, scores, overall average score).
    """
    logger.info("Step 7: Scoring %d proposal sections", len(sections))

    scores = _score_all_sections(client, sections, rfp, compliance, model)

    # Rewrite sections that scored below 70
    updated_sections = list(sections)
    for i, score in enumerate(scores):
        if score.requires_rewrite and score.score < 70:
            logger.warning(
                "Section %s scored %d — triggering rewrite",
                score.section_number,
                score.score,
            )
            updated_sections[i] = _rewrite_with_feedback(
                client=client,
                section=sections[i],
                score=score,
                rfp=rfp,
                model=model,
            )
            # Re-score the rewritten section
            new_score = _score_single_section(
                client, updated_sections[i], rfp, compliance, model
            )
            logger.info(
                "Section %s re-scored: %d → %d",
                score.section_number,
                score.score,
                new_score.score,
            )
            scores[i] = new_score

    overall = sum(s.score for s in scores) / len(scores) if scores else 0.0

    logger.info("Scoring complete. Overall score: %.1f/100", overall)
    return updated_sections, scores, overall


def _score_all_sections(
    client: OpenAI,
    sections: List[ProposalSection],
    rfp: RFPAnalysis,
    compliance: ComplianceMatrix,
    model: str,
) -> List[SectionScore]:
    """Score all sections."""
    scores = []
    for section in sections:
        score = _score_single_section(client, section, rfp, compliance, model)
        scores.append(score)
        logger.info(
            "Section %s (%s): %d/100",
            score.section_number,
            score.section_title,
            score.score,
        )
    return scores


def _score_single_section(
    client: OpenAI,
    section: ProposalSection,
    rfp: RFPAnalysis,
    compliance: ComplianceMatrix,
    model: str,
) -> SectionScore:
    """Score a single proposal section using structured output for reliable parsing."""
    # Get compliance rows for this section
    relevant_reqs = [
        f"- [{r.requirement_id}] {r.requirement_description}"
        for r in compliance.rows
        if r.proposal_section == section.number
        or section.number in r.proposal_section
    ]
    reqs_text = "\n".join(relevant_reqs) if relevant_reqs else "None specifically mapped"

    user_prompt = f"""Score this proposal section:

**Section {section.number}: {section.title}**
**Word Count:** {section.word_count}

**RFP Customer:** {rfp.customer}
**RFP Scope:** {rfp.scope}

**Requirements this section should address:**
{reqs_text}

**Section Content:**
{section.content}"""

    try:
        return structured_output(
            client=client,
            system_prompt=SCORING_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            response_model=SectionScore,
            model=model,
            max_retries=2,
        )
    except Exception as e:
        logger.warning(
            "Structured scoring failed for section %s, falling back to chat: %s",
            section.number,
            e,
        )
        # Fallback: try chat_completion with JSON extraction
        return _score_via_chat_fallback(client, section, rfp, reqs_text, model)


def _score_via_chat_fallback(
    client: OpenAI,
    section: ProposalSection,
    rfp: RFPAnalysis,
    reqs_text: str,
    model: str,
) -> SectionScore:
    """Fallback scorer using chat_completion with robust JSON extraction."""
    fallback_system = (
        SCORING_SYSTEM_PROMPT
        + "\n\nRespond with a JSON object containing: section_number, section_title, "
        "score (int 0-100), strengths (list of strings), weaknesses (list of strings), "
        "recommendations (list of strings), requires_rewrite (bool, true if score < 70)."
    )

    user_prompt = f"""Score this proposal section:

**Section {section.number}: {section.title}**
**Word Count:** {section.word_count}

**RFP Customer:** {rfp.customer}
**RFP Scope:** {rfp.scope}

**Requirements this section should address:**
{reqs_text}

**Section Content (first 3000 chars):**
{section.content[:3000]}"""

    response = chat_completion(
        client=client,
        system_prompt=fallback_system,
        user_prompt=user_prompt,
        model=model,
        max_tokens=2048,
        temperature=0.2,
    )

    try:
        if not response:
            raise json.JSONDecodeError("Empty response", "", 0)
        json_str = response.strip()
        # Strip markdown code fences
        if "```" in json_str:
            parts = json_str.split("```")
            for part in parts[1:]:
                candidate = part.strip()
                if candidate.startswith("json"):
                    candidate = candidate[4:].strip()
                if candidate and candidate[0] == "{":
                    json_str = candidate
                    break
        # Find JSON object in response
        if not json_str.startswith("{"):
            start = json_str.find("{")
            end = json_str.rfind("}") + 1
            if start != -1 and end > start:
                json_str = json_str[start:end]
        data = json.loads(json_str)
        return SectionScore(
            section_number=data.get("section_number", section.number),
            section_title=data.get("section_title", section.title),
            score=data.get("score", 0),
            strengths=data.get("strengths", []),
            weaknesses=data.get("weaknesses", []),
            recommendations=data.get("recommendations", []),
            requires_rewrite=data.get("requires_rewrite", False),
        )
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        logger.warning("Fallback scoring also failed for section %s: %s", section.number, e)
        return SectionScore(
            section_number=section.number,
            section_title=section.title,
            score=50,
            strengths=["Could not parse scoring response"],
            weaknesses=["Scoring parse error — manual review needed"],
            recommendations=["Re-run scoring"],
            requires_rewrite=False,
        )


def _rewrite_with_feedback(
    client: OpenAI,
    section: ProposalSection,
    score: SectionScore,
    rfp: RFPAnalysis,
    model: str,
) -> ProposalSection:
    """Rewrite a section based on scoring feedback."""
    weaknesses = "\n".join(f"- {w}" for w in score.weaknesses)
    recommendations = "\n".join(f"- {r}" for r in score.recommendations)

    user_prompt = f"""## Section to Rewrite
**{section.number}. {section.title}** (Current score: {score.score}/100)

## Current Content
{section.content}

## Weaknesses to Fix
{weaknesses}

## Specific Recommendations
{recommendations}

## RFP Context
**Customer:** {rfp.customer}
**Scope:** {rfp.scope}

Rewrite this section to address all weaknesses and recommendations above."""

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
