"""Step 1: Analyze RFP — extract structured information from raw RFP text."""

from __future__ import annotations

import logging

from openai import OpenAI

from ..models import RFPAnalysis
from ..openai_helpers import structured_output

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are an expert RFP analyst for a government/enterprise IT services company. \
Your job is to extract structured information from Request for Proposal (RFP) documents.

Analyze the provided RFP text and extract:

1. **customer**: The primary government agency or organization issuing the RFP.
2. **scope**: A 2-3 sentence summary of the scope of work being requested.
3. **tasks**: Major deliverable work activities described in the RFP. \
   Include only active tasks (e.g., "develop a web portal", "migrate legacy systems"), \
   NOT compliance requirements or standards.
4. **requirements**: Rules, standards, and constraints the contractor must follow. \
   Categorize each as one of: Security, Compliance, IT Standards, Personnel.
5. **dates**: Key dates mentioned (submission deadlines, performance periods, milestones).

Be thorough — capture ALL tasks, requirements, and dates. \
Consolidate duplicates but do not omit anything.\
"""


def analyze_rfp(
    client: OpenAI,
    rfp_text: str,
    model: str = "gpt-5",
) -> RFPAnalysis:
    """Extract structured RFP analysis from raw text.

    Args:
        client: OpenAI client instance.
        rfp_text: The full text of the RFP document.
        model: Model ID to use.

    Returns:
        RFPAnalysis with extracted customer, scope, tasks, requirements, dates.
    """
    logger.info("Step 1: Analyzing RFP text (%d chars)", len(rfp_text))

    result = structured_output(
        client=client,
        system_prompt=SYSTEM_PROMPT,
        user_prompt=f"Analyze this RFP and extract all structured information:\n\n{rfp_text}",
        response_model=RFPAnalysis,
        model=model,
    )

    logger.info(
        "RFP analysis complete: customer=%s, %d tasks, %d requirements, %d dates",
        result.customer,
        len(result.tasks),
        len(result.requirements),
        len(result.dates),
    )
    return result


def rfp_analysis_from_existing(data: dict) -> RFPAnalysis:
    """Convert an existing RFP analysis dict (from process_rfp.py) to our model.

    This allows the Streamlit UI to pass already-extracted RFP data
    into the proposal pipeline without re-analyzing.
    """
    from ..models import DateItem, Requirement, TaskItem

    tasks = [
        TaskItem(
            title=t.get("title", ""),
            description=t.get("description", ""),
            page=t.get("page", 0),
        )
        for t in data.get("tasks", [])
    ]
    requirements = [
        Requirement(
            category=r.get("category", "General"),
            description=r.get("description", ""),
            page=r.get("page", 0),
        )
        for r in data.get("requirements", [])
    ]
    dates = [
        DateItem(
            event=d.get("event", ""),
            date=d.get("date", ""),
            page=d.get("page", 0),
        )
        for d in data.get("dates", [])
    ]

    return RFPAnalysis(
        customer=data.get("customer", "Unknown"),
        scope=data.get("scope", ""),
        tasks=tasks,
        requirements=requirements,
        dates=dates,
    )
