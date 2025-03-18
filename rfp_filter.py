#!/usr/bin/env python3
import sys
import json
import logging
from typing import List, Dict, Any
from process_rfp import RFPProcessor

# Configure logging
logger = logging.getLogger(__name__)

def get_customer(result: Dict[str, Any]) -> Dict[str, Any]:
    return {"customer": result['customer']}

def get_scope(result: Dict[str, Any]) -> Dict[str, Any]:
    return {"scope": result['scope']}

def get_tasks(result: Dict[str, Any]) -> Dict[str, Any]:
    return {"tasks": result['tasks']}

def get_requirements(result: Dict[str, Any], category: str = None) -> Dict[str, Any]:
    if category:
        logger.debug(f"Filtering requirements for category: {category}")
        filtered_reqs = [
            req for req in result['requirements']
            if req.get('category', 'General').lower() == category.lower()
        ]
        return {"requirements": filtered_reqs}
    return {"requirements": result['requirements']}

def get_dates(result):
    # Return empty list if no dates key or it's empty
    if not result or 'dates' not in result or not result['dates']:
        return {"dates": []}
    
    # Make a copy of dates to avoid modifying the original
    dates_list = result.get('dates', [])
    
    # Ensure dates_list is actually a list
    if not isinstance(dates_list, list):
        try:
            dates_list = list(dates_list)
        except:
            return {"dates": []}
    
    valid_dates = []
    
    # Process each date, with extensive error handling
    for date in dates_list:
        try:
            # Skip None entries
            if date is None:
                continue
                
            # Ensure date is a dictionary
            if not isinstance(date, dict):
                continue
                
            # Create a sanitized date entry with default values
            sanitized_date = {
                'page': 0,
                'event': '',
                'date': date.get('date', ''),
                'description': date.get('description', '')
            }
            
            # Process page field
            if 'page' in date and date['page'] is not None:
                try:
                    sanitized_date['page'] = int(str(date['page']).strip())
                except:
                    pass  # Keep default value
            
            # Process event field
            if 'event' in date and date['event'] is not None:
                try:
                    sanitized_date['event'] = str(date['event']).strip()
                except:
                    pass  # Keep default value
            
            # Copy any other fields
            for key, value in date.items():
                if key not in sanitized_date and value is not None:
                    try:
                        sanitized_date[key] = value
                    except:
                        pass
            
            valid_dates.append(sanitized_date)
        except Exception as e:
            # If any date fails processing, just skip it
            print(f"Warning: Failed to process date entry: {str(e)}")
            continue
    
    # Try to sort dates, with fallback to unsorted
    try:
        # Sort first by page, then by event
        sorted_dates = sorted(valid_dates, key=lambda x: (x['page'], x['event']))
        return {"dates": sorted_dates}
    except Exception as e:
        # If sorting fails, return unsorted list
        print(f"Warning: Failed to sort dates: {str(e)}")
        return {"dates": valid_dates}

# Base sections
BASE_SECTIONS = {
    'customer': get_customer,
    'scope': get_scope,
    'tasks': get_tasks,
    'dates': get_dates,
}

# Requirements subcategories
REQ_CATEGORIES = {
    'security': lambda r: get_requirements(r, 'Security'),
    'compliance': lambda r: get_requirements(r, 'Compliance'),
    'it_standards': lambda r: get_requirements(r, 'IT Standards'),
    'personnel': lambda r: get_requirements(r, 'Personnel'),
    'requirements': get_requirements,  # All requirements
}

# Combined sections dictionary with safer implementation
SECTIONS = {
    **BASE_SECTIONS,
    **REQ_CATEGORIES,
    'all': lambda r: {
        **get_customer(r),
        **get_scope(r),
        **get_tasks(r),
        **get_requirements(r),
        **get_dates(r)
    }
}

def run_filter(pdf_filename: str, sections: List[str]) -> Dict[str, Any]:
    """
    Process an RFP PDF file and extract specified sections.
    
    Args:
        pdf_filename (str): Path to the PDF file
        sections (List[str]): List of sections to extract. Defaults to ["all"] if empty or invalid.
                            Valid sections: customer, scope, tasks, dates, security, compliance,
                            it_standards, personnel, requirements, all
        
    Returns:
        Dict[str, Any]: Extracted data in a structured format
    """
    logger.info(f"Processing PDF: {pdf_filename}")
    
    # Validate and clean sections input
    if not sections:
        logger.warning("No sections specified, defaulting to ['all']")
        sections = ["all"]
    
    # Convert to list if string is passed
    if isinstance(sections, str):
        logger.warning(f"String section '{sections}' provided, converting to list")
        sections = [sections]
    
    # Clean and validate sections
    cleaned_sections = []
    for section in sections:
        if not isinstance(section, str):
            logger.warning(f"Skipping non-string section: {section}")
            continue
            
        section = section.lower().strip()
        if section in SECTIONS:
            cleaned_sections.append(section)
        else:
            logger.warning(f"Invalid section '{section}' will be ignored")
    
    # If no valid sections after cleaning, default to "all"
    if not cleaned_sections:
        logger.warning("No valid sections after cleaning, defaulting to ['all']")
        cleaned_sections = ["all"]
    
    logger.info(f"Processing with validated sections: {cleaned_sections}")
    
    processor = RFPProcessor()
    logger.info("Initializing RFP processor")
    result = processor.process_rfp(pdf_filename)
    logger.info("Successfully processed RFP")
    
    if len(cleaned_sections) == 1:
        logger.info(f"Extracting single section: {cleaned_sections[0]}")
        return SECTIONS[cleaned_sections[0]](result)
    
    # Combine multiple sections
    logger.info("Combining multiple sections")
    output = {}
    for section in cleaned_sections:
        logger.debug(f"Processing section: {section}")
        output.update(SECTIONS[section](result))
    
    return output

def print_text_output(data: Dict[str, Any]) -> None:
    """Print data in a human-readable format for CLI usage."""
    logger.debug("Formatting output for CLI display")
    
    if 'customer' in data:
        print(f"Customer: {data['customer']}\n")
    
    if 'scope' in data:
        print(f"Scope: {data['scope']}\n")
    
    if 'tasks' in data:
        print("Major Tasks:")
        for task in data['tasks']:
            print(f"- {task.get('title')} (Page {task.get('page', 'N/A')})")
            print(f"  {task.get('description')}\n")
    
    if 'requirements' in data:
        print("Key Requirements:")
        reqs_by_category = {}
        for req in data['requirements']:
            cat = req.get('category', 'General')
            if cat not in reqs_by_category:
                reqs_by_category[cat] = []
            reqs_by_category[cat].append(req)
        
        for cat in sorted(reqs_by_category.keys()):
            print(f"\n{cat}:")
            for req in reqs_by_category[cat]:
                print(f"- (Page {req.get('page', 'N/A')}) {req.get('description')}")
    
    if 'dates' in data:
        print("\nKey Dates:")
        for date in data['dates']:
            print(f"- {date.get('event')}: {date.get('date')} (Page {date.get('page', 'N/A')})")

def main():
    if len(sys.argv) < 2:
        logger.error("No PDF file specified")
        print("Usage: python rfp_filter.py <pdf_filename> [section1 section2 ...]")
        print("\nAvailable sections (optional, defaults to 'all'):")
        print("  Base sections:", ', '.join(BASE_SECTIONS.keys()))
        print("  Requirements:", ', '.join(REQ_CATEGORIES.keys()))
        print("  Special:", 'all')
        sys.exit(1)
    
    pdf_filename = sys.argv[1]
    # Get sections from arguments if provided, otherwise default to ["all"]
    sections = [s.lower() for s in sys.argv[2:]] if len(sys.argv) > 2 else ["all"]
    logger.info(f"CLI invocation - PDF: {pdf_filename}, Sections: {sections}")
    
    try:
        result = run_filter(pdf_filename, sections)
        print_text_output(result)
    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        print(f"Error: {str(e)}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        print(f"Error: An unexpected error occurred")
        sys.exit(1)

if __name__ == "__main__":
    # Configure logging for CLI usage
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    main() 