#!/usr/bin/env python3

import boto3
import botocore
import requests
from requests_aws4auth import AWS4Auth
import argparse
import os
import json

def get_aws_session(aws_region):
    """
    Tries to create a session with the default profile. If it fails, switches to the 'rfp' profile.
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

def upload_and_process_pdf(pdf_path, s3_bucket, s3_key=None, aws_region='us-east-1', 
                          lambda_url="https://jc2qj7smmranhdtbxkazthh3hq0ymkih.lambda-url.us-east-1.on.aws/",
                          sections=None):
    """
    Uploads a PDF to S3 and triggers Lambda processing
    """
    # Use filename as S3 key if not specified
    if s3_key is None:
        s3_key = os.path.basename(pdf_path)
    
    if sections is None:
        sections = ["all"]
        
    print(f"Starting process for PDF: {pdf_path}")
    
    # Get AWS session with fallback logic
    session = get_aws_session(aws_region)
    
    credentials = session.get_credentials()
    aws_auth = AWS4Auth(
        credentials.access_key,
        credentials.secret_key,
        aws_region,
        'lambda',
        session_token=credentials.token
    )
    
    # 2. S3 Upload
    print(f"Uploading to S3 bucket: {s3_bucket}, key: {s3_key}")
    s3_client = session.client('s3')
    
    try:
        s3_client.upload_file(pdf_path, s3_bucket, s3_key)
        print(f"✓ Upload successful: s3://{s3_bucket}/{s3_key}")
    except Exception as e:
        print(f"✗ S3 Upload Failed: {str(e)}")
        return
    
    # 3. Call the Lambda Function
    print("Calling Lambda function for processing...")
    payload = {
        "s3_bucket": s3_bucket,
        "s3_key": s3_key,
        "sections": sections
    }
    
    try:
        response = requests.post(lambda_url, json=payload, auth=aws_auth)
    
        if response.status_code == 200:
            print("✓ Lambda processing successful")
            try:
                result = response.json()
                print("\nProcessing Results:")
                print(json.dumps(result, indent=2))
                return result
            except json.JSONDecodeError:
                print("\nResponse (not JSON format):")
                print(response.text)
                return response.text
        else:
            print(f"✗ Lambda processing failed with status code: {response.status_code}")
            print(f"Error message: {response.text}")
            return None
    except requests.RequestException as e:
        print(f"✗ Lambda request failed: {str(e)}")
        return None

def main():
    parser = argparse.ArgumentParser(description="Upload PDF to S3 and process with Lambda")
    parser.add_argument("pdf_path", help="Path to the PDF file to process")
    parser.add_argument("--bucket", required=True, help="S3 bucket name")
    parser.add_argument("--key", help="S3 object key (defaults to filename)")
    parser.add_argument("--region", default="us-east-1", help="AWS region (default: us-east-1)")
    parser.add_argument("--lambda-url", 
                       default="https://jc2qj7smmranhdtbxkazthh3hq0ymkih.lambda-url.us-east-1.on.aws/",
                       help="Lambda function URL")
    parser.add_argument("--sections", nargs='+', default=["all"], 
                       help="Sections to process (default: ['all'])")
    
    args = parser.parse_args()
    
    # Validate PDF file exists
    if not os.path.isfile(args.pdf_path):
        print(f"Error: The file '{args.pdf_path}' does not exist.")
        return
    
    # Run the upload and processing
    upload_and_process_pdf(
        pdf_path=args.pdf_path,
        s3_bucket=args.bucket,
        s3_key=args.key,
        aws_region=args.region,
        lambda_url=args.lambda_url,
        sections=args.sections
    )

if __name__ == "__main__":
    main()
