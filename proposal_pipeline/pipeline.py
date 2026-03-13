"""Main proposal pipeline orchestrator — explicit sequential execution."""

from __future__ import annotations

import logging
import time
from typing import Callable, Optional

from .models import PipelineContext, ProposalPackage
from .openai_helpers import get_client
from .steps.s1_analyze_rfp import analyze_rfp, rfp_analysis_from_existing
from .steps.s2_generate_outline import generate_outline
from .steps.s3_compliance_matrix import build_compliance_matrix
from .steps.s4_tech_research import research_technologies
from .steps.s5_write_sections import write_all_sections
from .steps.s6_review_polish import review_and_polish
from .steps.s7_score_proposal import score_and_rewrite

logger = logging.getLogger(__name__)


class ProposalPipeline:
    """Sequential proposal generation pipeline using direct OpenAI SDK calls.

    Each step runs to completion, validates its output, and passes results
    to the next step. Progress is reported via an optional callback.

    Usage:
        pipeline = ProposalPipeline(api_key="sk-...", model="gpt-5")
        package = pipeline.run(rfp_text="Full RFP document text...")
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-5",
        progress_callback: Optional[Callable[[str, float], None]] = None,
        context: PipelineContext | None = None,
    ):
        self.client = get_client(api_key)
        self.model = model
        self.progress_callback = progress_callback or (lambda msg, pct: None)
        self.context = context

    def run(
        self,
        rfp_text: str | None = None,
        existing_analysis: dict | None = None,
    ) -> ProposalPackage:
        """Execute the full 7-step proposal generation pipeline.

        Args:
            rfp_text: Raw RFP document text. Required if existing_analysis not provided.
            existing_analysis: Pre-extracted RFP analysis dict (from process_rfp.py).
                If provided, Step 1 is skipped and this data is used directly.

        Returns:
            ProposalPackage with all generated content, scores, and metadata.

        Raises:
            ValueError: If neither rfp_text nor existing_analysis is provided.
        """
        if not rfp_text and not existing_analysis:
            raise ValueError(
                "Either rfp_text or existing_analysis must be provided"
            )

        start_time = time.time()

        # ── Step 1: Analyze RFP ──
        self.progress_callback("Analyzing RFP...", 0.05)
        if existing_analysis:
            logger.info("Using pre-extracted RFP analysis")
            rfp = rfp_analysis_from_existing(existing_analysis)
        else:
            rfp = analyze_rfp(self.client, rfp_text, self.model)
        self.progress_callback("RFP analysis complete", 0.10)

        # ── Step 2: Generate Outline ──
        self.progress_callback("Generating proposal outline...", 0.12)
        outline = generate_outline(
            self.client, rfp, self.model, context=self.context
        )
        self.progress_callback(
            f"Outline complete: {len(outline.sections)} sections", 0.18
        )

        # ── Step 3: Compliance Matrix ──
        self.progress_callback("Building compliance matrix...", 0.20)
        compliance = build_compliance_matrix(
            self.client, rfp, outline, self.model
        )
        self.progress_callback(
            f"Compliance matrix: {compliance.coverage_percentage:.0f}% coverage",
            0.28,
        )

        # ── Step 4: Technology Research ──
        self.progress_callback("Researching technologies...", 0.29)
        tech_research = research_technologies(self.client, rfp, self.model)
        self.progress_callback(
            f"Tech research: {len(tech_research)} areas", 0.32
        )

        # ── Step 5: Write Sections (bulk of the work) ──
        sections = write_all_sections(
            client=self.client,
            rfp=rfp,
            outline=outline,
            compliance=compliance,
            tech_research=tech_research,
            model=self.model,
            context=self.context,
            progress_callback=self.progress_callback,
        )
        self.progress_callback("All sections drafted", 0.85)

        # ── Step 6: Review and Polish ──
        self.progress_callback("Reviewing and polishing...", 0.87)
        sections = review_and_polish(
            client=self.client,
            sections=sections,
            model=self.model,
            context=self.context,
            progress_callback=self.progress_callback,
        )
        self.progress_callback("Review complete", 0.92)

        # ── Step 7: Score and Rewrite Loop ──
        self.progress_callback("Scoring proposal...", 0.93)
        sections, scores, overall_score = score_and_rewrite(
            client=self.client,
            sections=sections,
            rfp=rfp,
            compliance=compliance,
            model=self.model,
        )
        self.progress_callback(
            f"Scoring complete: {overall_score:.0f}/100", 0.98
        )

        # ── Assemble Package ──
        elapsed = time.time() - start_time
        package = ProposalPackage(
            rfp_analysis=rfp,
            outline=outline,
            compliance_matrix=compliance,
            sections=sections,
            scores=scores,
            overall_score=overall_score,
            generation_metadata={
                "model": self.model,
                "total_sections": len(sections),
                "total_words": sum(s.word_count for s in sections),
                "elapsed_seconds": round(elapsed, 1),
            },
        )

        self.progress_callback("Proposal complete!", 1.0)
        logger.info(
            "Pipeline complete: %d sections, %d total words, score %.0f/100, %.0fs",
            len(sections),
            sum(s.word_count for s in sections),
            overall_score,
            elapsed,
        )
        return package
