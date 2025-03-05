# Enterprise RFP Analyzer

A powerful enterprise-grade tool for analyzing Request for Proposal (RFP) documents, extracting structured information, and providing an AI-powered chat interface to interact with the document content.

<!-- [![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://streamlit.io/gallery) -->

<!-- ![RFP Analyzer Demo](https://via.placeholder.com/800x400?text=RFP+Analyzer+Demo) -->

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
- **Document Management**: Store, view, and manage your RFP documents with a user-friendly interface

### Enterprise Features
- **Professional UI**: Modern enterprise-grade user interface with clean design
- **Advanced Data Visualization**: Interactive tabs, cards, and statistics dashboard
- **Requirements Categorization**: Automatic grouping of requirements by category
- **Timeline Analysis**: Visual representation of key dates and deadlines
- **Integrated Experience**: Combined extraction, analysis, and chat interface in a single application
- **User Authentication**: Secure login system with role-based access control
- **Document Library**: Persistent storage for all processed RFP documents
- **Multi-session Support**: Resume analysis from previous sessions

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
- Document management interface with status indicators
- Secure document deletion with confirmation flow

## 🏗️ Architecture

The application uses a hybrid cloud/local architecture with MongoDB for persistent storage:

```
┌───────────┐     ┌───────────┐     ┌───────────┐
│ Streamlit │ ──▶ │  AWS S3   │ ──▶ │AWS Lambda │
│ Frontend  │     │  Storage  │     │ Processing│
└───────────┘     └───────────┘     └───────────┘
      │                │                  │
      │                │                  ▼
      │                │           ┌───────────┐
      │                │           │ Structured│
      │                │           │   Data    │
      │                │           └───────────┘
      │                │                  │
      ▼                ▼                  ▼
┌───────────┐    ┌───────────┐     ┌───────────┐
│  Local    │ ◀─ │ MongoDB   │ ◀── │   Chat    │
│Processing │    │ Database  │     │ Interface │
└───────────┘    └───────────┘     └───────────┘
                       │
                       ▼
                ┌───────────┐
                │ Document  │
                │ Management│
                └───────────┘
```

- **Frontend**: Streamlit-based web interface
- **Processing**: AWS Lambda for scalable processing or local processing fallback
- **Storage**: 
  - AWS S3 for document storage
  - MongoDB for persistent metadata and analysis results
- **AI Models**: OpenAI API for natural language processing and chat
- **Authentication**: MongoDB-based user authentication system

## 🚀 Getting Started

### Prerequisites
- Python 3.8 or higher
- MongoDB (local or MongoDB Atlas)
- AWS account (for Lambda/S3 features)
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

4. Configure environment variables:
Create a `.env` file in the root directory with the following variables:
```
OPENAI_API_KEY=your_api_key_here
MONGODB_URI=mongodb+srv://username:password@cluster.mongodb.net/?retryWrites=true&w=majority&tls=true&tlsAllowInvalidCertificates=false
MONGODB_DB=rfp_analyzer
ADMIN_USERNAME=admin
ADMIN_PASSWORD=secure_password
S3_BUCKET=my-rfp-bucket
AWS_REGION=us-east-1
```

### Running the Application

#### Enterprise RFP Assistant (Recommended)
```bash
streamlit run enterprise_rfp_assistant.py
```

#### With Docker
```bash
docker-compose up -d
```

## 📖 Usage

### Enterprise RFP Assistant

1. Launch the application: `streamlit run enterprise_rfp_assistant.py`
2. Log in with your credentials
3. Configure your OpenAI API key in the settings (if not set in environment variables)
4. Navigate through the main tabs:
   - **Overview**: Dashboard with key metrics
   - **Requirements**: Detailed requirements organized by category
   - **Tasks**: Key tasks extracted from the document
   - **Timeline**: Visual timeline of key dates and deadlines
   - **Documents**: Manage your uploaded RFP documents

### Document Management Workflow

The application provides a comprehensive document management system:

#### Uploading Documents
1. Navigate to the main page
2. Use the "Upload RFP Document" section to select a PDF file
3. Click "Process RFP" to analyze the document
4. The document will be stored in the document library with its analysis results

#### Viewing Documents
1. Navigate to the "Documents" tab
2. Browse your uploaded documents with details like:
   - Filename
   - Upload date
   - File size
   - Processing status
3. Click the "View" button (👁️) on any document to load its analysis

#### Managing Documents
The Documents tab provides several actions for each document:
- **View**: Load the document analysis for chat and exploration
- **Download**: Download the original document via a temporary link
- **Delete**: Remove the document from the system (requires confirmation)

#### Deletion Workflow
1. Click the delete button (🗑️) on a document
2. A confirmation dialog appears at the top of the page
3. Click "Yes, Delete" to confirm or "Cancel" to abort
4. After deletion, the document list is automatically refreshed

### Chat Interface

Once a document is loaded:
1. The chat interface is available in the main view
2. Ask natural language questions about the RFP content
3. The AI assistant provides context-aware responses based on the document analysis
4. Previous chat history is cleared when loading a new document

## ⚙️ Configuration

### Environment Variables

The application is configured via environment variables:

| Variable | Description | Required |
|----------|-------------|----------|
| `OPENAI_API_KEY` | Your OpenAI API key | Yes |
| `MONGODB_URI` | Connection string for MongoDB | Yes |
| `MONGODB_DB` | MongoDB database name | Yes |
| `ADMIN_USERNAME` | Admin username | Yes |
| `ADMIN_PASSWORD` | Admin password | Yes |
| `S3_BUCKET` | AWS S3 bucket name | Yes for S3 storage |
| `AWS_REGION` | AWS region | Yes for AWS services |
| `AWS_LAMBDA_URL` | URL for AWS Lambda function | Optional |

### MongoDB Configuration

The application requires MongoDB for:
- User authentication
- Document metadata storage
- Analysis results persistence

For MongoDB Atlas:
- Ensure TLS is enabled with proper certificates
- Set the connection string with appropriate TLS parameters
- Specify the database name in environment variables

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
Use Docker and docker-compose to containerize the Enterprise RFP Assistant:

```bash
# Start the application stack
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the application
docker-compose down
```

The docker-compose.yml file includes:
- Application container
- MongoDB container (or connection to external MongoDB)
- Proper networking and volume configuration

## 🔒 Security Considerations

- API keys are handled through environment variables or secure user input
- AWS credentials are managed via standard AWS credential providers
- MongoDB connections use TLS for secure data transmission
- Document deletion requires confirmation to prevent accidental data loss
- User authentication with secure password handling
- HTTPS recommended for production deployments

## 💾 Data Management

### Document Storage
Documents are stored in:
1. **S3**: Original PDF files with secure access controls
2. **MongoDB**: Document metadata and analysis results

### Metadata Tracked
For each document, the system maintains:
- Original filename
- Upload timestamp
- File size
- Processing status
- User ID of the uploader
- S3 storage location
- Analysis results

### Document Lifecycle
1. **Upload**: Temporary storage during processing
2. **Processing**: Analysis by AWS Lambda or local processor
3. **Storage**: Permanent storage in S3 with metadata in MongoDB
4. **Retrieval**: Access via the Documents tab
5. **Deletion**: Removal from both S3 and MongoDB when deleted

## 🔍 Troubleshooting

### MongoDB Connection Issues
- Verify MongoDB connection string format
- Ensure TLS settings are correct
- Check network connectivity to MongoDB server

### Document Processing Failures
- Verify AWS credentials and permissions
- Check S3 bucket existence and accessibility
- Ensure Lambda function is deployed correctly

### UI Issues
- Clear browser cache
- Restart the Streamlit application
- Check for JavaScript console errors

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 📞 Contact

If you have any questions or feedback, please open an issue on GitHub. 