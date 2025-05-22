from setuptools import setup, find_packages

setup(
    name="rfp_analyzer",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "streamlit>=1.31.0",
        "openai>=1.2.0",
        "boto3>=1.34.0",
        "requests>=2.31.0",
        "pymongo>=4.5.0",
        "requests_aws4auth",
        "python-dotenv>=1.0.0",
        "PyMuPDF>=1.22.5",
        "reportlab>=3.6.12",
        "plotly>=5.13.0",
        "pandas>=2.0.0",
    ],
    author="Your Name",
    author_email="your.email@example.com",
    description="Enterprise RFP Analyzer for extracting structured information from RFPs",
    keywords="rfp, nlp, analysis, streamlit",
    python_requires=">=3.8",
)
