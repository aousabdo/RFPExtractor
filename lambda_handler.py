import json
import os
import boto3
import logging
from typing import Dict, Any
from rfp_filter import run_filter

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3_client = boto3.client('s3')

def download_from_s3(bucket: str, key: str) -> str:
    """Download file from S3 to Lambda's temp directory.
    
    Args:
        bucket: S3 bucket name
        key: S3 object key
        
    Returns:
        str: Local path to downloaded file
    """
    local_path = f"/tmp/{os.path.basename(key)}"
    logger.info(f"Downloading {key} from bucket {bucket} to {local_path}")
    s3_client.download_file(bucket, key, local_path)
    return local_path

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """AWS Lambda handler for RFP processing.
    
    Expected event format:
    {
        "s3_bucket": "my-bucket",
        "s3_key": "path/to/document.pdf",
        "sections": ["customer", "scope"]  # Optional, defaults to ["all"]
    }
    
    Returns:
        Dict containing API Gateway response with extracted RFP data
    """
    logger.info(f"Received event: {json.dumps(event)}")

    try:
        # Validate input
        if 's3_bucket' not in event or 's3_key' not in event:
            logger.error("Missing required parameters: s3_bucket and s3_key")
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'error': 'Missing required parameters: s3_bucket and s3_key'
                })
            }

        # Get parameters
        bucket = event['s3_bucket']
        key = event['s3_key']
        
        # Handle sections parameter with validation
        sections = event.get('sections')
        if sections is not None:
            if not isinstance(sections, (str, list)):
                logger.error(f"Invalid sections parameter type: {type(sections)}")
                return {
                    'statusCode': 400,
                    'body': json.dumps({
                        'error': 'sections parameter must be a string or list of strings'
                    })
                }
        else:
            sections = ['all']
            
        logger.info(f"Processing PDF from s3://{bucket}/{key} with sections: {sections}")

        # Download PDF from S3
        pdf_path = download_from_s3(bucket, key)
        logger.info(f"Successfully downloaded PDF to {pdf_path}")

        # Process the PDF
        logger.info("Starting RFP processing")
        result = run_filter(pdf_path, sections)
        logger.info("Successfully processed RFP")

        # Clean up
        if os.path.exists(pdf_path):
            logger.info(f"Cleaning up temporary file: {pdf_path}")
            os.remove(pdf_path)

        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json'
            },
            'body': json.dumps({
                'result': result
            })
        }

    except Exception as e:
        logger.error(f"Error processing RFP: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e)
            })
        } 