# -*- coding: utf-8 -*-
"""
Past Performance Weaver (US, pack-aware)

- Inputs:
  • active policy pack (US_GOV | US_COMMERCIAL)
  • optional library of past-performance items (structured)
  • final draft section map (to place callouts)

- Outputs:
  • snippets_by_section: {section_key: [short vignette strings]}
  • vignette_table: markdown table summarizing metrics and relevance
  • redaction_warnings: list of any placeholders that must be replaced
  • sourcing: list of source ids / references for traceability

Behavior:
  - US_GOV tone mirrors CPARS (Quality, Schedule, Cost Control, Management, Small Business)
  - US_COMMERCIAL tone mirrors SLAs/KPIs (Availability, Latency, MTTR, Throughput, NPS)
  - No client names are invented. If none provided, uses REDACTED placeholders.
"""

import os
from typing import List, Optional, Dict, Any, Tuple
from pydantic import BaseModel, Field, validator

from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agno.tools.reasoning import ReasoningTools

from policy_packs import inject_pack_context

# -------------------------
# Schemas
# -------------------------

class PastPerfItem(BaseModel):
    """Single past performance record (anonymized-friendly)."""
    project_id: str = Field(..., description="Internal id or slug")
    client_type: str = Field(..., description="e.g., US_FED_CIVILIAN, US_FED_DEFENSE, US_COMMERCIAL")
    customer_name: Optional[str] = Field(None, description="Use 'REDACTED' or generic if sensitive")
    sector_keywords: List[str] = Field(default_factory=list, description="Domains: 'geospatial','ETL','ATO','508','SCRM'")
    period_start: Optional[str] = Field(None, description="YYYY-MM")
    period_end: Optional[str] = Field(None, description="YYYY-MM or 'present'")
    contract_type: Optional[str] = None  # BPA, IDIQ, T&M, FFP, etc.
    scope_summary: str = Field(..., description="2-3 lines describing what was delivered")
    tech_stack: List[str] = Field(default_factory=list)
    compliance: List[str] = Field(default_factory=list)  # e.g., NIST_800_53, FedRAMP, 508, ISO_27001, SOC2
    kpis: Dict[str, str] = Field(default_factory=dict, description="e.g., {'Availability':'99.98%','MTTR':'22m'}")
    cpars_style: Dict[str, str] = Field(default_factory=dict, description="Gov: Quality/Schedule/Cost/Management notes")
    outcomes: List[str] = Field(default_factory=list, description="Bullet outcomes (quantified where possible)")
    reference_id: Optional[str] = Field(None, description="Internal doc id / CPARS id / case-study id")

    @validator("customer_name", always=True)
    def redact_if_missing(cls, v):
        return v or "REDACTED"

class SectionPlacement(BaseModel):
    """Map proposal sections to topical tags so the agent knows where to weave vignettes."""
    section_key: str
    title: str
    tags: List[str]  # e.g., ["ETL","DBA","API","Geospatial","ATO","508","SCRM","ConMon"]

class PastPerfWeaverInput(BaseModel):
    active_pack_name: str
    draft_outline: List[SectionPlacement]
    library: List[PastPerfItem] = Field(default_factory=list)
    max_snippets_per_section: int = 2

class PastPerfWeaverOutput(BaseModel):
    snippets_by_section: Dict[str, List[str]]
    vignette_table: str
    redaction_warnings: List[str]
    sourcing: List[str]

# -------------------------
# Agent factory
# -------------------------

llm_model = os.getenv("LLM_MODEL", "gpt-5")

_BASE_INSTRUCTIONS = [
    # Guardrails
    "STRICT RULES:",
    "- Do NOT invent real client names or agencies. If a PastPerfItem lacks a name, use 'REDACTED' or a generic descriptor like 'US Federal Civilian Agency'.",
    "- Do NOT fabricate dates, awards, or certifications. Only use what is present in the library input.",
    "- Keep each vignette to 2–3 sentences; include 1–2 quantified metrics if provided (or mark metric as 'REDACTED' if absent).",
    "- Use the ACTIVE_POLICY_PACK to choose tone and emphasis.",
    "- When no library is provided, emit sanitized placeholders clearly marked as 'REDACTED' and add a redaction warning describing what to replace.",
    "",
    # Style by pack
    "STYLE:",
    "- If ACTIVE_POLICY_PACK.name == 'US_GOV': write in a CPARS-adjacent tone emphasizing Quality, Schedule, Cost Control, Management, and Mission Impact; reference ATO, ConMon, 508, SCRM if relevant.",
    "- If ACTIVE_POLICY_PACK.name == 'US_COMMERCIAL': write in a KPI/SLA tone emphasizing availability, latency, throughput, MTTR, release cadence, SOC 2/ISO posture, customer impact.",
    "- Always mirror key terminology from section tags (e.g., ETL, Oracle DBA, Spring Boot APIs, Geospatial, ATO, 508, SCRM, ConMon).",
    "",
    # Output contract
    "OUTPUT (JSON ONLY): { 'snippets_by_section': {section_key: [vignette, ...]}, 'vignette_table': '<markdown table>', 'redaction_warnings': [..], 'sourcing': [..] }",
    "The markdown table should have columns: Project | Client | Period | Relevance | Metrics/Outcomes | SourceRef",
    "Use short, high-signal phrasing; avoid confidential details.",
]

def build_past_performance_weaver(active_pack_name: str) -> Agent:
    return Agent(
        name="Past Performance Weaver (US, Pack-Aware)",
        role=("Selects and rewrites short past-performance vignettes; places them in the most relevant sections; "
              "outputs a vignette summary table; never fabricates client identities."),
        model=OpenAIChat(id=llm_model),
        tools=[ReasoningTools(add_instructions=True)],
        instructions=inject_pack_context(_BASE_INSTRUCTIONS, active_pack_name),
        add_datetime_to_instructions=True,
    )

# -------------------------
# Helper to run the agent
# -------------------------

def run_past_performance_weaver(agent: Agent, payload: PastPerfWeaverInput) -> PastPerfWeaverOutput:
    """
    Serializes inputs, runs the agent, parses JSON, validates with Pydantic.
    """
    import json
    prompt = {
        "ACTIVE_PACK_NAME": payload.active_pack_name,
        "DRAFT_OUTLINE": [sp.model_dump() for sp in payload.draft_outline],
        "LIBRARY": [pp.model_dump() for pp in payload.library],
        "MAX_SNIPPETS_PER_SECTION": payload.max_snippets_per_section,
    }
    raw = agent.run(
        "Return ONLY the JSON as specified. No prose.\n"
        + json.dumps(prompt, ensure_ascii=False, indent=2)
    ).content

    # Normalize common code-fence wrappers
    raw = raw.strip()
    if "```json" in raw:
        raw = raw.split("```json", 1)[-1].split("```", 1)[0].strip()
    elif "```" in raw:
        raw = raw.split("```", 1)[-1].split("```", 1)[0].strip()

    data = __safe_json_loads(raw)
    return PastPerfWeaverOutput.model_validate(data)

def __safe_json_loads(raw: str) -> Dict[str, Any]:
    import json
    try:
        return json.loads(raw)
    except Exception as e:
        # Give a clearer error with preview
        preview = raw[:500].replace("\n", " ")
        raise ValueError(f"PastPerformanceWeaver JSON parse failed: {e}; preview={preview}")
