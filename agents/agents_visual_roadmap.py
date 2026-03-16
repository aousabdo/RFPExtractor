# -*- coding: utf-8 -*-
"""
Executive Visual Roadmap (pack-aware)
Outputs a single-page program view: lanes and milestones vary by US_GOV (ATO) vs US_COMMERCIAL (audit cadence).
"""

import os, json
from typing import List, Dict, Any
from pydantic import BaseModel, Field

from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agno.tools.reasoning import ReasoningTools
from policy_packs import inject_pack_context

class RoadmapInput(BaseModel):
    active_pack_name: str
    key_dates: Dict[str, str]  # e.g., {"PoPStart":"2025-09-01","PoPEnd":"2026-08-31","ATO_Submit":"2025-08-01","ATO_Renew":"2026-06-01"} or commercial analogs
    lanes: List[str] = Field(default_factory=lambda: ["APIs","Data/Geospatial","Security/ATO_or_Audit","ConMon/Monitoring"])
    major_deliverables: List[str] = Field(default_factory=list)  # e.g., ["OpenAPI v1.0","ETL DQ Catalog","ACR v1","SBOM SOP"]
    callouts: List[str] = Field(default_factory=list)  # optional highlights

class RoadmapOutput(BaseModel):
    mermaid_gantt: str        # code fence block
    ascii_timeline: str       # fallback
    caption: str              # one paragraph summary
    lane_legend: Dict[str, str]

llm_model = os.getenv("LLM_MODEL", "gpt-5")

_BASE_INSTRUCTIONS = [
    "ROLE: Create a single-page roadmap from key dates and deliverables.",
    "US_GOV: Include ATO submission/renewal, control-evidence sprints, independent validator gate, monthly ConMon.",
    "US_COMMERCIAL: Include audit window(s), security control checks, quarterly review cadence, monthly monitoring.",
    "OUTPUT JSON ONLY: { mermaid_gantt:'```mermaid\\n...\\n```', ascii_timeline:'...', caption:'...', lane_legend:{lane:desc} }",
    "Mermaid format: gantt, dateFormat YYYY-MM-DD, title from PoP and pack, sections per lane.",
    "Caption: ≤120 words; include 2–3 milestone highlights.",
]

def build_visual_roadmap_agent(active_pack_name: str) -> Agent:
    return Agent(
        name="Executive Visual Roadmap (US, Pack-Aware)",
        role="Generates a one-page program view aligned to the active pack.",
        model=OpenAIChat(id=llm_model),
        tools=[ReasoningTools(add_instructions=True)],
        instructions=inject_pack_context(_BASE_INSTRUCTIONS, active_pack_name),
        add_datetime_to_instructions=True,
    )

def run_visual_roadmap(agent: Agent, payload: RoadmapInput) -> RoadmapOutput:
    raw = agent.run("Return ONLY JSON.\n" + json.dumps(payload.model_dump(), ensure_ascii=False)).content.strip()
    if "```" in raw:
        raw = raw.split("```")[-2] if "```json" in raw else raw.split("```")[-2]
    data = json.loads(raw)
    return RoadmapOutput.model_validate(data)
