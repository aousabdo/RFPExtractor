from agno.agent import Agent
from agno.models.anthropic import Claude
from agno.models.openai import OpenAIChat
from agno.team.team import Team
from agno.tools.duckduckgo import DuckDuckGoTools
from agno.tools.reasoning import ReasoningTools
# from agno.tools.yfinance import YFinanceTools

import dotenv, os
import re
from rich.console import Console

dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
dotenv.load_dotenv(dotenv_path, override=True)

llm_model = "gpt-4.1"
llm_model = "gpt-5"
llm_model = "gpt-5-mini"
llm_model = "gpt-5-nano"
    
# import os, re

# key = os.getenv("OPENAI_API_KEY", "")
# print("Using OPENAI_API_KEY:", re.sub(r"(sk-[^_]+_)[A-Za-z0-9_-]{20,}(.*)", r"\1***REDACTED***\2", key))


# agent = Agent(
#     model=OpenAIChat(id="gpt-5"),
#     markdown=True
# )

# # Print the response in the terminal
# agent.print_response("Share a 2 sentence horror story.")

# raise SystemExit("stop code here")

# We need the following agents:

# 1. RFP Analyzer Agent: We already have this agent built, we will need to tweak it to fit our needs.
# 2. Outlining and Compliance matrix agent: this is somewhat already done as part of our RFP Analyzer agent above. But we need to revisit
# 3. Technology Agent: Research technologies that are relevent to the RFP. This agne should browse the internet and perform research on the technologies related to the given RFP.
# 4. English Agent: This agent takes a first glance at the proposal sections written by other agents and makes sure it is correct etc. 
# 5. Tone agent: make sure the final proposal souunds like it is from the same person
# 6. Proposal Scoring Agent: This agent scores the proposal based on the RFP and also based on what Patrick has already done in his custom gpt
# 7. Maestor Agent: This is the orchestrating agent that will be responsible for coordinating the other agents and making sure the final proposal is correct and complete.


# Outlining and Compliance Matrix Agent: Extracts a structured outline and compliance matrix from RFPs
outlining_compliance_agent = Agent(
    name="Outlining & Compliance Matrix Agent",
    role="Extracts a detailed outline and compliance matrix from RFPs, mapping requirements to sections and ensuring all compliance items are captured. Outputs structured tables and summaries.",
    model=OpenAIChat(id=llm_model),
    tools=[ReasoningTools(add_instructions=True)],
    instructions=[
        "Generate a hierarchical outline of the RFP sections and subsections.",
        "Extract all compliance requirements and map them to their corresponding sections/pages.",
        "Output a compliance matrix as a table: Requirement | Section | Page | Compliance Status (Y/N/Partial)",
        "Highlight any ambiguous or missing compliance items.",
        "Be concise and use tables wherever possible.",
    ],
    add_datetime_to_instructions=True,
)

# English Agent: Reviews proposal sections for clarity, correctness, and consistency
english_agent = Agent(
    name="English Agent",
    role="Reviews proposal sections for clarity, correctness, grammar, tone, and logical flow. Provides feedback and suggested edits to ensure professional, consistent, and persuasive writing.",
    model=OpenAIChat(id=llm_model),
    tools=[ReasoningTools(add_instructions=True)],
    instructions=[
        "Read the provided proposal section(s) and check for grammar, spelling, and clarity.",
        "Suggest edits to improve tone, flow, and persuasiveness, making sure the writing sounds like it is from the same author throughout.",
        "Point out any logical inconsistencies or unclear statements.",
        "Output both the revised text and a brief summary of changes.",
        "Be concise and direct in your feedback.",
    ],
    add_datetime_to_instructions=True,
)

# Tone Agent: Ensures consistent, professional, and persuasive tone throughout the proposal
tone_agent = Agent(
    name="Tone Agent",
    role="Ensures the proposal maintains a consistent, professional, and persuasive tone and style throughout all sections. Harmonizes voice, formality, and word choice.",
    model=OpenAIChat(id=llm_model),
    tools=[ReasoningTools(add_instructions=True)],
    instructions=[
        "Review the provided proposal sections for tone, style, and voice consistency.",
        "Suggest edits to align all sections to a unified, professional, and persuasive tone.",
        "Point out any sections that sound out of place or inconsistent.",
        "Output both the harmonized text and a summary of tone/style changes.",
        "Be specific and concise in your suggestions.",
    ],
    add_datetime_to_instructions=True,
)

# Proposal Scoring Agent: Scores the proposal based on RFP requirements and best practices
proposal_scoring_agent = Agent(
    name="Proposal Scoring Agent",
    role="Scores the proposal against the RFP requirements and industry best practices. Provides a detailed breakdown of strengths, weaknesses, and actionable recommendations.",
    model=OpenAIChat(id=llm_model),
    tools=[ReasoningTools(add_instructions=True)],
    instructions=[
        "Evaluate the proposal section(s) for compliance, completeness, clarity, and competitiveness.",
        "Score each section and the overall proposal on a 0-100 scale, with rationale for each score.",
        "Highlight strengths, weaknesses, and areas for improvement.",
        "Output a summary table: Section | Score | Strengths | Weaknesses | Recommendations.",
        "Be objective, thorough, and actionable in your feedback.",
    ],
    add_datetime_to_instructions=True,
)

# RFP Analyzer Agent: Extracts structured information from plain RFP text
rfp_analyzer_agent = Agent(
    name="RFP Analyzer Agent",
    role="Extracts structured information from RFP text, including customer, scope, tasks, requirements, and key dates. Outputs a JSON-like structure for downstream processing.",
    model=OpenAIChat(id=llm_model),
    tools=[ReasoningTools(add_instructions=True)],
    instructions=[
        "Analyze the provided RFP text and extract the following:",
        "- Customer (primary agency/department)",
        "- Clear scope of work (1-2 sentences)",
        "- Major tasks (active work activities to be performed, with titles, descriptions, and page numbers)",
        '  Note: Only include actual work activities that require active effort, not compliance requirements',
        "- Key requirements (rules, standards, compliance requirements with page numbers)",
        "  Categories: Security, Compliance, IT Standards, Personnel",
        "- Key dates (submission, performance period)",
        '',
        "Format as JSON with this exact structure:",
        '{',
        '    "customer": "string",',
        '    "scope": {"text": "string", "page": number},',
        '    "tasks": [{"title": "string", "description": "string", "page": number}],',
        '    "requirements": [{"category": "string", "description": "string", "page": number}],',
        '    "dates": [{"event": "string", "date": "string", "page": number}]',
        '}',
        '',
        "Guidelines:",
        '- Tasks must be active work activities (e.g., "Develop system", not "Must comply with")',
        '- Requirements should be rules/standards that must be followed',
        '- Group similar requirements under the same category',
        '- Normalize date descriptions (e.g., \"after contract award\" vs \"after the date of award\")',
        '- Avoid duplicate information with slight wording variations',
        '- Each requirement, task, and date should appear only once in the output',
        '- Consolidate similar requirements into single entries',
    ],
    add_datetime_to_instructions=True,
)

technology_agent = Agent(
    name="Technology Agent",
    role="Research and summarize technologies relevant to the RFP, including recent trends, standards, and best practices. Provide concise, actionable insights with sources.",
    model=OpenAIChat(id=llm_model),
    tools=[DuckDuckGoTools()],
    instructions=[
        "Focus on technologies, frameworks, and standards directly relevant to the RFP.",
        "Summarize findings clearly and cite all sources.",
        "Highlight recent developments, pros/cons, and suitability for government/enterprise use.",
    ],
    add_datetime_to_instructions=True,
)

# Section Writing Agent: Drafts full proposal sections using outline, compliance, and research
section_writing_agent = Agent(
    name="Section Writing Agent",
    role="Drafts complete proposal sections based on the provided outline, compliance matrix, and technology research. Integrates all requirements, best practices, and recommendations into clear, persuasive, and compliant proposal text.",
    model=OpenAIChat(id=llm_model),
    tools=[ReasoningTools(add_instructions=True)],
    instructions=[
        "For each section in the provided outline, write a detailed, professional draft that:",
        "- Integrates all relevant compliance requirements, personnel/security/IT standards, and key dates.",
        "- Incorporates technology research and best practices.",
        "- Uses the compliance matrix to ensure all requirements are addressed.",
        "- Follows the structure and recommendations from the English Agent.",
        "- Uses clear, persuasive, and action-oriented language.",
        "- References attachments, tables, and supporting documents as needed.",
        "Output each section as markdown, with clear section headers and numbering.",
        "Return a dictionary where each key is a section name/number and the value is the full markdown draft for that section.",
        "Be specific, avoid generic statements, and ensure all RFP requirements are addressed.",
        "Do not skip any sections from the outline.",
    ],
    add_datetime_to_instructions=True,
)

# Proposal Outline Agent: Generates a detailed proposal outline from RFP Analyzer output
proposal_outline_agent = Agent(
    name="Proposal Outline Agent",
    role="Generates a detailed, hierarchical proposal outline based on the structured RFP analysis, ensuring all customer requirements and best practices are addressed in the proposal structure.",
    model=OpenAIChat(id=llm_model),
    tools=[ReasoningTools(add_instructions=True)],
    instructions=[
        "Read the structured RFP analysis (JSON) from the RFP Analyzer Agent.",
        "Generate a recommended proposal outline that covers all required sections, subsections, and logical groupings to address the RFP.",
        "Output the outline as a hierarchical numbered list (e.g., 1., 1.1, 1.2, 2., etc.) in markdown.",
        "Flag any areas where the RFP is ambiguous or where additional sections may be needed for competitiveness.",
        "Be concise and do not include content, just section titles/headings.",
    ],
    add_datetime_to_instructions=True,
)

# Maestor Agent: Orchestrates all specialized agents to produce a complete, high-quality proposal
maestor_team = Team(
    name="Maestor Orchestration Team",
    mode="coordinate",
    model=OpenAIChat(id=llm_model),
    members=[
        rfp_analyzer_agent,  # 1. Analyze RFP and extract structured info
        proposal_outline_agent,  # 2. Generate detailed proposal outline from RFP analysis
        outlining_compliance_agent,  # 3. Extract compliance matrix and map requirements
        technology_agent,  # 4. Research relevant technologies
        section_writing_agent,  # 5. Draft proposal sections using outline, compliance, and research
        english_agent,  # 6. Review language/clarity
        tone_agent,  # 7. Harmonize tone/style
        proposal_scoring_agent,  # 8. Score proposal
    ],
    tools=[ReasoningTools(add_instructions=True)],
    instructions=[
        "Coordinate all member agents to analyze the RFP, generate a detailed proposal outline, extract structure and compliance, research technologies, draft full proposal sections, review language, harmonize tone, and score the proposal.",
        "Ensure the Proposal Outline Agent uses the output of the RFP Analyzer Agent to generate a comprehensive outline before compliance, technology, and section writing steps.",
        "Each step should be completed in logical order and outputs passed between agents as needed.",
        "If any agent flags missing or ambiguous information, highlight it in the final output.",
        "Produce a SINGLE, consolidated proposal package with all required sections, compliance matrix, technology research, language review, tone harmonization, and scoring summary.",
        "DO NOT duplicate content - each section should appear only once in the final output.",
        "Output all tables as markdown tables for easy rendering.",
        "Be explicit and clear in the final summary and recommendations.",
        "Ensure the final output is clean, well-structured, and free of redundant information.",
    ],
    markdown=True,
    show_members_responses=False,
    enable_agentic_context=True,
    add_datetime_to_instructions=True,
    success_criteria="The team has produced a complete, high-quality proposal package that is well-structured, compliant, persuasive, and ready for submission.",
)


sample_rfp = r'''
Customer Information:
Department of Homeland Security (DHS)

Scope of Work:
This procurement is for IT Infrastructure and Geospatial Support Services for the Fleet H.O.M.E. application, which supports ICE Fleet Management activities by providing a single interface for data entry, validation, and analytics.

## Compliance Requirements
| Requirement | Page |
| --- | --- |
| This procurement will be conducted in accordance with FAR 16. | 5 |
| Adhere to Office of Management and Budget (OMB) Circulars A-130, A-127, and A-123. | 8 |
| Adhere to Section 508 of the Rehabilitation Act for accessibility of electronic and information technology. | 22 |
| All EIT deliverables must comply with 36 CFR 1194 standards for software, web-based applications, and documentation. | 23 |
| Contractor must comply with DHS Instruction 121-01-007, Revision 2, and 5 CFR 731 for security and personnel requirements. | 31 |
| Adhere to DHS Management Directive 11042.1 and other DHS policies for safeguarding sensitive information. | 37 |
| Contractor must comply with FAR 52.224-1 Privacy Act Notification, FAR 52.224-2 Privacy Act, and other privacy-related regulations. | 47 |
| Contractor must adhere to DHS Instruction 121-01-007-001 for personnel security, suitability, and fitness program. | 50 |
| All hardware, software, and services must comply with DHS 4300A DHS Sensitive System Policy and DHS Policy Directive 4300A. | 58 |
| The Government may conduct periodic reviews to ensure security requirements are implemented and enforced. | 58 |
| Prohibition on contracting for hardware, software, and services developed or provided by Kaspersky Lab covered entities. | 62 |
| Prohibition on contracting for certain telecommunications and video surveillance services or equipment as per Section 889 of the John S. McCain National Defense Authorization Act for Fiscal Year 2019. | 64 |
| Contractor employees must complete initial and annual privacy training as per DHS requirements. | 71 |
| Include the privacy training clause in all subcontracts where subcontractor employees will handle personally identifiable information. | 72 |
| Contractor must comply with notification and credit monitoring requirements for PII incidents as directed by the Contracting Officer. | 80 |
| Contractor must comply with DHS policies applicable to acquisition of commercial items. | 86 |
| Contractor must comply with FAR 52.224-1 Privacy Act Notification and FAR 52.224-2 Privacy Act, ensuring access to Privacy Act information is limited. | 89 |
| Contractor must obtain Contracting Officer's approval before hiring subcontractors and abide by Government guidance for protecting sensitive information. | 90 |
| Adhere to DHS MD 4300.1, Information Technology Systems Security for processing sensitive government information. | 98 |

## Personnel Requirements
| Requirement | Page |
| --- | --- |
| Key Personnel must include ETL Developer, Systems Administrator, Database Administrator, and API Developer with requisite experience and education as identified in the SOW. | 7 |
| Key Personnel Certification: Offerors must certify that each individual proposed as Key Personnel was contacted after the issue date of the solicitation and confirmed availability for contract performance. | 8 |
| Contractor personnel may telework with prior approval and must adhere to defined telework policies. | 9 |
| ETL Developer must have 3-5 years' experience with Informatica PowerCenter and programming languages (SQL, PL/SQL). | 28 |
| Systems Administrator must have 3-5 years experience in AWS environment and Windows Server. | 28 |
| Database Administrator must have 3-5 years experience as an Oracle Database administrator. | 28 |
| Contractor personnel must have 3-5 years of experience with REST-based APIs, HTTP and SOAP Protocols, REST and Rest Oriented Architecture (ROA), and JAVA/JavaScript/Python/.NET development. | 29 |
| Contractor personnel must have excellent communication skills, superior organizational skills, and the ability to prioritize and manage multiple tasks. | 29 |
| All contractor employees accessing DHS IT systems must have an ICE-issued/provisioned PIV card and receive annual security training. | 45 |
| Privacy Lead must have excellent writing and communication skills, experience writing PIAs, and knowledge of the Privacy Act of 1974 and the E-Government Act of 2002. | 49 |
| Contractor employees involved with IT systems handling sensitive information must receive periodic training at least annually in security awareness and accepted security practices. | 55 |
| Contractor shall provide documentation of completion of privacy training to the Contracting Officer upon request. | 71 |
| Each individual employed under the contract shall be a U.S. citizen or a lawful permanent resident, unless exceptions are approved. | 86 |
| Contractor employees must be U.S. citizens or Legal Permanent Residents, with exceptions granted under DHS Instruction 121-01-007. | 96 |
| Contractor employees must complete Cybersecurity Awareness Training upon initial access and annually thereafter. | 99 |

## Security Requirements
| Requirement | Page |
| --- | --- |
| Comply with Federal Privacy and Security Legislation, Federal Information Processing Standards (FIPS), and Presidential Directives on Systems Security. | 8 |
| All personnel accessing sensitive information must sign a Non-Disclosure Agreement (DHS Form 11000-6). | 21 |
| Ensure all Government-Furnished Equipment (GFE) is secured and tracked using ICE Form G-570. | 22 |
| Contractor employees must wear an identification badge approved by security when visiting Government facilities and comply with all Government escort rules and requirements. | 30 |
| Contractor personnel must meet the minimum security clearance or investigation requirements of ICE and must be U.S. citizens. | 30 |
| Contractor must provide a list of all positions, including titles and specific descriptions of duties, for security vetting before personnel start work. | 31 |
| Contractor employees must undergo a position-sensitivity analysis and background investigations processed through OPR PSD. | 31 |
| Follow DHS Sensitive Systems Policy Directive 4300A and ensure compliance with FIPS 140-2 for cryptographic modules. | 37 |
| Contractor employees must undergo a Fitness screening process and background investigations before accessing sensitive information or systems. | 50 |
| Contractor employees must complete annual Information Technology Security Awareness Training and sign DHS Rules of Behavior before accessing DHS systems. | 46 |
| Contractors must complete DHS Form 11000-6-Sensitive but Unclassified Information Non-Disclosure Agreement (NDA) for access to sensitive information within 10 calendar days of entry-on-duty date. | 54 |
| Contractor must appoint a senior official as the Corporate Security Officer to interface with OPR PSD through the COR on all security matters. | 54 |
| Contractor employees must have favorably adjudicated background investigations commensurate with the defined sensitivity level. | 55 |
| All personnel accessing Department IT systems must have an ICE-issued/provisioned Personal Identity Verification (PIV) card and complete Cybersecurity Awareness Training (CSAT) upon initial access and annually thereafter. | 55 |
| Contractor must report any use of covered telecommunications equipment or services within one business day of identification. | 70 |
| Contractors must provide adequate security to protect Controlled Unclassified Information (CUI) from unauthorized access and disclosure. | 76 |
| Report all known or suspected incidents involving PII or SPII within 1 hour of discovery. | 78 |
| Contractor employees must complete necessary forms for security, including background investigations, and may be required to be fingerprinted or subject to other investigations. | 85 |
| Contractor employees authorized to access CUI must receive initial and refresher training concerning the protection and disclosure of CUI. | 85 |
| Contractor must ensure all employees complete DHS security training and sign the DHS Rules of Behavior before accessing DHS systems and sensitive information. | 89 |
| Contractor employees must undergo a background investigation and obtain a favorable preliminary Fitness determination before accessing sensitive information or systems. | 94 |
| Contractor must protect sensitive information from loss, misuse, modification, and unauthorized access in accordance with DHS Management Directive 11042.1 and ICE Policy 4003. | 98 |

## IT Standards
| Requirement | Page |
| --- | --- |
| Utilize Oracle database and tools to comply with DHS Enterprise Architecture requirements. | 9 |
| Use DHS Office of Accessible Systems and Technology approved testing methods for Section 508 compliance. | 24 |
| Contractor must adhere to DHS MD 4300.1, Information Technology Systems Security, for processing sensitive government information. | 36 |
| Contractor employees accessing Department IT systems must have an ICE-issued/provisioned Personal Identity Verification (PIV) card and complete Cybersecurity Awareness Training (CSAT) upon initial access and annually thereafter. | 36 |
| Develop Security Authorization documentation using Government-provided templates and ensure compliance with NIST SP 800-53. | 39 |
| All tasks must be performed on authorized Government networks using Government-furnished IT equipment. | 47 |
| All written reports must be in electronic format compatible with ICE applications (currently Microsoft 365). | 56 |
| Prohibition on the use of telecommunications equipment produced by Huawei Technologies Company or ZTE Corporation. | 67 |
| CUI transmitted via email must be protected by encryption or transmitted within secure communications systems. | 78 |
| Contractor employees must take an annual Information Technology Security Awareness Training course before accessing sensitive information. | 88 |
| All program data must be accessible to the Government within 24 hours of request, formatted to ensure rapid processing by government applications. | 92 |
| Contractor employees accessing Department IT systems require an ICE-issued/provisioned Personal Identity Verification (PIV) card. | 99 |

## Tasks
| Task | Description | Page |
| --- | --- | --- |
| Fleet IT Infrastructure and Geospatial Support Services | Provide Fleet IT Infrastructure and Geospatial Support Services for a base year and four option years. | 3 |
| Task 1: Steady State ETL Services for the Existing Infrastructure | Provide Extract, Transform, and Load (ETL) services using Informatica PowerCenter to support the existing infrastructure. | 13 |
| Task 2: System Administration | Perform system administration tasks to maintain the Fleet H.O.M.E. IT infrastructure. | 14 |
| Task 3: Database Administrator | Manage and maintain database systems to support Fleet H.O.M.E. operations. | 14 |
| Task 4: API Development Support | Develop and support APIs using JAVA 8 and Spring Boot for system integration and geospatial solutions. | 15 |
| Task 5: Program Manager | Oversee the program-management activities related to the Fleet H.O.M.E. project. | 15 |
| Task 1: Steady State ETL Services for the Existing Infrastructure | Administer and develop ETL activities using Informatica PowerCenter, including script design, data ingestion, transformation, and security management. | 24 |
| Task 2: System Administration | Maintain, upgrade, and manage all Fleet H.O.M.E. software and related infrastructure, ensuring system performance and security. | 25 |
| Task 3: Database Administrator | Maintain the Oracle data warehouse, conduct health checks, and design schema to support new data sources for the Fleet Program. | 25 |
| Task 4: API Development Support | Build and maintain software integrations to support data ingestion, develop API integration strategies, and ensure smooth functioning of integration architecture. | 26 |
| Task 5: Program Manager | Ensure monthly invoicing and reporting, administer contract staff, and manage Government-Furnished Equipment/Property. | 26 |
| API Development and Integration | Evaluate and select enterprise application development and integration technologies and solutions to support data ingestion from external sources. Conduct functional, regression, and load testing for API technologies. | 29 |
| API Design and Deployment Roadmap | Work with the ITPM and associated Fleet H.O.M.E. IT Support personnel in shaping an API design and deployment roadmap. | 29 |
| Complete Security Authorization Process | Develop and submit Security Authorization documentation using Government templates, validated by an independent third party, for acceptance by the Headquarters or Component CIO. | 39 |
| Support Privacy Threshold Analysis | Assist the Government in completing the Privacy Threshold Analysis (PTA) and ensure project management plans include time for PTA, PIA, and SORN completion. | 40 |
| Continuous Monitoring | Store monthly continuous monitoring data for at least one year and ensure data encryption in accordance with FIPS 140-2. | 41 |
| Sensitive Information Incident Reporting | Report all known or suspected sensitive information incidents to the appropriate DHS authorities within one hour of discovery. | 41 |
| Provide Credit Monitoring Services | If required, provide credit-monitoring services for individuals affected by a sensitive-information incident for at least 18 months. | 44 |
| Complete Separation Checklist | Contractor shall complete a separation checklist before any employee or subcontractor employee terminates working on the contract, verifying return of Government-furnished equipment and termination of access to sensitive information. | 48 |
| Assign Privacy Lead | Assign or procure a Privacy Lead responsible for supporting DHS in completing required privacy documentation and ensuring compliance with privacy regulations. | 49 |
| Provide Monthly Progress Reports | The Contractor shall provide a monthly progress report to the COR via electronic mail by the 5th business day after the end of the month, including a summary of all work performed, technical progress, schedule status, and any changes or recommendations. | 56 |
| Attend Progress Meetings | The Program Manager shall attend monthly Progress Meetings and additional meetings as required by the Government to discuss performance issues. | 56 |
| Report Identification of Covered Articles | In the event the Contractor identifies covered articles provided to the Government during contract performance, the Contractor shall report in writing to the Contracting Officer, Contracting Officer's Representative, and the Enterprise Security Operations Center. | 63 |
| Report Identification of Covered Telecommunications Equipment | If covered telecommunications equipment or services are identified during contract performance, report the information to the Contracting Officer, Contracting Officer's Representative, and the Network Operations Security Center. | 69 |
| Furnish Phase-In Training | Provide phase-in training to ensure continuity of services without interruption upon contract expiration. | 72 |
| Negotiate Phase-In, Phase-Out Plan | Negotiate in good faith a plan with a successor to determine the nature and extent of phase-in, phase-out services required. | 72 |
| Provide Experienced Personnel | Provide sufficient experienced personnel during the phase-in, phase-out period to maintain required service levels. | 72 |
| Notify Individuals of PII or SPII Incidents | Notify any individual whose PII or SPII was under the control of the Contractor or resided in an information system under control of the Contractor at the time the incident occurred, as directed by the Contracting Officer. | 81 |
| Provide Credit Monitoring Services | Provide credit-monitoring services to individuals whose PII or SPII was compromised, for a period of not less than 18 months from the date the individual is notified. | 81 |
| Establish a Dedicated Call Center | Establish a dedicated call center to assist affected individuals with credit-monitoring services and provide necessary information and support. | 82 |
| Perform Tasks on Authorized Government Networks | The Contractor shall perform all tasks on authorized Government networks, using Government-furnished IT and other equipment, ensuring Government information remains within authorized networks. | 90 |
| Complete Separation Checklist | Contractor shall complete a separation checklist before any employee or subcontractor employee terminates working on the contract, verifying the return of Government-furnished equipment and proper disposal of sensitive information. | 90 |
| Assign Privacy Lead | If the contract involves an IT system build or substantial development, the Contractor shall assign a Privacy Lead to support DHS in completing required privacy documentation. | 91 |
| Notify OPR PSD of Employee Terminations | Notify OPR PSD via the COR with an ICE Form 50-005 of all terminations/resignations of contractor employees within five days of occurrence. | 97 |
| Return Identification Cards and Passes | Return expired ICE-issued identification cards and building passes of terminated/resigned employees to the COR. | 97 |
| Submit Quarterly Employee Report | Provide a Quarterly Report containing the names of contractor employees actively serving on the contract, submitted to PSD-Industrial-Security@ice.dhs.gov. | 97 |
| Complete Non-Disclosure Agreement | Ensure all contract personnel complete the DHS Form 11000-6-Sensitive but Unclassified Information Non-Disclosure Agreement within 10 calendar days of the entry-on-duty date. | 97 |
| Appoint Corporate Security Officer | Appoint a senior official to act as the Corporate Security Officer to interface with OPR PSD on all security matters. | 98 |

## Key Dates
| Event | Date | Page |
| --- | --- | --- |
| Period of Performance End | September 7, 2026 | 3 |
| Period of Performance Start | September 8, 2025 | 3 |
| Questions Due | June 2, 2025 at 1:00 PM EST | 5 |
| Quote Due | June 23, 2025 at 1:00 PM EST | 5 |
| Base Period End | 08/31/2026 | 9 |
| Base Period Start | 09/01/2025 | 9 |
| Option Period 1 End | 08/31/2027 | 9 |
| Option Period 1 Start | 09/01/2026 | 9 |
| Option Period 2 End | 08/31/2028 | 9 |
| Option Period 2 Start | 09/01/2027 | 9 |
| Option Period 3 End | 08/31/2029 | 9 |
| Option Period 3 Start | 09/01/2028 | 9 |
| Option Period 4 End | 08/31/2030 | 9 |
| Option Period 4 Start | 09/01/2029 | 9 |
| Final monthly plan submission | 10 business days after BPA Call award | 26 |
| Contract Award | Date of contract award | 31 |
| Security Vetting Documentation Submission | Within 10 days of notification of initiation of an Electronic Application for Background Investigations (eAPP) | 31 |
| Quarterly Report Submission | No later than the 10th day of each January, April, July, and October | 35 |
| Security Authorization Package Submission | At least 30 days prior to the date of operation of the IT system | 39 |
| ATO Renewal Submission | At least 90 days before the ATO expiration date | 40 |
| Annual Training Completion | October 31st of each year | 46 |
| Initial Training Completion | 30 days after contract award | 46 |
| Submission of Security Vetting Documentation | 10 days after notification of initiation | 50 |
| NDA Completion | Within 10 calendar days of entry-on-duty date | 54 |
| Monthly Progress Report Submission | 5th business day after the end of the month | 56 |
| Prohibition Effective Date | August 13, 2019 | 64 |
| Prohibition Effective Date for Contracting with Entities Using Covered Equipment | August 13, 2020 | 68 |
| Contract Extension Notice | Within 60 days of the end of the period of performance | 71 |
| Privacy Training Completion | Within 30 days of contract award and annually by October 31st | 71 |
| Credit Monitoring Services Period | Not less than 18 months from the date the individual is notified | 81 |
| Notification to Affected Individuals | No later than 5 business days after being directed by the Contracting Officer | 81 |
| Initial CUI Training | Within 60 days of contract award | 85 |
| Annual IT Security Awareness Training | Completed within 30 days of contract award and annually by October 31st | 88 |
| Annual training certificate submission | October 31st of each year | 89 |
| Submission of initial training certificates | 30 days after contract award | 89 |
| Submission of security vetting documentation | Within 10 days of notification of initiation of an Electronic Application for Background Investigations | 94 |
'''

def _dedupe_consecutive_lines(text: str) -> str:
    """Remove consecutive duplicate lines while preserving order.
    Keeps the first occurrence when the same normalized line repeats back-to-back.
    """
    lines = text.splitlines()
    cleaned = []
    prev_norm = None
    for line in lines:
        norm = line.strip().lower()
        if norm == prev_norm:
            # skip exact consecutive duplicate
            continue
        cleaned.append(line)
        prev_norm = norm
    return "\n".join(cleaned)


def _msg_to_text(msg) -> str:
    try:
        d = msg.to_dict() if hasattr(msg, "to_dict") else None
    except Exception:
        d = None
    role = None
    name = None
    content = None
    if isinstance(d, dict):
        role = d.get("role")
        name = d.get("name")
        content = d.get("content")
    else:
        role = getattr(msg, "role", None)
        name = getattr(msg, "name", None)
        content = getattr(msg, "content", None)
    # Normalize content to string
    if content is None:
        content_str = ""
    elif isinstance(content, (list, dict)):
        import json
        try:
            content_str = json.dumps(content, ensure_ascii=False, indent=2)
        except Exception:
            content_str = str(content)
    else:
        content_str = str(content)
    header = f"[{role or 'unknown'}{(' - ' + name) if name else ''}]"
    return f"{header}\n{content_str}".strip()


def _format_transcript(messages) -> str:
    parts = ["Agent Conversation Transcript", ""]
    for m in messages:
        parts.append(_msg_to_text(m))
        parts.append("\n---\n")
    return "\n".join(parts).rstrip()


def main():
    from datetime import datetime
    dt_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    session_id = f"maestor_{dt_str}"

    print("Running team to generate proposal...")
    response = maestor_team.run(sample_rfp, session_id=session_id, retries=2)

    # Prefer the content field rather than repr to avoid duplicated metadata
    raw_text = getattr(response, "content", str(response)) or ""

    # Light cleanup: drop consecutive duplicate lines (common at the start)
    cleaned_text = _dedupe_consecutive_lines(raw_text)

    # Save main consolidated output
    out_filename = f"proposal_clean_{dt_str}.txt"
    with open(out_filename, "w", encoding="utf-8") as f:
        f.write(cleaned_text)

    # Save full conversation transcript separately
    try:
        # Prefer full session history if available
        messages = maestor_team.get_messages_for_session(session_id=session_id) or response.messages or []
    except Exception:
        messages = response.messages or []
    transcript_text = _format_transcript(messages) if messages else "(No conversation messages captured)"
    transcript_filename = f"proposal_conversation_{dt_str}.md"
    with open(transcript_filename, "w", encoding="utf-8") as tf:
        tf.write(transcript_text)

    print(f"Saved clean output to {out_filename}\nSaved conversation transcript to {transcript_filename}")

# def main():
#     console = Console(record=True)
#     maestor_team.print_response(
#         sample_rfp,
#         stream=True,
#         show_full_reasoning=True,
#         stream_intermediate_steps=True,
#         console=console,
#     )
#     console.save_text("proposal_pretty.txt")
#     print("Saved pretty output to proposal_pretty.txt")


if __name__ == "__main__":
    main()
    
