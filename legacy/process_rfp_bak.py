import os
import json
import fitz  # PyMuPDF
from openai import OpenAI
from dotenv import load_dotenv
from typing import List, Dict, Any

# Load environment variables
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

class RFPProcessor:
    def __init__(self):
        self.system_prompt = """You are a expert government contracting specialist with deep 
        expertise in analyzing RFPs. Extract structured information from Request for Proposals 
        with extreme accuracy. Pay special attention to distributed information across multiple 
        sections and pages. Distinguish between actual tasks (work to be performed) and 
        requirements (rules/standards to follow). Tasks should be active work items, not passive requirements."""
        
        self.extraction_prompt = """Analyze this RFP section and extract:
        - Customer (primary agency/department)
        - Clear scope of work (1-2 sentences)
        - Major tasks (active work activities to be performed, with titles, descriptions, and page numbers)
          Note: Only include actual work activities that require active effort, not compliance requirements
        - Key requirements (rules, standards, compliance requirements with page numbers)
          Categories: 
          - Security (security controls, clearances, etc.)
          - Compliance (regulations, standards, policies)
          - IT Standards (technical specifications, platforms)
          - Personnel (qualifications, certifications, experience)
        - Key dates (submission, performance period)
        
        Format as JSON with this exact structure:
        {
            "customer": "string",
            "scope": {"text": "string", "page": number},
            "tasks": [{"title": "string", "description": "string", "page": number}],
            "requirements": [{"category": "string", "description": "string", "page": number}],
            "dates": [{"event": "string", "date": "string", "page": number}]
        }
        
        Guidelines:
        - Tasks must be active work activities (e.g., "Develop system", not "Must comply with")
        - Requirements should be rules/standards that must be followed
        - Group similar requirements under the same category
        - Normalize date descriptions (e.g., 'after contract award' vs 'after the date of award')
        - Avoid duplicate information with slight wording variations"""

    def extract_text(self, pdf_path: str) -> List[Dict]:
        """Extract text with metadata from PDF"""
        doc = fitz.open(pdf_path)
        pages = []
        for page_num, page in enumerate(doc):
            text = page.get_text()
            pages.append({
                "page": page_num + 1,
                "text": text,
                "blocks": [{"bbox": block[:4], "text": block[4]} for block in page.get_text("blocks")]
            })
        return pages

    def chunk_content(self, pages: List[Dict], max_tokens: int = 6000) -> List[Dict]:
        """Create context-aware chunks respecting section boundaries"""
        chunks = []
        current_chunk = []
        current_token_count = 0
        
        for page in pages:
            page_text = f"Page {page['page']}:\n{page['text']}"
            token_estimate = len(page_text) // 4  # Approximate token count
            
            if current_token_count + token_estimate > max_tokens:
                chunks.append({"pages": current_chunk})
                current_chunk = []
                current_token_count = 0
                
            current_chunk.append(page)
            current_token_count += token_estimate
            
        if current_chunk:
            chunks.append({"pages": current_chunk})
            
        return chunks

    def process_chunk(self, chunk: Dict) -> Dict:
        """Process a chunk through GPT-4 with validation"""
        combined_text = "\n".join([f"Page {p['page']}:\n{p['text']}" for p in chunk["pages"]])
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": f"{self.extraction_prompt}\n\n{combined_text}"}
            ],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        
        try:
            return json.loads(response.choices[0].message.content)
        except json.JSONDecodeError:
            return {"error": "Invalid JSON response"}

    def aggregate_results(self, results: List[Dict]) -> Dict:
        """Combine and validate results from all chunks"""
        aggregated = {
            "customer": None,
            "scope": None,
            "tasks": [],
            "requirements": [],
            "dates": [],
        }
        
        # Customer resolution through voting
        customers = [res.get("customer") for res in results if res.get("customer")]
        if customers:
            aggregated["customer"] = max(set(customers), key=customers.count)
        
        # Scope resolution (longest coherent description)
        scopes = [(res.get("scope", {}).get("text"), res.get("scope", {}).get("page")) 
                 for res in results if res.get("scope")]
        if scopes:
            aggregated["scope"] = max(scopes, key=lambda x: len(x[0]) if x[0] else 0)[0]
        
        # Deduplicate tasks and requirements using more specific identifiers
        seen_tasks = set()
        seen_reqs = set()
        seen_dates = set()
        
        for res in results:
            # Handle tasks
            for task in res.get("tasks", []):
                if not task.get("title") or not task.get("description"):
                    continue
                # Normalize task title and description for better deduplication
                title = task.get("title").lower().strip()
                desc = task.get("description").lower().strip()
                task_id = f"{title}-{desc}"
                if task_id not in seen_tasks:
                    aggregated["tasks"].append(task)
                    seen_tasks.add(task_id)
            
            # Handle requirements
            for req in res.get("requirements", []):
                if not req.get("description"):
                    continue
                # Normalize requirement description for better deduplication
                desc = req.get("description").lower().strip()
                category = req.get("category", "General").lower().strip()
                req_id = f"{category}-{desc}"
                if req_id not in seen_reqs:
                    aggregated["requirements"].append(req)
                    seen_reqs.add(req_id)
            
            # Handle dates
            for date in res.get("dates", []):
                if not date.get("event") or not date.get("date"):
                    continue
                # Normalize date event names for better deduplication
                event = date.get("event").lower().strip().replace("date of award", "contract award")
                date_str = date.get("date").lower().strip()
                date_id = f"{event}-{date_str}"
                if date_id not in seen_dates:
                    # Use the original (non-normalized) text for display
                    aggregated["dates"].append(date)
                    seen_dates.add(date_id)
        
        return aggregated

    def process_rfp(self, pdf_path: str) -> Dict:
        """Main processing pipeline"""
        pages = self.extract_text(pdf_path)
        chunks = self.chunk_content(pages)
        results = [self.process_chunk(chunk) for chunk in chunks]
        return self.aggregate_results(results)

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) != 2:
        print("Usage: python process_rfp.py <pdf_filename>")
        sys.exit(1)
        
    pdf_filename = sys.argv[1]
    processor = RFPProcessor()
    result = processor.process_rfp(pdf_filename)
    
    print("Extracted RFP Information:")
    print(f"Customer: {result['customer']}\n")
    print(f"Scope: {result['scope']}\n")
    
    print("Major Tasks:")
    for task in result['tasks']:
        print(f"- {task.get('title')} (Page {task.get('page', 'N/A')})")
        print(f"  {task.get('description')}\n")
    
    # Group requirements by category
    requirements_by_category = {}
    for req in result['requirements']:
        category = req.get('category', 'General')
        if category not in requirements_by_category:
            requirements_by_category[category] = []
        requirements_by_category[category].append(req)
    
    print("Key Requirements:")
    for category in sorted(requirements_by_category.keys()):
        print(f"\n{category}:")
        for req in requirements_by_category[category]:
            print(f"- (Page {req.get('page', 'N/A')}) {req.get('description')}")
    
    if result['dates']:
        print("\nKey Dates:")
        # Sort dates by page number for more logical ordering
        sorted_dates = sorted(result['dates'], key=lambda x: (x.get('page', 0), x.get('event', '')))
        for date in sorted_dates:
            print(f"- {date.get('event')}: {date.get('date')} (Page {date.get('page', 'N/A')})")