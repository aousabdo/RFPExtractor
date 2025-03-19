import os
import json
import fitz  # PyMuPDF
import logging
from openai import OpenAI
import boto3
from typing import List, Dict, Any

# Configure logging
logger = logging.getLogger(__name__)

def get_openai_api_key() -> str:
    """
    Retrieve OpenAI API key from AWS Secrets Manager.
    Fallback to environment variable if Secrets Manager fails.
    
    Returns:
        str: OpenAI API key
        
    Raises:
        ValueError: If API key not found in Secrets Manager or environment
    """
    secret_name = "OpenAIKey"  # Update if you used a different name
    region_name = "us-east-1"  # Or match your actual region

    try:
        logger.info("Attempting to retrieve OpenAI API key from AWS Secrets Manager")
        session = boto3.session.Session()
        client = session.client(
            service_name='secretsmanager',
            region_name=region_name
        )
        get_secret_value_response = client.get_secret_value(SecretId=secret_name)
        secret = get_secret_value_response['SecretString']
        logger.info("Successfully retrieved API key from Secrets Manager")
        return secret  # If you stored it as a simple string
    except Exception as e:
        logger.warning(f"Failed to get API key from Secrets Manager: {str(e)}")
        logger.info("Falling back to environment variable OPENAI_API_KEY")

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.error("OpenAI API key not found in Secrets Manager or environment")
            raise ValueError(
                "OpenAI API key not found in AWS Secrets Manager or environment variables. "
                "Please either:\n"
                "1. Store key in AWS Secrets Manager with name 'OpenAIKey'\n"
                "2. Set OPENAI_API_KEY environment variable for local development"
            )
        logger.info("Using API key from environment variable")
        return api_key

class RFPProcessor:
    def __init__(self):
        logger.info("Initializing RFPProcessor")
        self.client = OpenAI(api_key=get_openai_api_key())
        logger.debug("OpenAI client initialized")
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
        logger.info(f"Extracting text from PDF: {pdf_path}")
        doc = fitz.open(pdf_path)
        pages = []
        
        for page_num, page in enumerate(doc):
            logger.debug(f"Processing page {page_num + 1}")
            text = page.get_text()
            pages.append({
                "page": page_num + 1,
                "text": text,
                "blocks": [{"bbox": block[:4], "text": block[4]} for block in page.get_text("blocks")]
            })
            
        logger.info(f"Extracted {len(pages)} pages from PDF")
        return pages

    def chunk_content(self, pages: List[Dict], max_tokens: int = 6000) -> List[Dict]:
        """Create context-aware chunks respecting section boundaries"""
        logger.info(f"Chunking content with max_tokens={max_tokens}")
        chunks = []
        current_chunk = []
        current_token_count = 0
        
        for page in pages:
            page_text = f"Page {page['page']}:\n{page['text']}"
            token_estimate = len(page_text) // 4  # Approximate token count
            
            if current_token_count + token_estimate > max_tokens:
                logger.debug(f"Creating new chunk at page {page['page']} (token limit reached)")
                chunks.append({"pages": current_chunk})
                current_chunk = []
                current_token_count = 0
                
            current_chunk.append(page)
            current_token_count += token_estimate
            
        if current_chunk:
            chunks.append({"pages": current_chunk})
            
        logger.info(f"Created {len(chunks)} chunks from {len(pages)} pages")
        return chunks

    def process_chunk(self, chunk: Dict) -> Dict:
        """Process a chunk through GPT-4 with validation"""
        logger.debug("Processing chunk with GPT-4")
        combined_text = "\n".join([f"Page {p['page']}:\n{p['text']}" for p in chunk["pages"]])
        
        response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": f"{self.extraction_prompt}\n\n{combined_text}"}
            ],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        
        try:
            logger.debug("Parsing GPT-4 response")
            return json.loads(response.choices[0].message.content)
        except json.JSONDecodeError:
            logger.error("Failed to parse GPT-4 response as JSON")
            return {"error": "Invalid JSON response"}

    def aggregate_results(self, results: List[Dict]) -> Dict:
        """Combine and validate results from all chunks"""
        logger.info("Aggregating results from all chunks")
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
            logger.debug(f"Selected customer: {aggregated['customer']}")
        
        # Scope resolution (longest coherent description)
        scopes = [(res.get("scope", {}).get("text"), res.get("scope", {}).get("page")) 
                 for res in results if res.get("scope")]
        if scopes:
            aggregated["scope"] = max(scopes, key=lambda x: len(x[0]) if x[0] else 0)[0]
            logger.debug("Selected scope (longest description)")
        
        # Deduplicate tasks and requirements
        seen_tasks = set()
        seen_reqs = set()
        seen_dates = set()
        
        for res in results:
            logger.debug("Processing chunk results for deduplication")
            
            # Handle tasks
            for task in res.get("tasks", []):
                if not task.get("title") or not task.get("description"):
                    continue
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
                desc = req.get("description").lower().strip()
                category = req.get("category", "General").lower().strip()
                req_id = f"{category}-{desc}"
                if req_id not in seen_reqs:
                    aggregated["requirements"].append(req)
                    seen_reqs.add(req_id)
            
            # Handle dates
            for date in res.get("dates", []):
                try:
                    # Skip entries with missing required fields
                    if not date:
                        continue
                        
                    # Ensure date is a dictionary
                    if not isinstance(date, dict):
                        continue
                    
                    # Skip entries with missing key fields
                    if not date.get("event") or not date.get("date"):
                        continue
                    
                    # Sanitize and standardize fields
                    event = str(date.get("event", "")).strip()
                    date_str = str(date.get("date", "")).strip()
                    page = 0
                    
                    # Ensure page is a valid integer
                    if "page" in date and date["page"] is not None:
                        try:
                            page = int(str(date["page"]).strip())
                        except (ValueError, TypeError):
                            # Keep default if conversion fails
                            pass
                    
                    # Create a sanitized date object
                    clean_date = {
                        "event": event,
                        "date": date_str,
                        "page": page
                    }
                    
                    # Add description if available
                    if "description" in date and date["description"]:
                        clean_date["description"] = str(date["description"]).strip()
                    
                    # Generate a unique ID for deduplication
                    date_id = f"{event.lower()}-{date_str.lower()}"
                    
                    if date_id not in seen_dates:
                        aggregated["dates"].append(clean_date)
                        seen_dates.add(date_id)
                        
                except Exception as e:
                    logger.warning(f"Failed to process date entry: {str(e)}")
                    continue
        
        logger.info(f"Aggregation complete: {len(aggregated['tasks'])} tasks, "
                   f"{len(aggregated['requirements'])} requirements, "
                   f"{len(aggregated['dates'])} dates")
        return aggregated

    def process_rfp(self, pdf_path: str) -> Dict:
        """Main processing pipeline"""
        logger.info(f"Starting RFP processing for {pdf_path}")
        pages = self.extract_text(pdf_path)
        chunks = self.chunk_content(pages)
        results = [self.process_chunk(chunk) for chunk in chunks]
        return self.aggregate_results(results)

def process_pdf(pdf_filename: str) -> Dict[str, Any]:
    """Process a PDF file and return structured RFP data.
    
    Args:
        pdf_filename: Path to the PDF file
        
    Returns:
        Dict containing extracted RFP information with the following structure:
        {
            "customer": str,
            "scope": str,
            "tasks": List[Dict],
            "requirements": List[Dict],
            "dates": List[Dict]
        }
    """
    logger.info(f"Processing PDF file: {pdf_filename}")
    processor = RFPProcessor()
    result = processor.process_rfp(pdf_filename)
    logger.info("PDF processing complete")
    return result

if __name__ == "__main__":
    # Configure logging for CLI usage
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    import sys
    if len(sys.argv) != 2:
        logger.error("Invalid number of arguments")
        print("Usage: python process_rfp.py <pdf_filename>")
        sys.exit(1)
        
    result = process_pdf(sys.argv[1])
    
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