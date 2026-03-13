"""Streamlit UI for the proposal generation tab."""

from __future__ import annotations

import io
import logging
import tempfile
from typing import Optional

import streamlit as st

from proposal_pipeline.models import ProposalPackage

logger = logging.getLogger(__name__)


def render_proposal_tab(rfp_data: dict):
    """Render the proposal generation tab in the Streamlit UI.

    Args:
        rfp_data: The current RFP analysis data dict from session state.
    """
    st.markdown("### Proposal Generator")
    st.markdown(
        "Generate a full, submission-ready proposal from the analyzed RFP. "
        "Each section is written individually with quality checks and scoring."
    )

    # ── Configuration ──
    col1, col2 = st.columns(2)
    with col1:
        model = st.selectbox(
            "Model",
            ["gpt-5", "gpt-5-mini"],
            index=0,
            help="gpt-5 produces higher quality. gpt-5-mini is faster and cheaper.",
        )
    with col2:
        st.info("Estimated time: 5-10 min for full proposal")

    # ── Generate Button ──
    if st.button(
        "Generate Full Proposal",
        type="primary",
        use_container_width=True,
        disabled=not rfp_data,
    ):
        _run_pipeline(rfp_data, model)

    # ── Display Results ──
    if "proposal_package" in st.session_state and st.session_state.proposal_package:
        _display_proposal(st.session_state.proposal_package)


def _run_pipeline(rfp_data: dict, model: str):
    """Run the proposal pipeline with progress indicators."""
    from proposal_pipeline.pipeline import ProposalPipeline

    progress_bar = st.progress(0)
    status_text = st.empty()

    def progress_callback(message: str, percent: float):
        progress_bar.progress(min(percent, 1.0))
        status_text.text(message)

    api_key = st.session_state.get("openai_api_key")
    if not api_key:
        api_key = st.session_state.get("api_key")
    if not api_key:
        st.error("Please configure your OpenAI API key in the sidebar.")
        return

    try:
        pipeline = ProposalPipeline(
            api_key=api_key,
            model=model,
            progress_callback=progress_callback,
        )
        package = pipeline.run(existing_analysis=rfp_data)
        st.session_state.proposal_package = package

        total_words = sum(s.word_count for s in package.sections)
        st.success(
            f"Proposal generated! {len(package.sections)} sections, "
            f"{total_words:,} words, score: {package.overall_score:.0f}/100"
        )
        st.rerun()

    except Exception as e:
        logger.exception("Pipeline error")
        st.error(f"Pipeline error: {str(e)}")
        progress_bar.empty()
        status_text.empty()


def _display_proposal(package: ProposalPackage):
    """Display the generated proposal with sub-tabs."""
    ptab1, ptab2, ptab3, ptab4 = st.tabs(
        ["Full Proposal", "Compliance Matrix", "Scores", "Export"]
    )

    with ptab1:
        _render_full_proposal(package)

    with ptab2:
        _render_compliance_matrix(package)

    with ptab3:
        _render_scores(package)

    with ptab4:
        _render_export(package)


def _render_full_proposal(package: ProposalPackage):
    """Render all proposal sections as expandable blocks."""
    total_words = sum(s.word_count for s in package.sections)
    st.markdown(
        f"**{len(package.sections)} sections** | "
        f"**{total_words:,} total words** | "
        f"**Score: {package.overall_score:.0f}/100**"
    )

    for section in package.sections:
        with st.expander(
            f"{section.number}. {section.title} ({section.word_count:,} words)",
            expanded=False,
        ):
            st.markdown(section.content)


def _render_compliance_matrix(package: ProposalPackage):
    """Render the compliance matrix as a table."""
    cm = package.compliance_matrix
    st.markdown(
        f"**Coverage: {cm.coverage_percentage:.0f}%** | "
        f"**Gaps: {cm.gap_count}** | "
        f"**Total Requirements: {len(cm.rows)}**"
    )

    if not cm.rows:
        st.info("No compliance data available.")
        return

    # Build table data
    table_data = []
    for row in cm.rows:
        status_icon = {"Full": "✅", "Partial": "⚠️", "Gap": "❌"}.get(
            row.compliance_status, "❓"
        )
        table_data.append(
            {
                "ID": row.requirement_id,
                "Requirement": row.requirement_description[:100],
                "Section": row.proposal_section,
                "Status": f"{status_icon} {row.compliance_status}",
            }
        )

    st.dataframe(table_data, use_container_width=True, hide_index=True)


def _render_scores(package: ProposalPackage):
    """Render section scores with color coding."""
    st.markdown(f"### Overall Score: {package.overall_score:.0f}/100")

    if not package.scores:
        st.info("No scoring data available.")
        return

    for score in package.scores:
        color = (
            "green" if score.score >= 80
            else "orange" if score.score >= 60
            else "red"
        )
        st.markdown(
            f"**{score.section_number}. {score.section_title}**: "
            f":{color}[{score.score}/100]"
        )

        col1, col2 = st.columns(2)
        with col1:
            if score.strengths:
                st.markdown("**Strengths:**")
                for s in score.strengths:
                    st.markdown(f"- {s}")
        with col2:
            if score.weaknesses:
                st.markdown("**Weaknesses:**")
                for w in score.weaknesses:
                    st.markdown(f"- {w}")

        if score.recommendations:
            with st.expander("Recommendations"):
                for r in score.recommendations:
                    st.markdown(f"- {r}")

        st.divider()


def _render_export(package: ProposalPackage):
    """Render export/download buttons."""
    from proposal_pipeline.export import to_docx, to_markdown

    st.markdown("### Download Proposal")

    col1, col2, col3 = st.columns(3)

    # Markdown export
    with col1:
        md_content = to_markdown(package)
        st.download_button(
            "Download Markdown",
            md_content,
            file_name="proposal.md",
            mime="text/markdown",
            use_container_width=True,
        )

    # JSON export
    with col2:
        json_content = package.model_dump_json(indent=2)
        st.download_button(
            "Download JSON",
            json_content,
            file_name="proposal.json",
            mime="application/json",
            use_container_width=True,
        )

    # Word export
    with col3:
        try:
            with tempfile.NamedTemporaryFile(
                suffix=".docx", delete=False
            ) as tmp:
                to_docx(package, tmp.name)
                with open(tmp.name, "rb") as f:
                    docx_bytes = f.read()

            st.download_button(
                "Download Word (.docx)",
                docx_bytes,
                file_name="proposal.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True,
            )
        except ImportError:
            st.warning("python-docx not installed. Install with: pip install python-docx")
        except Exception as e:
            st.error(f"Error generating Word doc: {e}")
