"""Step 4: Technology research — per-task-area recommendations based on RFP."""

from __future__ import annotations

import logging
from typing import Dict, List

from openai import OpenAI

from ..models import RFPAnalysis
from ..openai_helpers import chat_completion

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are a senior solutions architect for a government/enterprise IT services company.

Given a specific task area from an RFP, provide concise technology recommendations:
- **Recommended technologies** with specific product names (FedRAMP-authorized where applicable)
- **Architecture patterns** relevant to this task
- **Compliance considerations** (FedRAMP, FISMA, Section 508, etc.)
- **Key differentiators** — what would make this approach stand out

Be specific: name exact products and services (e.g., "Amazon EKS in GovCloud", not "container orchestration").
Keep your response focused and under 500 words per task area.\
"""


def research_technologies(
    client: OpenAI,
    rfp: RFPAnalysis,
    model: str = "gpt-5",
) -> Dict[str, str]:
    """Research technologies for each major task area in the RFP.

    Makes one API call per task area (up to 8) for focused, relevant results.
    Falls back to a single combined call if there are fewer than 2 tasks.

    Args:
        client: OpenAI client instance.
        rfp: Structured RFP analysis.
        model: Model ID to use.

    Returns:
        Dict mapping technology area names to detailed recommendation text.
    """
    logger.info("Step 4: Researching technologies for %d tasks", len(rfp.tasks))

    # Gather requirement context
    it_reqs = [r for r in rfp.requirements if r.category == "IT Standards"]
    security_reqs = [r for r in rfp.requirements if r.category == "Security"]
    it_text = "\n".join(f"- {r.description}" for r in it_reqs) or "None specified"
    sec_text = "\n".join(f"- {r.description}" for r in security_reqs) or "None specified"

    context_block = f"""**Customer:** {rfp.customer}
**Scope:** {rfp.scope}

**IT Standards Requirements:**
{it_text}

**Security Requirements:**
{sec_text}"""

    tech_research: Dict[str, str] = {}

    if len(rfp.tasks) < 2:
        # Fallback: single combined research call
        tech_research = _research_combined(client, rfp, context_block, model)
    else:
        # Research each task area individually (cap at 8 to manage cost)
        tasks_to_research = rfp.tasks[:8]
        for task in tasks_to_research:
            logger.info("Researching tech for: %s", task.title)
            user_prompt = f"""Recommend technologies for this task area:

**Task:** {task.title}
**Description:** {task.description}

{context_block}

Provide specific, actionable technology recommendations for this task area."""

            response = chat_completion(
                client=client,
                system_prompt=SYSTEM_PROMPT,
                user_prompt=user_prompt,
                model=model,
                max_tokens=2048,
            )
            tech_research[task.title] = response

    logger.info("Tech research complete: %d areas covered", len(tech_research))
    return tech_research


def _research_combined(
    client: OpenAI,
    rfp: RFPAnalysis,
    context_block: str,
    model: str,
) -> Dict[str, str]:
    """Fallback: single combined technology research call."""
    tasks_text = "\n".join(f"- {t.title}: {t.description}" for t in rfp.tasks)

    user_prompt = f"""Research and recommend technologies for this RFP:

{context_block}

**Major Tasks:**
{tasks_text}

Provide detailed technology recommendations organized by technology area."""

    response = chat_completion(
        client=client,
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
        model=model,
        max_tokens=4096,
    )

    # Parse the response into sections by heading
    return _parse_tech_sections(response)


def _parse_tech_sections(response: str) -> Dict[str, str]:
    """Parse the LLM response into technology area sections."""
    sections: Dict[str, str] = {}
    current_heading = "General"
    current_content: List[str] = []

    for line in response.split("\n"):
        stripped = line.strip()
        # Detect markdown headings (## or ###)
        if stripped.startswith("#"):
            # Save previous section
            if current_content:
                sections[current_heading] = "\n".join(current_content).strip()
            current_heading = stripped.lstrip("#").strip()
            current_content = []
        else:
            current_content.append(line)

    # Save final section
    if current_content:
        sections[current_heading] = "\n".join(current_content).strip()

    # If no headings were found, return the whole response
    if not sections:
        sections["Technology Recommendations"] = response

    return sections
