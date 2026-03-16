# === agents_accessibility.py ===
from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agno.tools.reasoning import ReasoningTools
from policy_packs import inject_pack_context

import dotenv, os
llm_model = os.getenv("LLM_MODEL", "gpt-5")

_base_instructions = [
    "Use ACTIVE_POLICY_PACK.accessibility to choose standards.",
    "- If 'Section_508' present: align to DHS Trusted Tester style checks (keyboard, focus order, contrast, alt text, ARIA, screen reader flows; ANDI is acceptable as an example tool).",
    "- If WCAG_2_2_AA present: produce WCAG 2.2 AA test set.",
    "Output two elements:",
    "1) Per-deliverable checklist table: Deliverable | Test | Method | Pass Criteria | Evidence | Owner.",
    "2) 'DefinitionOfDone' snippet (≤200 words) that can be added to QA/DoD.",
    "Be concrete, testable, and concise. No generic platitudes.",
]

def build_accessibility_agent(active_pack_name: str) -> Agent:
    return Agent(
        name="Accessibility Compliance Agent (US)",
        role="Produces accessibility checklists and DoD for 508 or WCAG 2.2 AA.",
        model=OpenAIChat(id=llm_model),
        tools=[ReasoningTools(add_instructions=True)],
        instructions=inject_pack_context(_base_instructions, active_pack_name),
        add_datetime_to_instructions=True,
    )
