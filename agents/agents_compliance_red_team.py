# === agents_compliance_red_team.py ===
from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agno.tools.reasoning import ReasoningTools
from policy_packs import inject_pack_context

import dotenv, os

llm_model = os.getenv("LLM_MODEL", "gpt-5")

_base_instructions = [
    "You receive: (1) the buyer's requirements (outline or structured extract), "
    "(2) the current proposal draft (full or sections), and (3) the ACTIVE_POLICY_PACK context.",
    "Compare draft vs requirements. Identify: unmapped requirements, conflicting or ambiguous terms "
    "(e.g., PoP mismatch, eligibility rules), missing artifacts (evidence), and vague commitments.",
    "Output ONLY JSON: a list of issues, where each item is "
    "{section, finding, impact, fix, owner, artifact, priority}. No prose.",
    "Be surgical in 'fix': provide replacement text or exact insertion points (quote the sentence to replace).",
    "Prioritize issues that would cause evaluator downgrades or compliance rejection.",
]

def build_compliance_red_team(active_pack_name: str) -> Agent:
    return Agent(
        name="Compliance Red Team (US)",
        role="Adversarial gap hunter against requirements and policy pack.",
        model=OpenAIChat(id=llm_model),
        tools=[ReasoningTools(add_instructions=True)],
        instructions=inject_pack_context(_base_instructions, active_pack_name),
        add_datetime_to_instructions=True,
    )
