# === agents_scrm_sbom.py ===
from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agno.tools.reasoning import ReasoningTools
from policy_packs import inject_pack_context

import dotenv, os

llm_model = os.getenv("LLM_MODEL", "gpt-5")

_base_instructions = [
    "Based on ACTIVE_POLICY_PACK.scrm toggles:",
    "- Always include SBOM plan: CycloneDX or SPDX, generation cadence, signing, storage, exception handling, review gates.",
    "- If section_889=True, include covered telecom reporting: CO/COR/NOSC/ESOC paths and 1-business-day timeline.",
    "- If kaspersky=True, include prohibition/attestation language.",
    "Output two deliverables:",
    "1) 'SOP' (1–2 pages, markdown): practical step-by-step procedure and R&R.",
    "2) 'ExecutiveSummary' (≤150 words) to paste into the main proposal body.",
    "Be specific about artifacts (attestation templates, SBOM filenames, locations) without referencing internal secrets.",
]

def build_scrm_sbom_agent(active_pack_name: str) -> Agent:
    return Agent(
        name="SCRM & SBOM Agent (US)",
        role="Drafts SBOM/SCRM SOP and summary with correct US toggles.",
        model=OpenAIChat(id=llm_model),
        tools=[ReasoningTools(add_instructions=True)],
        instructions=inject_pack_context(_base_instructions, active_pack_name),
        add_datetime_to_instructions=True,
    )
