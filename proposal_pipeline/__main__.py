"""CLI entry point: python -m proposal_pipeline <rfp_pdf_or_txt> [--model MODEL]"""

import argparse
import logging
import sys
import time

import fitz  # PyMuPDF

from .pipeline import ProposalPipeline


def _extract_text(path: str) -> str:
    """Extract text from a PDF or read a plain text file."""
    if path.lower().endswith(".pdf"):
        doc = fitz.open(path)
        return "\n".join(page.get_text() for page in doc)
    with open(path) as f:
        return f.read()


def _progress(msg: str, pct: float) -> None:
    bar_len = 30
    filled = int(bar_len * pct)
    bar = "█" * filled + "░" * (bar_len - filled)
    print(f"\r  [{bar}] {pct:5.1%}  {msg:<60}", end="", flush=True)
    if pct >= 1.0:
        print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a proposal from an RFP/SOW document."
    )
    parser.add_argument("rfp_files", nargs="+", help="One or more RFP/SOW PDF or text files")
    parser.add_argument("--model", default="gpt-5", help="Base model for analysis/scoring (default: gpt-5)")
    parser.add_argument(
        "--writing-model", default=None,
        help="Model for writing/polishing/compressing (default: same as --model). "
             "Use gpt-5.4 for highest quality writing."
    )
    parser.add_argument("--output-dir", default=None, help="Custom output directory")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    )

    all_text_parts = []
    for f in args.rfp_files:
        print(f"📄 Reading: {f}")
        text = _extract_text(f)
        print(f"   Extracted {len(text):,} characters")
        all_text_parts.append(text)
    rfp_text = "\n\n---\n\n".join(all_text_parts)
    print(f"\n   Total: {len(rfp_text):,} characters from {len(args.rfp_files)} file(s)\n")

    pipeline = ProposalPipeline(
        model=args.model,
        writing_model=args.writing_model,
        progress_callback=_progress,
        output_dir=args.output_dir,
    )

    if args.writing_model and args.writing_model != args.model:
        print(f"🧠 Analysis/scoring: {args.model}")
        print(f"✍️  Writing/polish/compress: {args.writing_model}")
        print()

    start = time.time()
    result = pipeline.run(rfp_text=rfp_text, source_files=args.rfp_files)
    elapsed = time.time() - start

    minutes, seconds = divmod(int(elapsed), 60)
    print(f"\n✅ Done in {minutes}m {seconds}s")
    print(f"   Output: {pipeline.output_dir}")
    print(f"   Sections: {len(result.sections)}")
    print(f"   Score: {result.overall_score:.1f}/100")

    # Show word counts for both versions
    final_words = result.generation_metadata.get("total_words", 0)
    full_words = result.generation_metadata.get("full_version_words", 0)
    page_limit = result.generation_metadata.get("page_limit", 0)
    if full_words and full_words != final_words:
        print(f"   Full version: {full_words:,} words (proposal_full.docx)")
        print(f"   Compressed:   {final_words:,} words (proposal.docx)")
        if page_limit:
            est_pages = final_words / 500
            print(f"   Page limit:   {page_limit} pages (~{est_pages:.0f} estimated)")
    else:
        print(f"   Words: {final_words:,}")

    # Print cost if tracked
    from .openai_helpers import get_usage_tracker
    usage = get_usage_tracker()
    if usage.estimated_cost_usd > 0:
        print(f"   Cost: ${usage.estimated_cost_usd:.2f} ({usage.total_input_tokens:,} in / {usage.total_output_tokens:,} out)")

    print()


if __name__ == "__main__":
    main()
