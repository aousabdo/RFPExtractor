#!/usr/bin/env python3

import boto3
import botocore
import requests
from requests_aws4auth import AWS4Auth
import argparse
import os
import json
import logging
from typing import Dict, Any, List, Optional
from botocore.exceptions import ClientError

# Configure logging
logger = logging.getLogger(__name__)

def get_aws_session(aws_region):
    """
    Tries to create a session with the default profile. If it fails, switches to the 'rfp' profile.
    
    Args:
        aws_region (str): The AWS region to use (e.g., 'us-east-1')
    
    Returns:
        boto3.Session: An AWS session object
    
    Exits:
        If both default and 'rfp' profiles fail to authenticate
    """
    try:
        # Attempt to use the default profile
        session = boto3.Session(region_name=aws_region)
        credentials = session.get_credentials()
        
        if credentials is None or credentials.access_key is None:
            raise botocore.exceptions.NoCredentialsError()

        print("Using AWS default profile")
        return session

    except (botocore.exceptions.NoCredentialsError, botocore.exceptions.PartialCredentialsError):
        print("Default AWS profile failed. Trying 'rfp' profile...")
        try:
            session = boto3.Session(profile_name="rfp", region_name=aws_region)
            credentials = session.get_credentials()
            
            if credentials is None or credentials.access_key is None:
                raise botocore.exceptions.NoCredentialsError()

            print("Using AWS profile: rfp")
            return session
        except Exception as e:
            print(f"Error: Unable to authenticate with AWS. {str(e)}")
            exit(1)  # Exit the script if both profiles fail

def upload_to_s3(
    file_path: str,
    bucket: str,
    object_name: str,
    region: str = "us-east-1"
) -> bool:
    """
    Upload a file to an S3 bucket.

    Args:
        file_path (str): Path to file to upload
        bucket (str): Bucket to upload to
        object_name (str): S3 object name
        region (str): AWS region name

    Returns:
        bool: True if file was uploaded, else False
    """
    try:
        logger.info(f"Uploading {file_path} to {bucket}/{object_name}")
        s3_client = boto3.client('s3', region_name=region)
        
        with open(file_path, "rb") as f:
            s3_client.upload_fileobj(f, bucket, object_name)
            
        logger.info("Upload successful")
        return True
        
    except ClientError as e:
        logger.error(f"Upload failed: {str(e)}")
        return False

def invoke_lambda(
    lambda_url: str,
    bucket: str,
    key: str,
    aws_region: str,
    sections: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Invoke Lambda function to process uploaded PDF with proper AWS authentication.

    Args:
        lambda_url (str): Lambda function URL
        bucket (str): S3 bucket containing PDF
        key (str): S3 key (object name) of PDF
        aws_region (str): AWS region for authentication
        sections (List[str], optional): Sections to extract

    Returns:
        Dict[str, Any]: Processed results from Lambda
    """
    if not lambda_url:
        raise ValueError("Lambda URL not provided")

    try:
        logger.info(f"Invoking Lambda via URL: {lambda_url}")
        
        # Get AWS session with credentials
        session = get_aws_session(aws_region)
        credentials = session.get_credentials()
        
        # Create request auth with AWS Signature v4
        auth = AWS4Auth(
            credentials.access_key,
            credentials.secret_key,
            aws_region,
            'lambda',
            session_token=credentials.token
        )
        
        # Use the correct parameter names that the Lambda function expects
        payload = {
            "s3_bucket": bucket,
            "s3_key": key,
            "sections": sections if sections else ["all"]
        }
            
        # Include auth in the request
        response = requests.post(lambda_url, json=payload, auth=auth)
        response.raise_for_status()
        
        logger.info("Lambda invocation successful")
        return response.json()
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Lambda invocation failed: {str(e)}")
        raise

def upload_and_process_pdf(
    pdf_path: str,
    s3_bucket: str,
    s3_key: str,
    aws_region: str,
    lambda_url: str,
    sections: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Upload PDF to S3 and process it via Lambda.

    Args:
        pdf_path (str): Local path to PDF file
        s3_bucket (str): Target S3 bucket
        s3_key (str): Target S3 key (object name)
        aws_region (str): AWS region
        lambda_url (str): Lambda function URL
        sections (List[str], optional): Sections to extract

    Returns:
        Dict[str, Any]: Processed results

    Raises:
        Exception: If upload or processing fails
    """
    logger.info(f"Starting upload and process for {pdf_path}")
    
    # Upload to S3
    if not upload_to_s3(pdf_path, s3_bucket, s3_key, aws_region):
        raise Exception("Failed to upload PDF to S3")
        
    # Process via Lambda
    try:
        result = invoke_lambda(lambda_url, s3_bucket, s3_key, aws_region, sections)
        logger.info("Processing complete")
        return result
        
    except Exception as e:
        logger.error(f"Processing failed: {str(e)}")
        raise Exception(f"Failed to process PDF: {str(e)}")

def main():
    """
    Command-line interface for uploading and processing a PDF.
    """
    parser = argparse.ArgumentParser(description="Upload PDF to S3 and process with Lambda")
    parser.add_argument("pdf_path", help="Path to the PDF file to process")
    parser.add_argument("--bucket", required=True, help="S3 bucket name")
    parser.add_argument("--key", help="S3 object key (defaults to filename)")
    parser.add_argument("--region", default="us-east-1", help="AWS region (default: us-east-1)")
    parser.add_argument("--lambda-url",
                       default=os.getenv("AWS_LAMBDA_URL", ""),
                       help="Lambda function URL")
    parser.add_argument("--sections", nargs='+', default=["all"], 
                       help="Sections to process (default: ['all'])")
    
    args = parser.parse_args()

    # Validate PDF file exists
    if not os.path.isfile(args.pdf_path):
        print(f"Error: The file '{args.pdf_path}' does not exist.")
        return

    if not args.lambda_url:
        print("Error: Lambda URL is required. Set AWS_LAMBDA_URL or pass --lambda-url.")
        return
    
    # Run the upload and processing
    try:
        result = upload_and_process_pdf(
            pdf_path=args.pdf_path,
            s3_bucket=args.bucket,
            s3_key=args.key,
            aws_region=args.region,
            lambda_url=args.lambda_url,
            sections=args.sections
        )
        print(f"Processing result: {result}")
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    # Configure logging for CLI usage
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    main()