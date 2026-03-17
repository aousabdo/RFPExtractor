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
    parser.add_argument("--model", default="gpt-5", help="OpenAI model (default: gpt-5)")
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
        progress_callback=_progress,
        output_dir=args.output_dir,
    )

    start = time.time()
    result = pipeline.run(rfp_text=rfp_text, source_files=args.rfp_files)
    elapsed = time.time() - start

    minutes, seconds = divmod(int(elapsed), 60)
    print(f"\n✅ Done in {minutes}m {seconds}s")
    print(f"   Output: {pipeline.output_dir}")
    print(f"   Sections: {len(result.sections)}")
    print(f"   Score: {result.overall_score}/100")

    # Print cost if tracked
    from .openai_helpers import get_usage_tracker
    usage = get_usage_tracker()
    if usage.estimated_cost_usd > 0:
        print(f"   Cost: ${usage.estimated_cost_usd:.2f} ({usage.total_input_tokens:,} in / {usage.total_output_tokens:,} out)")

    print()


if __name__ == "__main__":
    main()
