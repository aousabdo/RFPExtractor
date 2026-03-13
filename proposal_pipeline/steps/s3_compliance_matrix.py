"""Step 3: Build compliance matrix — map every requirement to a proposal section."""

from __future__ import annotations

import logging

from openai import OpenAI

from ..models import ComplianceMatrix, ProposalOutline, RFPAnalysis
from ..openai_helpers import structured_output

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are a compliance specialist for government/enterprise proposals.

Given the RFP analysis and proposal outline, create a compliance matrix that maps \
EVERY requirement from the RFP to the appropriate proposal section.

For each requirement:
1. **requirement_id**: Assign a unique ID (e.g., "REQ-SEC-001", "REQ-COMP-003").
2. **requirement_description**: The full requirement text.
3. **category**: The requirement category (Security, Compliance, IT Standards, Personnel).
4. **source_page**: The page number from the RFP (use 0 if unknown).
5. **proposal_section**: The section number from the outline that will address this requirement.
6. **compliance_status**: "Full" if the section guidance already covers this requirement. \
   "Partial" if partially addressed. "Gap" if no section adequately covers it.
7. **notes**: Any notes about how to address the requirement or why there's a gap.

Also compute:
- **gap_count**: Number of requirements with "Gap" status.
- **coverage_percentage**: Percentage of requirements with "Full" or "Partial" status.

EVERY requirement must appear in the matrix. If a requirement doesn't fit any section, \
mark it as "Gap" and suggest which section should be expanded to cover it.\
"""


def build_compliance_matrix(
    client: OpenAI,
    rfp: RFPAnalysis,
    outline: ProposalOutline,
    model: str = "gpt-5",
) -> ComplianceMatrix:
    """Build a compliance matrix mapping requirements to proposal sections.

    Args:
        client: OpenAI client instance.
        rfp: Structured RFP analysis.
        outline: Proposal outline with sections.
        model: Model ID to use.

    Returns:
        ComplianceMatrix with all requirements mapped.
    """
    logger.info(
        "Step 3: Building compliance matrix for %d requirements",
        len(rfp.requirements),
    )

    requirements_text = "\n".join(
        f"- [{r.category}] (page {r.page}) {r.description}" for r in rfp.requirements
    )
    outline_text = "\n".join(
        f"- Section {s.number}: {s.title} — {s.guidance[:100]}..."
        for s in outline.sections
    )

    user_prompt = f"""Build a compliance matrix for this proposal:

**RFP Requirements:**
{requirements_text}

**Proposal Outline:**
{outline_text}

Map every requirement to a proposal section. Identify any gaps."""

    result = structured_output(
        client=client,
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
        response_model=ComplianceMatrix,
        model=model,
    )

    logger.info(
        "Compliance matrix built: %d rows, %.0f%% coverage, %d gaps",
        len(result.rows),
        result.coverage_percentage,
        result.gap_count,
    )
    return result
