# === agents_controls_mapper.py ===
from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agno.tools.reasoning import ReasoningTools
from policy_packs import inject_pack_context

import dotenv, os

llm_model = os.getenv("LLM_MODEL", "gpt-5")

_base_instructions = [
    "Input: list of staffing roles with responsibilities; ACTIVE_POLICY_PACK.",
    "If pack.controls includes NIST_800_53, map roles to relevant NIST families and specific controls "
    "(e.g., AC-2, AU-12, CM-6, CP-9, IA-2, IR-4, SC-13, SI-2, SR-3).",
    "If pack.controls includes ISO_27001 or SOC2, map to Annex A controls or SOC2 CC series accordingly.",
    "Output a markdown table with columns: Role | Framework | Control | Responsibility | Evidence Artifact.",
    "Keep mappings specific and auditable (e.g., 'DBA → AU-12: log review weekly; evidence: SIEM report IDs').",
]

def build_controls_mapper(active_pack_name: str) -> Agent:
    return Agent(
        name="Controls Mapper (US)",
        role="Maps staffing to applicable controls based on US policy pack.",
        model=OpenAIChat(id=llm_model),
        tools=[ReasoningTools(add_instructions=True)],
        instructions=inject_pack_context(_base_instructions, active_pack_name),
        add_datetime_to_instructions=True,
    )
