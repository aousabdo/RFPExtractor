# Enterprise RFP Analyzer

A powerful enterprise-grade tool for analyzing Request for Proposal (RFP) documents, extracting structured information, and providing an AI-powered chat interface to interact with the document content.

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://streamlit.io/gallery)

![RFP Analyzer Demo](https://via.placeholder.com/800x400?text=RFP+Analyzer+Demo)

## 📋 Overview

The Enterprise RFP Analyzer is designed to help proposal teams quickly analyze, extract, and understand the content of RFP documents. By leveraging AWS services and OpenAI's language models, the application processes PDF documents to extract critical information such as customer details, scope of work, requirements, key dates, and more.

The main application:
- **Enterprise RFP Assistant**: A comprehensive enterprise-grade application that combines document processing, data extraction, and an AI-powered chat interface for RFP analysis

## ✨ Features

### Core Features
- **PDF Processing**: Upload and analyze PDF-based RFP documents
- **Structured Data Extraction**: Automatically identify and categorize key RFP components
- **AI-Powered Chat**: Ask natural language questions about the RFP content
- **Hybrid Processing**: Uses AWS Lambda for large documents with local processing fallback
- **PDF Report Generation**: Export comprehensive analysis reports in professional PDF format

### Enterprise Features
- **Professional UI**: Modern enterprise-grade user interface with clean design
- **Advanced Data Visualization**: Interactive tabs, cards, and statistics dashboard
- **Requirements Categorization**: Automatic grouping of requirements by category
- **Timeline Analysis**: Visual representation of key dates and deadlines
- **Integrated Experience**: Combined extraction, analysis, and chat interface in a single application

### Data Extraction
- Customer and organization information
- Scope of work identification
- Requirements extraction and categorization
- Key dates and deadlines
- Major tasks and deliverables

### User Experience
- Modern, intuitive enterprise-style interface
- Clear visualization with metrics dashboard
- Interactive organization of extracted RFP data
- Contextual AI chat with RFP-specific knowledge
- Error handling with graceful fallback to local processing

## 🏗️ Architecture

The application uses a hybrid cloud/local architecture:

```
┌───────────┐     ┌───────────┐     ┌───────────┐
│ Streamlit │ ──▶ │  AWS S3   │ ──▶ │AWS Lambda │
│ Frontend  │     │  Storage  │     │ Processing│
└───────────┘     └───────────┘     └───────────┘
      │                                   │
      │                                   ▼
      │                            ┌───────────┐
      │                            │ Structured│
      │                            │   Data    │
      │                            └───────────┘
      │                                   │
      ▼                                   ▼
┌───────────┐                      ┌───────────┐
│  Local    │ ◀────────────────── │   Chat    │
│Processing │                      │ Interface │
└───────────┘                      └───────────┘
```

- **Frontend**: Streamlit-based web interface
- **Processing**: AWS Lambda for scalable processing or local processing fallback
- **Storage**: AWS S3 for temporary document storage
- **AI Models**: OpenAI API for natural language processing and chat

## 🚀 Getting Started

### Prerequisites
- Python 3.8 or higher
- AWS account (optional for Lambda/S3 features)
- OpenAI API key

### Installation

1. Clone the repository:
```bash
git clone https://github.com/aousabdo/RFPExtractor.git
cd RFPExtractor
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables (optional for AWS integration):
```bash
export OPENAI_API_KEY=your_api_key_here
```

### Running the Application

#### Enterprise RFP Assistant (Recommended)
```bash
streamlit run enterprise_rfp_assistant.py
```

#### Legacy Applications
```bash
streamlit run rfp_extractor_app.py   # Basic RFP Extractor
streamlit run rfp_chat_assistant.py  # Basic Chat Assistant
```

## 📖 Usage

### Enterprise RFP Assistant (Recommended)

1. Launch the application: `streamlit run enterprise_rfp_assistant.py`
2. Enter your OpenAI API key in the sidebar
3. Upload a PDF RFP document
4. Click "Process RFP"
5. View the comprehensive analysis with:
   - Key metrics dashboard
   - Detailed requirements organized by category 
   - Tasks extracted from the document
   - Timeline of key dates and deadlines
6. Use the integrated chat assistant to ask questions about the RFP
7. Export a professional PDF report of the analysis

### Legacy Applications

#### RFP Extractor App

1. Launch the application
2. Upload a PDF RFP document
3. Select sections to extract (or choose "all")
4. Click "Process PDF"
5. View the structured extraction results

#### RFP Chat Assistant

1. Launch the application
2. Enter your OpenAI API key in the sidebar
3. Upload a PDF RFP document
4. Click "Process New RFP"
5. Once processed, ask questions in the chat interface
6. Expand "View RFP Analysis" to see the structured data extraction

## ⚙️ Configuration

The Enterprise RFP Assistant is configured via the Streamlit interface:

- **OpenAI API Key**: Required for analysis and chat functionality
- **AWS Region**: Hard-coded to "us-east-1" (can be modified in code)
- **S3 Bucket**: Hard-coded to "my-rfp-bucket" (can be modified in code)
- **Lambda URL**: Hard-coded in the application code

The assistant automatically falls back to local processing if AWS services are unavailable, ensuring a seamless experience even without cloud connectivity.

## 🛠️ Deployment Options

### Local Deployment
Run the applications on your local machine as described in the Getting Started section.

### EC2 Deployment
1. Launch an EC2 instance
2. Install dependencies and clone the repository
3. Set up a web server (Nginx) with HTTPS
4. Configure environment variables
5. Run the applications with a process manager like PM2 or Supervisor

### Docker Deployment
Use Docker to containerize the Enterprise RFP Assistant:

```bash
# Build the Docker image
docker build -t enterprise-rfp-analyzer .

# Run the container
docker run -p 8501:8501 -e OPENAI_API_KEY=your_api_key_here enterprise-rfp-analyzer

# Or mount a volume for persistent storage
docker run -p 8501:8501 -e OPENAI_API_KEY=your_api_key_here -v $(pwd)/data:/app/data enterprise-rfp-analyzer
```

## 🔒 Security Considerations

- API keys are handled through environment variables or secure user input
- AWS credentials are managed via standard AWS credential providers
- HTTPS recommended for production deployments
- Authentication should be added for multi-user deployments

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 📞 Contact

If you have any questions or feedback, please open an issue on GitHub. 