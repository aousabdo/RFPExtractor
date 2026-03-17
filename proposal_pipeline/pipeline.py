"""Main proposal pipeline orchestrator — explicit sequential execution."""

from __future__ import annotations

import json
import logging
import os
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional

from .export import create_output_dir, save_intermediate, to_json, to_markdown, to_docx
from .models import CompanyProfile, PastPerformanceEntry, PipelineContext, ProposalPackage
from .openai_helpers import get_client, reset_usage_tracker, get_usage_tracker
from .steps.s1_analyze_rfp import analyze_rfp, rfp_analysis_from_existing
from .steps.s2_generate_outline import generate_outline
from .steps.s3_compliance_matrix import build_compliance_matrix
from .steps.s4_tech_research import research_technologies
from .steps.s5_write_sections import write_all_sections
from .steps.s6_review_polish import review_and_polish
from .steps.s6b_compress import compress_to_page_limit
from .steps.s7_score_proposal import score_and_rewrite

logger = logging.getLogger(__name__)

# Default location for company-specific data files
_COMPANY_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "company_data")


def load_company_data(company_data_dir: str = _COMPANY_DATA_DIR) -> PipelineContext:
    """Load company data files from disk and return a populated PipelineContext.

    Looks for these files in the given directory:
      - company_profile.json  → CompanyProfile
      - past_performance.json → List[PastPerformanceEntry]
      - win_themes.json       → List[str]
      - style_guide.txt       → str

    Missing files are silently skipped — each field stays at its default.
    """
    ctx = PipelineContext()

    profile_path = os.path.join(company_data_dir, "company_profile.json")
    if os.path.isfile(profile_path):
        with open(profile_path) as f:
            ctx.company_profile = CompanyProfile(**json.load(f))
        logger.info("Loaded company profile from %s", profile_path)

    pp_path = os.path.join(company_data_dir, "past_performance.json")
    if os.path.isfile(pp_path):
        with open(pp_path) as f:
            ctx.past_performance = [PastPerformanceEntry(**e) for e in json.load(f)]
        logger.info("Loaded %d past performance entries from %s", len(ctx.past_performance), pp_path)

    themes_path = os.path.join(company_data_dir, "win_themes.json")
    if os.path.isfile(themes_path):
        with open(themes_path) as f:
            ctx.win_themes = json.load(f)
        logger.info("Loaded %d win themes from %s", len(ctx.win_themes), themes_path)

    guide_path = os.path.join(company_data_dir, "style_guide.txt")
    if os.path.isfile(guide_path):
        with open(guide_path) as f:
            ctx.company_style_guide = f.read()
        logger.info("Loaded style guide from %s", guide_path)

    return ctx


class ProposalPipeline:
    """Sequential proposal generation pipeline using direct OpenAI SDK calls.

    Each step runs to completion, validates its output, and passes results
    to the next step. Progress is reported via an optional callback.

    Intermediate artifacts are saved to disk after each step so nothing
    is lost if the pipeline fails midway.

    Usage:
        pipeline = ProposalPipeline(api_key="sk-...", model="gpt-5")
        package = pipeline.run(
            rfp_text="Full RFP document text...",
            source_files=["path/to/sow.pdf", "path/to/rfq.pdf"],
        )
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-5",
        writing_model: str | None = None,
        progress_callback: Optional[Callable[[str, float], None]] = None,
        context: PipelineContext | None = None,
        output_dir: str | None = None,
    ):
        self.client = get_client(api_key)
        self.model = model  # Used for analysis, outline, compliance, tech research, scoring
        self.writing_model = writing_model or model  # Used for writing, polishing, compressing
        self.progress_callback = progress_callback or (lambda msg, pct: None)
        self._output_dir = output_dir  # Set later if not provided

        if self.writing_model != self.model:
            logger.info(
                "Using split model strategy: %s for analysis/scoring, %s for writing/polish/compress",
                self.model,
                self.writing_model,
            )

        # Auto-load company data from company_data/ if no context provided
        if context is not None:
            self.context = context
        elif os.path.isdir(_COMPANY_DATA_DIR):
            logger.info("Auto-loading company data from %s", _COMPANY_DATA_DIR)
            self.context = load_company_data()
        else:
            self.context = None

    @property
    def output_dir(self) -> str | None:
        return self._output_dir

    def run(
        self,
        rfp_text: str | None = None,
        existing_analysis: dict | None = None,
        source_files: List[str] | None = None,
    ) -> ProposalPackage:
        """Execute the full 7-step proposal generation pipeline.

        Args:
            rfp_text: Raw RFP document text. Required if existing_analysis not provided.
            existing_analysis: Pre-extracted RFP analysis dict (from process_rfp.py).
                If provided, Step 1 is skipped and this data is used directly.
            source_files: Optional list of file paths (PDFs, docs, etc.) to copy
                into the output directory for traceability.

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
        run_timestamp = datetime.now().isoformat()
        usage_tracker = reset_usage_tracker()

        # ── Step 1: Analyze RFP ──
        self.progress_callback("Analyzing RFP...", 0.05)
        if existing_analysis:
            logger.info("Using pre-extracted RFP analysis")
            rfp = rfp_analysis_from_existing(existing_analysis)
        else:
            rfp = analyze_rfp(self.client, rfp_text, self.model)
        self.progress_callback("RFP analysis complete", 0.10)

        # Create output directory from RFP customer name
        if not self._output_dir:
            self._output_dir = create_output_dir(rfp_name=rfp.customer)
        else:
            os.makedirs(self._output_dir, exist_ok=True)

        # ── Save inputs for traceability ──
        self._save_inputs(rfp_text, source_files)

        save_intermediate(rfp, "step1_rfp_analysis.json", self._output_dir)

        # ── Step 2: Generate Outline ──
        self.progress_callback("Generating proposal outline...", 0.12)
        outline = generate_outline(
            self.client, rfp, self.model, context=self.context
        )
        self.progress_callback(
            f"Outline complete: {len(outline.sections)} sections", 0.18
        )
        save_intermediate(outline, "step2_outline.json", self._output_dir)

        # ── Step 3: Compliance Matrix ──
        self.progress_callback("Building compliance matrix...", 0.20)
        compliance = build_compliance_matrix(
            self.client, rfp, outline, self.model
        )
        self.progress_callback(
            f"Compliance matrix: {compliance.coverage_percentage:.0f}% coverage",
            0.28,
        )
        save_intermediate(compliance, "step3_compliance_matrix.json", self._output_dir)

        # ── Step 4: Technology Research ──
        self.progress_callback("Researching technologies...", 0.29)
        tech_research = research_technologies(self.client, rfp, self.model)
        self.progress_callback(
            f"Tech research: {len(tech_research)} areas", 0.32
        )
        save_intermediate(tech_research, "step4_tech_research.json", self._output_dir)

        # ── Step 5: Write Sections (bulk of the work — uses writing_model) ──
        sections = write_all_sections(
            client=self.client,
            rfp=rfp,
            outline=outline,
            compliance=compliance,
            tech_research=tech_research,
            model=self.writing_model,
            context=self.context,
            progress_callback=self.progress_callback,
        )
        self.progress_callback("All sections drafted", 0.82)
        save_intermediate(sections, "step5_sections_draft.json", self._output_dir)

        # ── Step 6: Review and Polish (uses writing_model) ──
        self.progress_callback("Reviewing and polishing...", 0.83)
        sections = review_and_polish(
            client=self.client,
            sections=sections,
            model=self.writing_model,
            context=self.context,
            progress_callback=self.progress_callback,
        )
        self.progress_callback("Review complete", 0.88)
        save_intermediate(sections, "step6_sections_polished.json", self._output_dir)

        # ── Save FULL version (always, before compression) ──
        full_words = sum(s.word_count for s in sections)
        self.progress_callback(
            f"Saving full version ({full_words:,} words)...", 0.89
        )
        full_package = ProposalPackage(
            rfp_analysis=rfp,
            outline=outline,
            compliance_matrix=compliance,
            sections=sections,
            scores=[],
            overall_score=0.0,
            generation_metadata={"model": self.model, "writing_model": self.writing_model},
        )
        md_full = os.path.join(self._output_dir, "proposal_full.md")
        with open(md_full, "w") as f:
            f.write(to_markdown(full_package))
        logger.info("Saved full proposal (%d words) to %s", full_words, md_full)

        docx_full = os.path.join(self._output_dir, "proposal_full.docx")
        to_docx(full_package, docx_full)

        # ── Step 7: Score and Rewrite Loop (uses base model) ──
        self.progress_callback("Scoring proposal...", 0.90)
        sections, scores, overall_score = score_and_rewrite(
            client=self.client,
            sections=sections,
            rfp=rfp,
            compliance=compliance,
            model=self.model,
        )
        self.progress_callback(
            f"Scoring complete: {overall_score:.0f}/100", 0.92
        )
        save_intermediate(scores, "step7_scores.json", self._output_dir)

        # ── Step 6b: Compress to page limit (if applicable, uses writing_model) ──
        if rfp.page_limit > 0:
            total_word_budget = rfp.page_limit * 500
            current_words = sum(s.word_count for s in sections)
            if current_words > total_word_budget:
                self.progress_callback(
                    f"Compressing to {rfp.page_limit}-page limit "
                    f"({current_words:,} → {total_word_budget:,} words)...",
                    0.93,
                )
                sections = compress_to_page_limit(
                    client=self.client,
                    sections=sections,
                    scores=scores,
                    total_word_budget=total_word_budget,
                    model=self.writing_model,
                    progress_callback=self.progress_callback,
                )
                save_intermediate(
                    sections, "step6b_sections_compressed.json", self._output_dir
                )
                self.progress_callback("Compression complete", 0.97)
            else:
                logger.info(
                    "Proposal within page limit (%d words ≤ %d budget), skipping compression",
                    current_words,
                    total_word_budget,
                )

        # ── Assemble Package ──
        elapsed = time.time() - start_time
        usage = get_usage_tracker()
        source_file_names = [
            os.path.basename(f) for f in (source_files or [])
        ]
        metadata = {
            "model": self.model,
            "writing_model": self.writing_model,
            "total_sections": len(sections),
            "total_words": sum(s.word_count for s in sections),
            "full_version_words": full_words,
            "page_limit": rfp.page_limit,
            "elapsed_seconds": round(elapsed, 1),
            "output_dir": self._output_dir,
            "timestamp": run_timestamp,
            "source_files": source_file_names,
            "rfp_text_length": len(rfp_text) if rfp_text else 0,
            "cost": usage.summary(),
        }

        package = ProposalPackage(
            rfp_analysis=rfp,
            outline=outline,
            compliance_matrix=compliance,
            sections=sections,
            scores=scores,
            overall_score=overall_score,
            generation_metadata=metadata,
        )

        # ── Save final (compressed if applicable) outputs ──
        md_path = os.path.join(self._output_dir, "proposal.md")
        with open(md_path, "w") as f:
            f.write(to_markdown(package))
        logger.info("Saved proposal.md to %s", md_path)

        docx_path = os.path.join(self._output_dir, "proposal.docx")
        to_docx(package, docx_path)

        json_path = os.path.join(self._output_dir, "proposal.json")
        with open(json_path, "w") as f:
            f.write(to_json(package))
        logger.info("Saved proposal.json to %s", json_path)

        # ── Save run manifest ──
        self._save_manifest(metadata, overall_score, sections, scores)

        self.progress_callback(
            f"Proposal complete! ({usage.total_calls} API calls, ~${usage.estimated_cost_usd:.2f})",
            1.0,
        )
        logger.info(
            "Pipeline complete: %d sections, %d words, score %.0f/100, "
            "%.0fs, %s → %s",
            len(sections),
            sum(s.word_count for s in sections),
            overall_score,
            elapsed,
            str(usage),
            self._output_dir,
        )
        return package

    def _save_inputs(
        self,
        rfp_text: str | None,
        source_files: List[str] | None,
    ) -> None:
        """Save input documents and extracted text to the output directory."""
        inputs_dir = os.path.join(self._output_dir, "inputs")
        os.makedirs(inputs_dir, exist_ok=True)

        # Save raw extracted text
        if rfp_text:
            text_path = os.path.join(inputs_dir, "rfp_extracted_text.txt")
            with open(text_path, "w") as f:
                f.write(rfp_text)
            logger.info("Saved extracted RFP text (%d chars) to %s", len(rfp_text), text_path)

        # Copy source files (PDFs, docs, etc.)
        if source_files:
            for src_path in source_files:
                src_path = str(src_path)
                if os.path.isfile(src_path):
                    dest = os.path.join(inputs_dir, os.path.basename(src_path))
                    shutil.copy2(src_path, dest)
                    logger.info("Copied input file: %s → %s", src_path, dest)
                else:
                    logger.warning("Source file not found, skipping: %s", src_path)

    def _save_manifest(
        self,
        metadata: dict,
        overall_score: float,
        sections: list,
        scores: list,
    ) -> None:
        """Save a human-readable run manifest summarizing the pipeline run."""
        manifest = {
            "run_info": {
                "timestamp": metadata.get("timestamp"),
                "model": metadata.get("model"),
                "elapsed_seconds": metadata.get("elapsed_seconds"),
                "output_dir": metadata.get("output_dir"),
            },
            "inputs": {
                "source_files": metadata.get("source_files", []),
                "rfp_text_length_chars": metadata.get("rfp_text_length", 0),
            },
            "results": {
                "total_sections": metadata.get("total_sections"),
                "total_words": metadata.get("total_words"),
                "overall_score": round(overall_score, 1),
                "sections": [
                    {
                        "number": s.number,
                        "title": s.title,
                        "word_count": s.word_count,
                    }
                    for s in sections
                ],
                "scores_summary": [
                    {
                        "section": f"{sc.section_number}. {sc.section_title}",
                        "score": sc.score,
                        "requires_rewrite": sc.requires_rewrite,
                    }
                    for sc in scores
                ],
            },
            "cost": metadata.get("cost", {}),
            "files_in_directory": sorted(
                f for f in os.listdir(self._output_dir)
                if not f.startswith(".")
            ),
        }

        manifest_path = os.path.join(self._output_dir, "manifest.json")
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2, default=str)
        logger.info("Saved run manifest to %s", manifest_path)
