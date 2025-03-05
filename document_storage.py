#!/usr/bin/env python3
import os
import uuid
import logging
import boto3
import botocore
from typing import Dict, Any, Optional, List
from datetime import datetime
from bson.objectid import ObjectId

# Configure logging
logger = logging.getLogger(__name__)

class DocumentStorage:
    def __init__(self, db, aws_region="us-east-1", s3_bucket="my-rfp-bucket"):
        """
        Initialize the DocumentStorage class with a MongoDB database instance
        
        Args:
            db: MongoDB database instance
            aws_region: AWS region for S3
            s3_bucket: S3 bucket name for document storage
        """
        self.db = db
        self.documents = db.rfp_documents
        self.aws_region = aws_region
        self.s3_bucket = s3_bucket
        
        # Create necessary indexes
        self._setup_indexes()
        
        # Initialize S3 client
        try:
            self.s3_client = boto3.client('s3', region_name=aws_region)
            logger.info(f"S3 client initialized for region {aws_region}")
        except Exception as e:
            logger.error(f"Failed to initialize S3 client: {str(e)}")
            self.s3_client = None
    
    def _setup_indexes(self):
        """Create necessary database indexes"""
        try:
            # Index for user_id to quickly find documents for a user
            self.documents.create_index("user_id")
            
            # Index for uploaded_at to sort by date
            self.documents.create_index("uploaded_at")
            
            # Compound index for user and filename
            self.documents.create_index([("user_id", 1), ("original_filename", 1)])
            
            logger.info("Document collection indexes created/verified")
        except Exception as e:
            logger.error(f"Failed to create indexes: {str(e)}")
    
    def store_document(self, 
                      user_id: str, 
                      file_path: str, 
                      original_filename: str,
                      file_content: Optional[bytes] = None,
                      metadata: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """
        Store a document in S3 and record metadata in MongoDB
        
        Args:
            user_id: User ID who uploaded the document
            file_path: Path to the file (if file_content is None)
            original_filename: Original filename
            file_content: File content as bytes (optional, if provided file_path will be ignored)
            metadata: Additional metadata to store
            
        Returns:
            str: Document ID if successful, None otherwise
        """
        try:
            # Generate a unique S3 key
            timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
            unique_id = str(uuid.uuid4())[:8]
            
            # Clean the filename to make it S3-safe
            safe_filename = "".join(c if c.isalnum() or c in ['.', '_', '-'] else '_' for c in original_filename)
            
            s3_key = f"users/{user_id}/rfps/{timestamp}_{unique_id}_{safe_filename}"
            
            # Upload to S3
            try:
                if file_content:
                    self.s3_client.put_object(
                        Bucket=self.s3_bucket,
                        Key=s3_key,
                        Body=file_content
                    )
                else:
                    with open(file_path, 'rb') as file_data:
                        self.s3_client.upload_fileobj(
                            file_data,
                            self.s3_bucket,
                            s3_key
                        )
                logger.info(f"File uploaded to S3: {s3_key}")
            except Exception as e:
                logger.error(f"Failed to upload file to S3: {str(e)}")
                return None
            
            # Create document record in MongoDB
            document_data = {
                "user_id": user_id,
                "original_filename": original_filename,
                "s3_bucket": self.s3_bucket,
                "s3_key": s3_key,
                "uploaded_at": datetime.utcnow(),
                "status": "uploaded",  # initial status
                "file_size": os.path.getsize(file_path) if file_path and os.path.exists(file_path) else None,
                "metadata": metadata or {},
                "analysis_results": None,  # Will be populated after processing
                "processing_history": [
                    {
                        "timestamp": datetime.utcnow(),
                        "action": "upload",
                        "status": "success"
                    }
                ]
            }
            
            result = self.documents.insert_one(document_data)
            document_id = str(result.inserted_id)
            logger.info(f"Document record created with ID: {document_id}")
            
            return document_id
            
        except Exception as e:
            logger.error(f"Failed to store document: {str(e)}")
            return None
    
    def update_analysis_results(self, document_id: str, analysis_results: Dict[str, Any]) -> bool:
        """
        Update a document with analysis results
        
        Args:
            document_id: Document ID
            analysis_results: Analysis results to store
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            result = self.documents.update_one(
                {"_id": ObjectId(document_id)},
                {
                    "$set": {
                        "analysis_results": analysis_results,
                        "status": "processed"
                    },
                    "$push": {
                        "processing_history": {
                            "timestamp": datetime.utcnow(),
                            "action": "analysis",
                            "status": "success"
                        }
                    }
                }
            )
            
            if result.modified_count > 0:
                logger.info(f"Analysis results updated for document {document_id}")
                return True
            else:
                logger.warning(f"No document found with ID {document_id}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to update analysis results: {str(e)}")
            return False
    
    def get_document_by_id(self, document_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a document by ID
        
        Args:
            document_id: Document ID
            
        Returns:
            Dict: Document data if found, None otherwise
        """
        try:
            document = self.documents.find_one({"_id": ObjectId(document_id)})
            if document:
                # Convert ObjectId to string for JSON serialization
                document["_id"] = str(document["_id"])
                return document
            else:
                logger.warning(f"No document found with ID {document_id}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to get document: {str(e)}")
            return None
    
    def get_documents_for_user(self, 
                              user_id: str, 
                              limit: int = 100, 
                              skip: int = 0, 
                              sort_by: str = "uploaded_at", 
                              sort_order: int = -1) -> List[Dict[str, Any]]:
        """
        Get documents for a specific user
        
        Args:
            user_id: User ID
            limit: Maximum number of documents to return
            skip: Number of documents to skip (for pagination)
            sort_by: Field to sort by
            sort_order: Sort order (1 for ascending, -1 for descending)
            
        Returns:
            List: List of document data
        """
        try:
            cursor = self.documents.find(
                {"user_id": user_id}
            ).sort(
                sort_by, sort_order
            ).skip(skip).limit(limit)
            
            documents = []
            for document in cursor:
                # Convert ObjectId to string for JSON serialization
                document["_id"] = str(document["_id"])
                documents.append(document)
            
            return documents
                
        except Exception as e:
            logger.error(f"Failed to get documents for user: {str(e)}")
            return []
    
    def delete_document(self, document_id: str, user_id: Optional[str] = None) -> bool:
        """
        Delete a document from S3 and MongoDB
        
        Args:
            document_id: Document ID
            user_id: Optional user ID for permission check
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Add debug logging
            print(f"DEBUG DELETE: Attempting to delete document {document_id} for user {user_id}")
            logger.info(f"Attempting to delete document {document_id} for user {user_id}")
            
            # Validate input types
            print(f"DEBUG DELETE: document_id type: {type(document_id)}, value: {document_id}")
            print(f"DEBUG DELETE: user_id type: {type(user_id)}, value: {user_id}")
            
            try:
                # Try to convert to ObjectId and print
                obj_id = ObjectId(document_id)
                print(f"DEBUG DELETE: ObjectId conversion successful: {obj_id}")
            except Exception as e:
                print(f"DEBUG DELETE: ObjectId conversion FAILED: {str(e)}")
                # Try to fix it if possible
                if len(document_id) == 24:
                    print(f"DEBUG DELETE: Attempting ObjectId conversion with string length 24")
                else:
                    print(f"DEBUG DELETE: Invalid ObjectId format, length={len(document_id)}")
            
            # Get document data first for the S3 key
            query = {"_id": ObjectId(document_id)}
            if user_id:
                query["user_id"] = user_id  # Add user check if provided
            
            print(f"DEBUG DELETE: MongoDB query: {query}")
            
            # Test if the document exists
            doc_exists = self.documents.count_documents(query)
            print(f"DEBUG DELETE: Document count for query: {doc_exists}")
            
            document = self.documents.find_one(query)
            if not document:
                logger.warning(f"No document found with ID {document_id}")
                print(f"DEBUG DELETE: No document found with query {query}")
                
                # Try without user_id to see if that's the issue
                if user_id:
                    alt_query = {"_id": ObjectId(document_id)}
                    alt_doc = self.documents.find_one(alt_query)
                    if alt_doc:
                        print(f"DEBUG DELETE: Document found WITHOUT user_id filter. Document user_id: {alt_doc.get('user_id')}")
                    else:
                        print(f"DEBUG DELETE: Document not found even without user_id filter")
                
                return False
            
            # Log document details
            print(f"DEBUG DELETE: Found document: {document.get('original_filename')}, user_id: {document.get('user_id')}")
            logger.info(f"Found document: {document['original_filename']}, S3 key: {document.get('s3_key')}")
            
            # Delete from S3
            try:
                print(f"DEBUG DELETE: Deleting from S3: Bucket={document.get('s3_bucket')}, Key={document.get('s3_key')}")
                self.s3_client.delete_object(
                    Bucket=document["s3_bucket"],
                    Key=document["s3_key"]
                )
                logger.info(f"Deleted from S3: {document['s3_key']}")
                print(f"DEBUG DELETE: S3 deletion successful")
            except Exception as e:
                logger.error(f"Failed to delete from S3: {str(e)}")
                print(f"DEBUG DELETE: S3 deletion failed: {str(e)}")
                # Continue with MongoDB deletion even if S3 deletion fails
            
            # Delete from MongoDB
            print(f"DEBUG DELETE: Deleting from MongoDB with query: {{'_id': ObjectId('{document_id}')}}") 
            result = self.documents.delete_one({"_id": ObjectId(document_id)})
            print(f"DEBUG DELETE: MongoDB deletion result: {result.deleted_count}")
            
            if result.deleted_count > 0:
                logger.info(f"Document {document_id} deleted from MongoDB")
                print(f"DEBUG DELETE: Document deleted successfully")
                return True
            else:
                logger.warning(f"Failed to delete document {document_id} from MongoDB")
                print(f"DEBUG DELETE: MongoDB deletion reported 0 documents deleted")
                return False
                
        except Exception as e:
            logger.error(f"Failed to delete document: {str(e)}")
            print(f"DEBUG DELETE: Exception during deletion: {str(e)}")
            import traceback
            print(f"DEBUG DELETE: Traceback: {traceback.format_exc()}")
            return False
    
    def generate_presigned_url(self, document_id: str, user_id: Optional[str] = None, expiration: int = 3600) -> Optional[str]:
        """
        Generate a presigned URL for a document in S3
        
        Args:
            document_id: Document ID
            user_id: Optional user ID for permission check
            expiration: URL expiration time in seconds (default: 1 hour)
            
        Returns:
            str: Presigned URL if successful, None otherwise
        """
        try:
            # Get document data first for the S3 key
            query = {"_id": ObjectId(document_id)}
            if user_id:
                query["user_id"] = user_id  # Add user check if provided
                
            document = self.documents.find_one(query)
            if not document:
                logger.warning(f"No document found with ID {document_id}")
                return None
            
            # Generate presigned URL
            try:
                url = self.s3_client.generate_presigned_url(
                    'get_object',
                    Params={
                        'Bucket': document["s3_bucket"],
                        'Key': document["s3_key"]
                    },
                    ExpiresIn=expiration
                )
                logger.info(f"Generated presigned URL for document {document_id}")
                return url
            except Exception as e:
                logger.error(f"Failed to generate presigned URL: {str(e)}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to generate presigned URL: {str(e)}")
            return None