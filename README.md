# RFP Extractor and Chat Assistant

A powerful tool for analyzing Request for Proposal (RFP) documents, extracting structured information, and providing an AI-powered chat interface to interact with the document content.

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://streamlit.io/gallery)

![RFP Analyzer Demo](https://via.placeholder.com/800x400?text=RFP+Analyzer+Demo)

## 📋 Overview

The RFP Extractor is a suite of tools designed to help proposal teams quickly analyze, extract, and understand the content of RFP documents. By leveraging AWS services and OpenAI's language models, the application processes PDF documents to extract critical information such as customer details, scope of work, requirements, key dates, and more.

It includes two main applications:
- **RFP Extractor App**: Focuses on document processing and data extraction
- **RFP Chat Assistant**: Provides a conversational interface to ask questions about the RFP

## ✨ Features

### Core Features
- **PDF Processing**: Upload and analyze PDF-based RFP documents
- **Structured Data Extraction**: Automatically identify and categorize key RFP components
- **AI-Powered Chat**: Ask natural language questions about the RFP content
- **Hybrid Processing**: Uses AWS Lambda for large documents with local processing fallback

### Data Extraction
- Customer and organization information
- Scope of work identification
- Requirements extraction and categorization
- Key dates and deadlines
- Major tasks and deliverables

### User Experience
- Modern, intuitive user interface
- Clear visualization of extracted RFP data
- Interactive chat with context-aware responses
- Error handling and graceful fallbacks

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

### Running the Applications

#### RFP Extractor App
```bash
streamlit run rfp_extractor_app.py
```

#### RFP Chat Assistant
```bash
streamlit run rfp_chat_assistant.py
```

## 📖 Usage

### RFP Extractor App

1. Launch the application
2. Upload a PDF RFP document
3. Select sections to extract (or choose "all")
4. Click "Process PDF"
5. View the structured extraction results

### RFP Chat Assistant

1. Launch the application
2. Enter your OpenAI API key in the sidebar
3. Upload a PDF RFP document
4. Click "Process New RFP"
5. Once processed, ask questions in the chat interface
6. Expand "View RFP Analysis" to see the structured data extraction

## ⚙️ Configuration

The applications can be configured via the Streamlit interface:

- **OpenAI API Key**: Required for the Chat Assistant
- **AWS Region**: Hard-coded to "us-east-1" (can be modified in code)
- **S3 Bucket**: Hard-coded to "my-rfp-bucket" (can be modified in code)
- **Lambda URL**: Hard-coded in the application code

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
Use Docker to containerize the applications:

```bash
docker build -t rfp-extractor .
docker run -p 8501:8501 rfp-extractor
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