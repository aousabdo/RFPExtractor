"""Step 4: Technology research — recommend relevant technologies based on RFP."""

from __future__ import annotations

import logging
from typing import Dict, List

from openai import OpenAI

from ..models import RFPAnalysis
from ..openai_helpers import chat_completion

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are a senior solutions architect for a government/enterprise IT services company.

Given the RFP analysis, identify the key technology areas relevant to this project and \
provide detailed technology recommendations for each area.

For each technology area, provide:
- **Recommended technologies/frameworks** with specific product names and versions
- **Why this technology is the best fit** for government/enterprise use
- **Compliance and security considerations** (FedRAMP, FISMA, Section 508, etc.)
- **Implementation best practices** and architectural patterns
- **Alternatives considered** and why the recommended option is preferred

Format your response as a structured analysis with clear headings for each technology area.

Focus on technologies that are:
- Proven in government/enterprise environments
- FedRAMP authorized or authorization-ready where applicable
- Well-supported with strong vendor backing
- Compliant with accessibility standards (Section 508 / WCAG 2.2)

Be specific and detailed — name exact products, versions, and configurations. \
Avoid generic recommendations.\
"""


def research_technologies(
    client: OpenAI,
    rfp: RFPAnalysis,
    model: str = "gpt-5",
) -> Dict[str, str]:
    """Research and recommend technologies relevant to the RFP.

    Uses LLM knowledge to provide technology recommendations.
    Returns a dict mapping technology areas to detailed findings.

    Args:
        client: OpenAI client instance.
        rfp: Structured RFP analysis.
        model: Model ID to use.

    Returns:
        Dict mapping technology area names to detailed recommendation text.
    """
    logger.info("Step 4: Researching technologies for %d tasks", len(rfp.tasks))

    tasks_text = "\n".join(f"- {t.title}: {t.description}" for t in rfp.tasks)
    it_reqs = [r for r in rfp.requirements if r.category == "IT Standards"]
    security_reqs = [r for r in rfp.requirements if r.category == "Security"]

    it_text = "\n".join(f"- {r.description}" for r in it_reqs) or "None specified"
    sec_text = "\n".join(f"- {r.description}" for r in security_reqs) or "None specified"

    user_prompt = f"""Research and recommend technologies for this RFP:

**Customer:** {rfp.customer}
**Scope:** {rfp.scope}

**Major Tasks:**
{tasks_text}

**IT Standards Requirements:**
{it_text}

**Security Requirements:**
{sec_text}

Provide detailed technology recommendations organized by technology area."""

    response = chat_completion(
        client=client,
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
        model=model,
        max_tokens=4096,
    )

    # Parse the response into sections by heading
    tech_research = _parse_tech_sections(response)

    logger.info("Tech research complete: %d areas covered", len(tech_research))
    return tech_research


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
