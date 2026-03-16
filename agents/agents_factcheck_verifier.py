# -*- coding: utf-8 -*-
"""
Fact-Check & Citation Verifier (pack-aware)
Normalizes references and terminology; proposes precise redlines. No web calls; checks internal consistency/glossary.
"""

import os, json
from typing import List, Dict, Any
from pydantic import BaseModel, Field

from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agno.tools.reasoning import ReasoningTools
from policy_packs import inject_pack_context

class Glossary(BaseModel):
    # Canonical names per pack (examples; extend as needed)
    frameworks: Dict[str, List[str]] = Field(default_factory=dict)   # {"NIST_800_53": ["NIST SP 800-53","800-53","NIST controls"], ...}
    citations_format: str = "Ref: {section} p.{page}"
    banned_terms: List[str] = Field(default_factory=lambda: ["best-in-class", "world-class", "cutting-edge"])
    preferred_terms: Dict[str, str] = Field(default_factory=lambda: {"ROA": "Resource-Oriented Architecture", "VPAT": "Accessibility Conformance Report (ACR/VPAT)"})

class FactCheckInput(BaseModel):
    active_pack_name: str
    final_draft_text: str
    crosswalk: Dict[str, Any]
    citation_examples: List[str]
    glossary: Glossary

class Redline(BaseModel):
    location_hint: str
    current_text: str
    proposed_text: str
    reason: str

class FactCheckReport(BaseModel):
    normalized_citations: List[str]
    redlines: List[Redline]
    unknown_refs: List[str]
    terminology_notes: List[str]
    summary: str

llm_model = os.getenv("LLM_MODEL", "gpt-5")

_BASE_INSTRUCTIONS = [
    "ROLE: Verify and normalize references/citations and terminology.",
    "Use the pack-aware glossary to standardize framework names and preferred terms; flag banned terms.",
    "Normalize citation style to glossary.citations_format wherever possible.",
    "Identify unknown/ambiguous references, and propose exact redlines with minimal edits.",
    "OUTPUT JSON ONLY: {normalized_citations:[], redlines:[], unknown_refs:[], terminology_notes:[], summary}",
]

def build_factcheck_verifier(active_pack_name: str) -> Agent:
    return Agent(
        name="Fact-Check & Citation Verifier (US, Pack-Aware)",
        role="Normalizes references and terminology; proposes redlines for clarity and consistency.",
        model=OpenAIChat(id=llm_model),
        tools=[ReasoningTools(add_instructions=True)],
        instructions=inject_pack_context(_BASE_INSTRUCTIONS, active_pack_name),
        add_datetime_to_instructions=True,
    )

def run_factcheck_verifier(agent: Agent, payload: FactCheckInput) -> FactCheckReport:
    try:
        raw = agent.run("Return ONLY JSON.\n" + json.dumps(payload.model_dump(), ensure_ascii=False)).content.strip()
        if "```" in raw:
            raw = raw.split("```")[-2] if "```json" in raw else raw.split("```")[-2]
        data = json.loads(raw)
        
        # Validate and fix the data structure
        validated_data = {
            "normalized_citations": data.get("normalized_citations", []),
            "redlines": [],
            "unknown_refs": [],
            "terminology_notes": data.get("terminology_notes", []),
            "summary": data.get("summary", "Fact-check completed with validation issues.")
        }
        
        # Fix redlines structure
        for redline in data.get("redlines", []):
            if isinstance(redline, dict):
                validated_redline = {
                    "location_hint": redline.get("location", redline.get("location_hint", "Unknown location")),
                    "current_text": redline.get("current_text", ""),
                    "proposed_text": redline.get("proposed_text", ""),
                    "reason": redline.get("reason", "Validation issue")
                }
                validated_data["redlines"].append(validated_redline)
        
        # Fix unknown_refs structure
        for ref in data.get("unknown_refs", []):
            if isinstance(ref, dict):
                validated_data["unknown_refs"].append(ref.get("reference", str(ref)))
            else:
                validated_data["unknown_refs"].append(str(ref))
        
        # Fix normalized_citations structure - convert dicts to strings
        for citation in data.get("normalized_citations", []):
            if isinstance(citation, dict):
                # Extract the original text or format it nicely
                original = citation.get("original", str(citation))
                validated_data["normalized_citations"].append(original)
            else:
                validated_data["normalized_citations"].append(str(citation))
        
        # Fix terminology_notes structure - convert dicts to strings
        for note in data.get("terminology_notes", []):
            if isinstance(note, dict):
                # Extract the term and note content
                term = note.get("term", "")
                content = note.get("note", note.get("content", str(note)))
                formatted_note = f"{term}: {content}" if term else content
                validated_data["terminology_notes"].append(formatted_note)
            else:
                validated_data["terminology_notes"].append(str(note))
        
        return FactCheckReport.model_validate(validated_data)
        
    except json.JSONDecodeError as e:
        print(f"⚠️  JSON decode error in fact-check: {e}")
        return FactCheckReport(
            normalized_citations=[],
            redlines=[],
            unknown_refs=[],
            terminology_notes=["JSON parsing failed"],
            summary="Fact-check failed due to JSON parsing error."
        )
    except Exception as e:
        print(f"⚠️  Fact-check error: {e}")
        return FactCheckReport(
            normalized_citations=[],
            redlines=[],
            unknown_refs=[],
            terminology_notes=[f"Error: {str(e)}"],
            summary="Fact-check failed due to validation error."
        )
