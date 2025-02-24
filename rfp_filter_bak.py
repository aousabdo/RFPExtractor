#!/usr/bin/env python3
import sys
import json
from process_rfp import RFPProcessor

def print_customer(result):
    print(f"Customer: {result['customer']}\n")

def print_scope(result):
    print(f"Scope: {result['scope']}\n")

def print_tasks(result):
    print("Major Tasks:")
    for task in result['tasks']:
        print(f"- {task.get('title')} (Page {task.get('page', 'N/A')})")
        print(f"  {task.get('description')}\n")

def print_requirements(result, category=None):
    requirements_by_category = {}
    for req in result['requirements']:
        req_category = req.get('category', 'General')
        if category and req_category.lower() != category.lower():
            continue
        if req_category not in requirements_by_category:
            requirements_by_category[req_category] = []
        requirements_by_category[req_category].append(req)
    
    if not requirements_by_category:
        return
        
    print("Key Requirements:")
    for cat in sorted(requirements_by_category.keys()):
        print(f"\n{cat}:")
        for req in requirements_by_category[cat]:
            print(f"- (Page {req.get('page', 'N/A')}) {req.get('description')}")

def print_dates(result):
    if result['dates']:
        print("Key Dates:")
        sorted_dates = sorted(result['dates'], key=lambda x: (x.get('page', 0), x.get('event', '')))
        for date in sorted_dates:
            print(f"- {date.get('event')}: {date.get('date')} (Page {date.get('page', 'N/A')})")

# Base sections
BASE_SECTIONS = {
    'customer': print_customer,
    'scope': print_scope,
    'tasks': print_tasks,
    'dates': print_dates,
}

# Requirements subcategories
REQ_CATEGORIES = {
    'security': lambda r: print_requirements(r, 'Security'),
    'compliance': lambda r: print_requirements(r, 'Compliance'),
    'it_standards': lambda r: print_requirements(r, 'IT Standards'),
    'personnel': lambda r: print_requirements(r, 'Personnel'),
    'requirements': lambda r: print_requirements(r),  # All requirements
}

# Combined sections dictionary
SECTIONS = {
    **BASE_SECTIONS,
    **REQ_CATEGORIES,
    'all': lambda r: [f(r) for f in [print_customer, print_scope, print_tasks, 
                                    lambda x: print_requirements(x), print_dates]]
}

def main():
    if len(sys.argv) < 3:
        print("Usage: python rfp_filter.py <pdf_filename> <section1> [section2 ...]")
        print("\nAvailable sections:")
        print("  Base sections:", ', '.join(BASE_SECTIONS.keys()))
        print("  Requirements:", ', '.join(REQ_CATEGORIES.keys()))
        print("  Special:", 'all')
        sys.exit(1)
        
    pdf_filename = sys.argv[1]
    sections = [s.lower() for s in sys.argv[2:]]
    
    invalid_sections = [s for s in sections if s not in SECTIONS]
    if invalid_sections:
        print(f"Error: Invalid section(s): {', '.join(invalid_sections)}")
        print("\nAvailable sections:")
        print("  Base sections:", ', '.join(BASE_SECTIONS.keys()))
        print("  Requirements:", ', '.join(REQ_CATEGORIES.keys()))
        print("  Special:", 'all')
        sys.exit(1)
    
    processor = RFPProcessor()
    result = processor.process_rfp(pdf_filename)
    
    # Print requested sections with spacing between them
    for i, section in enumerate(sections):
        if i > 0:
            print("\n" + "="*50 + "\n")  # Section separator
        SECTIONS[section](result)

if __name__ == "__main__":
    main() 