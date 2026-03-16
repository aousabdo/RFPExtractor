# -*- coding: utf-8 -*-
"""
Evidence & Artifact Packager (pack-aware)
Curates a minimal proof kit and an insertion map. Templates are neutral and reusable.
"""

import os, json
from typing import List, Dict, Any
from pydantic import BaseModel, Field

from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agno.tools.reasoning import ReasoningTools
from policy_packs import inject_pack_context

class EvidenceInput(BaseModel):
    active_pack_name: str
    crosswalk: Dict[str, Any]
    claimed_capabilities: List[str]   # e.g., ["508","WCAG","NIST_800_53","ISO_27001","SBOM","VEX","ConMon","OpenAPI","DQ_Catalog"]
    existing_artifacts: Dict[str, bool]  # what you already have
    section_map: Dict[str, str]       # section_key -> section_title

class ArtifactItem(BaseModel):
    name: str
    required: bool
    status: str          # Present | Missing | Placeholder
    placement_hint: str  # where to reference/insert
    template_stub: str   # short template or outline
    evidence_tags: List[str]

class EvidencePack(BaseModel):
    artifacts: List[ArtifactItem]
    insertion_map: Dict[str, List[str]]  # section_key -> [artifact_names]
    gaps: List[str]                      # items to create before submission
    summary: str

llm_model = os.getenv("LLM_MODEL", "gpt-5")

_BASE_INSTRUCTIONS = [
    "ROLE: Compile a compact evidence/appendix bundle based on ACTIVE_POLICY_PACK and crosswalk.",
    "Always consider these canonical artifacts (toggle by pack): Staff↔Control Matrix, Accessibility (ACR/VPAT or WCAG checklist), SCRM & SBOM SOP, Visual Roadmap, Past Performance Table, API Lifecycle Policy, DQ Rule Catalog, Incident Response Summary, ConMon dashboard sample.",
    "For each artifact: set required=True/False from the pack and claims; mark status (Present/Missing/Placeholder) based on existing_artifacts; propose placement hints and short template stubs.",
    "OUTPUT JSON ONLY: {artifacts:[], insertion_map:{}, gaps:[], summary}",
    "Templates must be brief outlines, not full documents; use neutral language.",
]

def build_evidence_packager(active_pack_name: str) -> Agent:
    return Agent(
        name="Evidence & Artifact Packager (US, Pack-Aware)",
        role="Curates proof kit and insertion plan for any US proposal.",
        model=OpenAIChat(id=llm_model),
        tools=[ReasoningTools(add_instructions=True)],
        instructions=inject_pack_context(_BASE_INSTRUCTIONS, active_pack_name),
        add_datetime_to_instructions=True,
    )

def run_evidence_packager(agent: Agent, payload: EvidenceInput) -> EvidencePack:
    try:
        raw = agent.run("Return ONLY JSON.\n" + json.dumps(payload.model_dump(), ensure_ascii=False)).content.strip()
        if "```" in raw:
            raw = raw.split("```")[-2] if "```json" in raw else raw.split("```")[-2]
        data = json.loads(raw)
        
        # Validate and fix the data structure
        validated_data = {
            "artifacts": [],
            "insertion_map": data.get("insertion_map", {}),
            "gaps": [],
            "summary": ""
        }
        
        # Fix artifacts structure
        for artifact in data.get("artifacts", []):
            if isinstance(artifact, dict):
                validated_artifact = {
                    "name": artifact.get("name", "Unnamed artifact"),
                    "required": artifact.get("required", False),
                    "status": artifact.get("status", "Missing"),
                    "placement_hint": artifact.get("placement_hint", "To be determined"),
                    "template_stub": artifact.get("template_stub", ""),
                    "evidence_tags": artifact.get("evidence_tags", [])
                }
                # Ensure evidence_tags is a list of strings
                if not isinstance(validated_artifact["evidence_tags"], list):
                    validated_artifact["evidence_tags"] = []
                validated_data["artifacts"].append(validated_artifact)
        
        # Fix gaps structure - convert dicts to strings
        for gap in data.get("gaps", []):
            if isinstance(gap, dict):
                # Extract artifact name and details
                artifact_name = gap.get("artifact", "")
                details = gap.get("details", gap.get("description", str(gap)))
                formatted_gap = f"{artifact_name}: {details}" if artifact_name else details
                validated_data["gaps"].append(formatted_gap)
            else:
                validated_data["gaps"].append(str(gap))
        
        # Fix summary structure
        summary_data = data.get("summary", {})
        if isinstance(summary_data, dict):
            # Extract key information from the summary dict
            pack = summary_data.get("pack", "")
            alignment = summary_data.get("alignment", "")
            artifacts_count = len(validated_data["artifacts"])
            gaps_count = len(validated_data["gaps"])
            validated_data["summary"] = f"Evidence pack for {pack}: {artifacts_count} artifacts, {gaps_count} gaps. Alignment: {alignment}"
        else:
            validated_data["summary"] = str(summary_data) if summary_data else "Evidence packaging completed"
        
        return EvidencePack.model_validate(validated_data)
        
    except json.JSONDecodeError as e:
        print(f"⚠️  JSON decode error in evidence packager: {e}")
        return EvidencePack(
            artifacts=[],
            insertion_map={},
            gaps=[],
            summary="Evidence packaging failed due to JSON parsing error."
        )
    except Exception as e:
        print(f"⚠️  Evidence packager error: {e}")
        return EvidencePack(
            artifacts=[],
            insertion_map={},
            gaps=[],
            summary=f"Evidence packaging failed: {str(e)}"
        )
