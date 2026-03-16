from agno.team.team import Team
from agno.models.openai import OpenAIChat
from agno.tools.reasoning import ReasoningTools

from policy_packs import POLICY_PACKS, select_policy_pack
from .agents_domain_profiler import domain_profiler
from .agents_compliance_red_team import build_compliance_red_team
from .agents_controls_mapper import build_controls_mapper
from .agents_scrm_sbom import build_scrm_sbom_agent
from .agents_accessibility import build_accessibility_agent


def assemble_team_with_us_upgrades(
    llm_model: str,
    base_members: list,
    rfp_text_or_draft: str,
):
    """Assemble a pack-aware orchestration team layered on top of existing base members.

    Notes:
    - Avoids circular imports by NOT referencing symbols from agents.py directly.
    - Assumes `base_members` already includes your core pipeline agents (incl. scoring if desired).
    """
    # 1) Profile domain and select policy pack
    profile_raw = domain_profiler.run(rfp_text_or_draft).content
    import json
    try:
        profile = json.loads(profile_raw)
    except Exception:
        profile = {"domain": "US_COMMERCIAL", "frameworks": [], "flags": [], "open_questions": []}
    active_pack_name = select_policy_pack(profile)

    # 2) Build pack-aware agents
    compliance_red = build_compliance_red_team(active_pack_name)
    controls_mapper = build_controls_mapper(active_pack_name)
    scrm_sbom = build_scrm_sbom_agent(active_pack_name)
    accessibility = build_accessibility_agent(active_pack_name)

    # 3) Assemble the full team (reuse provided base order, then augment)
    members = [
        *base_members,  # analyzer → outline → compliance → tech → section writing → english → tone (→ scoring if provided)
        # Post-draft augmenters (pack-aware)
        controls_mapper,
        accessibility,
        scrm_sbom,
        compliance_red,
    ]

    team = Team(
        name=f"US-Orchestration ({active_pack_name})",
        mode="coordinate",
        model=OpenAIChat(id=llm_model),
        members=members,
        tools=[ReasoningTools(add_instructions=True)],
        instructions=[
            "Run the base pipeline to produce a full, harmonized draft.",
            "Then run Controls Mapper, Accessibility Agent, SCRM & SBOM Agent, and Compliance Red Team.",
            "Integrate their outputs back into Section Writing → English → Tone for a final pass.",
            "Finalize with the scoring agent if present in members. Deliver: (a) proposal, (b) Staff↔Control matrix, "
            "(c) Accessibility checklist + DoD snippet, (d) SCRM/SBOM SOP + Exec summary, "
            "(e) Compliance Red Team issue list with incorporated fixes, (f) final scoring.",
        ],
        markdown=True,
        show_members_responses=False,
        enable_agentic_context=True,
        add_datetime_to_instructions=True,
        success_criteria=(
            "Pack-aware deliverables present; no unresolved compliance gaps; "
            "accessibility and SCRM evidence specified; tone unified; submission-ready."
        ),
    )

    return team, active_pack_name, profile


