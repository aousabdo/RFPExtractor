# -*- coding: utf-8 -*-
"""
QA Gatekeeper (pack-aware, proposal-agnostic)
Validates last-mile readiness: artifacts present, coverage, citations, density, tone consistency, and unresolved gaps.
"""

import os, json
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agno.tools.reasoning import ReasoningTools
from policy_packs import inject_pack_context

# ---------- Schemas ----------

class QAFinding(BaseModel):
    severity: str  # Critical | Major | Minor | Info
    area: str      # Artifacts | Coverage | Citations | Density | Tone | RedTeam | Redaction | Consistency
    description: str
    fix: str
    evidence_anchor: Optional[str] = None

class QAInputs(BaseModel):
    active_pack_name: str
    final_draft_text: str
    compliance_crosswalk: Dict[str, Any]  # your existing crosswalk JSON
    artifact_presence: Dict[str, bool]    # e.g., {"StaffControlMatrix": True, "Accessibility": True, "SCRM_SOP": True, "VisualRoadmap": True, "PastPerfTable": True}
    section_lengths: Dict[str, int]       # word counts by section key
    section_targets: Dict[str, int]       # target words by section key
    citation_samples: List[str]           # lines/paragraphs containing refs to normalize/check
    unresolved_red_team: List[Dict[str, Any]]  # items from Compliance Red Team not yet closed

class QAReport(BaseModel):
    pass_fail: str  # PASS | FAIL
    score: int      # 0-100
    summary: str
    findings: List[QAFinding]
    dashboard: Dict[str, Any]  # { "Critical": n, "Major": n, "Minor": n, "Info": n }

# ---------- Agent ----------

llm_model = os.getenv("LLM_MODEL", "gpt-5")

_BASE_INSTRUCTIONS = [
    "ROLE: Pre-submission QA Gatekeeper for any US proposal (Federal or Commercial).",
    "TASK: Given the final draft, crosswalk, artifact presence, section lengths, citation samples, and unresolved red-team items:",
    "- Validate completeness & traceability: every crosswalk item maps to at least one section with evidence pointer OR an explicit N/A rationale.",
    "- Validate artifacts required by ACTIVE_POLICY_PACK are present (e.g., ATO roadmap vs. Commercial audit window, 508 vs. WCAG).",
    "- Normalize citation style (emit corrections), flag stale/ambiguous references.",
    "- Check section density: compare actual word counts vs targets; propose compressions or expansions.",
    "- Flag wording inconsistencies and any remaining 'REDACTED' placeholders.",
    "- Compile a scored report with PASS/FAIL, findings (Critical/Major/Minor/Info), and a summary.",
    "OUTPUT: JSON only -> { pass_fail, score, summary, findings[], dashboard }",
    "SCORING HEURISTIC: Start at 100; -15 per Critical, -7 per Major, -2 per Minor (floor 0); PASS requires 0 Critical and score≥85.",
]

def build_qa_gatekeeper(active_pack_name: str) -> Agent:
    return Agent(
        name="QA Gatekeeper (US, Pack-Aware)",
        role="Final automated checklist and quality gate for any US proposal.",
        model=OpenAIChat(id=llm_model),
        tools=[ReasoningTools(add_instructions=True)],
        instructions=inject_pack_context(_BASE_INSTRUCTIONS, active_pack_name),
        add_datetime_to_instructions=True,
    )

# ---------- Runner ----------

def run_qa_gatekeeper(agent: Agent, payload: QAInputs) -> QAReport:
    prompt = payload.model_dump()
    raw = agent.run("Return ONLY JSON.\n" + json.dumps(prompt, ensure_ascii=False)).content.strip()
    if "```" in raw:
        raw = raw.split("```")[-2] if "```json" in raw else raw.split("```")[-2]
    data = json.loads(raw)
    return QAReport.model_validate(data)
