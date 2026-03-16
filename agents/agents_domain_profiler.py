# === agents_domain_profiler.py ===
from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agno.tools.reasoning import ReasoningTools

import dotenv, os

llm_model = os.getenv("LLM_MODEL", "gpt-5")

domain_profiler = Agent(
    name="Domain Profiler & Clarifier (US)",
    role=("Classifies RFPs for the US market into US_GOV vs US_COMMERCIAL; "
          "extracts frameworks and flags; drafts buyer questions for ambiguities."),
    model=OpenAIChat(id=llm_model),
    tools=[ReasoningTools(add_instructions=True)],
    instructions=[
        "Analyze the provided RFP/proposal text or structured extract.",
        "Output ONLY valid JSON with keys: domain (US_GOV|US_COMMERCIAL), "
        "frameworks (list of strings among: NIST_800_53, FedRAMP, 508, ISO_27001, SOC2, WCAG_2_2), "
        "flags (list among: SECTION_889, KASPERSKY, DATA_RESIDENCY, EXPORT_CONTROL, ACCESS_CLEARANCE), "
        "open_questions (list of short buyer questions). No prose.",
        "If uncertain, infer using strongest signals present.",
    ],
    add_datetime_to_instructions=True,
)
