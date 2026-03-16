# RFP Extractor & Proposal Generator

An AI-powered tool that analyzes RFP (Request for Proposal) documents and generates comprehensive, submission-ready proposals using OpenAI's language models.

## What It Does

1. **Analyzes RFPs** — Upload a PDF, extract structured data (customer, scope, requirements, dates, tasks)
2. **Generates Proposals** — A 7-step pipeline writes a full proposal with quality gates and scoring
3. **Exports Results** — Markdown, Word (.docx), and JSON output with compliance matrix and scoring

## Project Structure

```
RFPExtractor/
├── enterprise_rfp_assistant.py     # Main Streamlit app entry point
├── process_rfp.py                  # RFP text extraction & analysis
├── rfp_filter.py                   # RFP content filtering
├── requirements.txt
│
├── rfp_app/                        # Streamlit UI modules
│   ├── ui.py                       # Main analysis UI (tabs, charts, export)
│   ├── proposal_ui.py              # Proposal generation UI
│   ├── chat.py                     # AI chat interface
│   ├── pdf_processing.py           # PDF upload & extraction
│   ├── storage.py                  # Document storage
│   └── logo_utils.py               # Logo loading
│
├── proposal_pipeline/              # Proposal generation engine
│   ├── pipeline.py                 # 7-step sequential orchestrator
│   ├── models.py                   # Pydantic data models
│   ├── export.py                   # Markdown/Word/JSON export + timestamped dirs
│   ├── quality_gates.py            # Per-section quality validation
│   ├── openai_helpers.py           # OpenAI SDK wrappers (structured output, retry)
│   └── steps/
│       ├── s1_analyze_rfp.py       # Extract customer, scope, requirements
│       ├── s2_generate_outline.py  # Section headings + word count targets
│       ├── s3_compliance_matrix.py # Map requirements → proposal sections
│       ├── s4_tech_research.py     # Technology recommendations
│       ├── s5_write_sections.py    # Write each section with quality gates
│       ├── s6_review_polish.py     # Grammar, clarity, tone pass
│       └── s7_score_proposal.py    # Score 0-100, rewrite weak sections
│
├── agents/                         # Specialist review agents
│   ├── agents_accessibility.py     # Section 508 / WCAG compliance
│   ├── agents_compliance_red_team.py
│   ├── agents_controls_mapper.py   # NIST 800-53 controls mapping
│   ├── agents_domain_profiler.py
│   ├── agents_evidence_packager.py
│   ├── agents_factcheck_verifier.py
│   ├── agents_past_performance.py
│   ├── agents_qa_gatekeeper.py
│   ├── agents_scrm_sbom.py        # Supply chain / SBOM
│   ├── agents_visual_roadmap.py
│   └── orchestration_integration.py
│
├── tests/                          # Test suite
│   ├── test_pdf_processing.py
│   ├── test_rfp_filter.py
│   └── test_proposal_pipeline/
│       ├── test_models.py
│       ├── test_openai_helpers.py
│       └── test_quality_gates.py
│
├── docker/                         # Docker deployment
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── nginx.conf
│
├── assets/                         # Static files
│   └── rfp_analyzer_logo.svg
│
└── proposals/                      # (gitignored) Generated output
    └── <customer>_YYYY-MM-DD_HHMMSS/
        ├── proposal.md
        ├── proposal.docx
        ├── proposal.json
        ├── step1_rfp_analysis.json
        ├── step2_outline.json
        ├── step3_compliance_matrix.json
        ├── step4_tech_research.json
        ├── step5_sections_draft.json
        ├── step6_sections_polished.json
        └── step7_scores.json
```

## Getting Started

### Prerequisites

- Python 3.9+
- OpenAI API key (with access to gpt-5 or gpt-4o)

### Installation

```bash
git clone https://github.com/aousabdo/RFPExtractor.git
cd RFPExtractor
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Configuration

Create a `.env` file in the project root:

```
OPENAI_API_KEY=sk-your-key-here
```

### Running the Streamlit App

```bash
streamlit run enterprise_rfp_assistant.py
```

Then:
1. Upload an RFP PDF
2. Review extracted data in the **Analysis** tabs
3. Go to the **Proposal** tab → click **Generate Full Proposal**
4. Export as Markdown, Word, or JSON

### Running the Pipeline from CLI

```python
import fitz
from proposal_pipeline import ProposalPipeline

# Extract text from RFP PDF
doc = fitz.open("your_rfp.pdf")
text = "".join(page.get_text() for page in doc)

# Generate proposal
pipeline = ProposalPipeline(
    model="gpt-5",
    progress_callback=lambda msg, pct: print(f"[{pct:.0%}] {msg}")
)
package = pipeline.run(rfp_text=text)

print(f"Done! {len(package.sections)} sections, "
      f"{sum(s.word_count for s in package.sections):,} words, "
      f"score: {package.overall_score:.0f}/100")
print(f"Output: {pipeline.output_dir}")
```

## Proposal Pipeline

The pipeline generates proposals through 7 sequential steps:

| Step | What It Does | Output |
|------|-------------|--------|
| 1. Analyze RFP | Extract customer, scope, tasks, requirements, dates | `RFPAnalysis` |
| 2. Generate Outline | Create section headings with guidance and word targets | `ProposalOutline` |
| 3. Compliance Matrix | Map every requirement to a proposal section | `ComplianceMatrix` |
| 4. Tech Research | Research relevant technologies and recommendations | Tech summaries |
| 5. Write Sections | Write each section individually with quality gates | `ProposalSection[]` |
| 6. Review & Polish | Grammar, clarity, and tone harmonization pass | Polished sections |
| 7. Score & Rewrite | Score 0-100, rewrite sections below 70 | Final sections + scores |

### Quality Gates

Each section must pass before proceeding:
- **Word count** — meets target (±30%)
- **No placeholders** — no `[TBD]`, `[INSERT]`, `lorem ipsum`, etc.
- **Requirement coverage** — ≥70% of mapped requirements explicitly addressed
- Sections that fail get up to 2 automatic retries with specific feedback

### Output

Every run creates a timestamped directory under `proposals/`:
- **proposal.md** — Full proposal in Markdown
- **proposal.docx** — Formatted Word document with title page, TOC, compliance matrix
- **proposal.json** — Complete data package (sections, scores, metadata)
- **step1-7 JSON files** — Intermediate artifacts from each pipeline step

## Running Tests

```bash
pip install pytest
python -m pytest tests/ -v
```

## Docker Deployment

```bash
cd docker
docker-compose up -d
```

## Security

- API keys are loaded from `.env` (gitignored)
- No credentials are logged or committed
- Client RFP documents are gitignored (`*.pdf`)
- Generated proposals are gitignored (`proposals/`)
- Old code is archived locally in `_archive/` (gitignored)

## License

MIT License — see LICENSE file for details.
