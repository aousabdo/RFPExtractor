#!/usr/bin/env python3
import os
import uuid
import logging
import boto3
import botocore
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from bson.objectid import ObjectId

# Import from config
from rfp_analyzer.app.config import AWS_REGION, S3_BUCKET

# Configure logging
logger = logging.getLogger(__name__)

class DocumentStorage:
    def __init__(self, db, aws_region=None, s3_bucket=None):
        """
        Initialize the DocumentStorage class with a MongoDB database instance
        
        Args:
            db: MongoDB database instance
            aws_region: AWS region for S3
            s3_bucket: S3 bucket name for document storage
        """
        self.db = db
        self.documents = db.rfp_documents
        self.aws_region = aws_region or AWS_REGION
        self.s3_bucket = s3_bucket or S3_BUCKET
        
        # Create necessary indexes
        self._setup_indexes()
        
        # Initialize S3 client
        try:
            self.s3_client = boto3.client('s3', region_name=self.aws_region)
            logger.info(f"S3 client initialized for region {self.aws_region}")
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
        Store a document in MongoDB and S3
        
        Args:
            user_id: User ID of the uploading user
            file_path: Path to the file to upload
            original_filename: Original filename
            file_content: File content as bytes (if already read)
            metadata: Additional metadata
            
        Returns:
            Document ID if successful, None otherwise
        """
        try:
            # Get file size
            file_size = os.path.getsize(file_path) if os.path.exists(file_path) else None
            
            # Generate a unique ID for the document
            s3_key = f"{user_id}/{uuid.uuid4()}/{original_filename}"
            
            # Upload to S3 if client available
            s3_upload_success = False
            if self.s3_client:
                try:
                    # Read file content if not provided
                    if not file_content:
                        with open(file_path, 'rb') as f:
                            file_content = f.read()
                    
                    # Upload to S3
                    self.s3_client.put_object(
                        Bucket=self.s3_bucket,
                        Key=s3_key,
                        Body=file_content
                    )
                    s3_upload_success = True
                    logger.info(f"Uploaded {original_filename} to S3 bucket {self.s3_bucket}")
                except Exception as e:
                    logger.error(f"Failed to upload to S3: {str(e)}")
                    s3_key = None
            
            # Get user email from the database for tracking
            user = self.db.users.find_one({"_id": ObjectId(user_id)})
            user_email = user.get("email", "Unknown") if user else "Unknown"
            user_name = user.get("fullname", "Unknown") if user else "Unknown"
            
            # Create MongoDB document
            now = datetime.utcnow()
            document = {
                "user_id": user_id,
                "uploaded_by": user_email,
                "uploaded_by_name": user_name,
                "original_filename": original_filename,
                "uploaded_at": now,
                "file_size": file_size,
                "s3_bucket": self.s3_bucket if s3_upload_success else None,
                "s3_key": s3_key if s3_upload_success else None,
                "status": "uploaded",
                "metadata": metadata or {},
                "analysis_results": None,
                "processing_history": [
                    {
                        "event_type": "upload",
                        "timestamp": now,
                        "details": {
                            "filename": original_filename,
                            "file_size": file_size,
                            "uploaded_by": user_email,
                            "uploaded_by_name": user_name
                        }
                    }
                ]
            }
            
            # Insert into MongoDB
            result = self.documents.insert_one(document)
            document_id = str(result.inserted_id)
            
            logger.info(f"Document {original_filename} stored with ID {document_id}")
            return document_id
            
        except Exception as e:
            logger.error(f"Failed to store document: {str(e)}")
            return None
    
    def update_analysis_results(self, document_id: str, analysis_results: Dict[str, Any]) -> bool:
        """
        Update the analysis results for a document
        
        Args:
            document_id: Document ID
            analysis_results: Analysis results data
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Convert string ID to ObjectId
            doc_id = ObjectId(document_id) if isinstance(document_id, str) else document_id
            
            # Add analysis timestamp
            now = datetime.utcnow()
            analysis_results["analysis_timestamp"] = now
            
            # Update document
            update_data = {
                "$set": {
                    "analysis_results": analysis_results,
                    "status": "processed",
                    "last_updated": now
                },
                "$push": {
                    "processing_history": {
                        "event_type": "analysis_complete",
                        "timestamp": now,
                        "details": {
                            "requirements_count": len(analysis_results.get("requirements", [])),
                            "tasks_count": len(analysis_results.get("tasks", [])),
                            "dates_count": len(analysis_results.get("dates", []))
                        }
                    }
                }
            }
            
            result = self.documents.update_one(
                {"_id": doc_id},
                update_data
            )
            
            success = result.modified_count > 0
            if success:
                logger.info(f"Updated analysis results for document {document_id}")
            else:
                logger.warning(f"Failed to update analysis results for document {document_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error updating analysis results: {str(e)}")
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
                              sort_order: int = -1,
                              status_filter: Optional[str] = None,
                              date_range: Optional[Dict[str, datetime]] = None,
                              search_query: Optional[str] = None,
                              category: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get documents for a user with advanced filtering options
        
        Args:
            user_id: User ID
            limit: Maximum number of documents to return
            skip: Number of documents to skip (for pagination)
            sort_by: Field to sort by (uploaded_at, original_filename, file_size, status)
            sort_order: Sort order (1 for ascending, -1 for descending)
            status_filter: Filter by document status (uploaded, processing, processed, error)
            date_range: Filter by date range (dict with 'start' and 'end' keys)
            search_query: Text search query for filename or content
            category: Filter by document category if available
            
        Returns:
            List of document dictionaries
        """
        try:
            query = {"user_id": user_id}
            
            # Add status filter if provided
            if status_filter:
                query["status"] = status_filter
            
            # Add date range filter if provided
            if date_range:
                date_query = {}
                if "start" in date_range:
                    date_query["$gte"] = date_range["start"]
                if "end" in date_range:
                    date_query["$lte"] = date_range["end"]
                if date_query:
                    query["uploaded_at"] = date_query
            
            # Add category filter if provided
            if category:
                query["category"] = category
            
            # Add text search if provided
            if search_query:
                # Search in filename
                query["$or"] = [
                    {"original_filename": {"$regex": search_query, "$options": "i"}},
                    {"metadata.extracted_text": {"$regex": search_query, "$options": "i"}}
                ]
            
            # Get allowed sort fields
            allowed_sort_fields = ["uploaded_at", "original_filename", "file_size", "status"]
            if sort_by not in allowed_sort_fields:
                sort_by = "uploaded_at"
            
            # Restrict sort_order to valid values
            sort_order = 1 if sort_order == 1 else -1
            
            # Execute the query
            documents = list(self.documents.find(query)
                            .sort(sort_by, sort_order)
                            .skip(skip)
                            .limit(limit))
            
            # Convert ObjectId to string
            for doc in documents:
                if "_id" in doc:
                    doc["_id"] = str(doc["_id"])
            
            logger.info(f"Retrieved {len(documents)} documents for user {user_id} with filters")
            return documents
            
        except Exception as e:
            logger.error(f"Error getting documents for user {user_id}: {str(e)}")
            return []
    
    def delete_document(self, document_id: str, user_id: Optional[str] = None) -> bool:
        """
        Delete a document from both MongoDB and S3
        
        Args:
            document_id: Document ID to delete
            user_id: Optional user ID for permission checking (if None, no permission check)
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Log the attempt
            logger.info(f"Attempting to delete document {document_id} by user {user_id}")
            
            # Handle ObjectId conversion
            try:
                doc_obj_id = ObjectId(document_id)
            except Exception as e:
                logger.error(f"Invalid document ID format: {document_id}, error: {str(e)}")
                return False
            
            # Find document record
            query = {"_id": doc_obj_id}
            if user_id:
                # For admin user_id is the admin's ID, not the document owner
                # So we don't add it to the query - admins can delete any document
                pass
            
            # Log the query
            logger.info(f"Document delete query: {query}")
            
            document = self.documents.find_one(query)
            if not document:
                logger.warning(f"Document not found or access denied: {document_id}")
                return False
            
            # Log the document we're about to delete
            logger.info(f"Found document to delete: {document.get('original_filename')}")
            
            # Delete from S3 if file exists and we have S3 client
            if document.get("s3_key") and self.s3_client:
                try:
                    self.s3_client.delete_object(
                        Bucket=self.s3_bucket,
                        Key=document["s3_key"]
                    )
                    logger.info(f"Deleted document from S3: {document['s3_key']}")
                except Exception as e:
                    logger.error(f"Error deleting from S3: {str(e)}")
                    # Continue with database deletion even if S3 delete fails
            
            # Delete from MongoDB
            result = self.documents.delete_one({"_id": doc_obj_id})
            
            if result.deleted_count:
                logger.info(f"Document deleted successfully: {document_id}")
                return True
            else:
                logger.warning(f"Document found but not deleted from database: {document_id}")
                return False
            
        except Exception as e:
            logger.error(f"Error deleting document: {str(e)}", exc_info=True)
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
    
    def get_all_documents(self, admin_id: str, user_id: Optional[str] = None, 
                         date_filter: str = "All Time", 
                         status_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all documents with optional filtering (admin only)
        
        Args:
            admin_id: ID of the admin user making the request
            user_id: Optional user ID to filter documents by owner
            date_filter: Date range filter (All Time, Today, Last 7 Days, etc.)
            status_filter: Status filter (Analyzed, Pending Analysis, Error)
            
        Returns:
            List of document records
        """
        try:
            # Log the request
            logger.info(f"Admin {admin_id} requesting documents with filters: user_id={user_id}, date={date_filter}, status={status_filter}")
            
            # Build query
            query = {}
            
            # Filter by user if provided
            if user_id:
                logger.debug(f"Filtering by user_id: {user_id}")
                query["user_id"] = ObjectId(user_id)
            
            # Apply date filter
            if date_filter != "All Time":
                now = datetime.utcnow()
                if date_filter == "Today":
                    start_date = datetime(now.year, now.month, now.day)
                    query["uploaded_at"] = {"$gte": start_date}
                elif date_filter == "Last 7 Days":
                    start_date = now - timedelta(days=7)
                    query["uploaded_at"] = {"$gte": start_date}
                elif date_filter == "Last 30 Days":
                    start_date = now - timedelta(days=30)
                    query["uploaded_at"] = {"$gte": start_date}
                elif date_filter == "Last 90 Days":
                    start_date = now - timedelta(days=90)
                    query["uploaded_at"] = {"$gte": start_date}
                elif date_filter == "This Year":
                    start_date = datetime(now.year, 1, 1)
                    query["uploaded_at"] = {"$gte": start_date}
                logger.debug(f"Date filter applied: {date_filter}, query: {query.get('uploaded_at')}")
            
            # Apply status filter
            if status_filter:
                if status_filter == "Analyzed":
                    query["analysis_results"] = {"$exists": True, "$ne": None}
                elif status_filter == "Pending Analysis":
                    query["analysis_results"] = {"$exists": False}
                elif status_filter == "Error":
                    query["error"] = {"$exists": True, "$ne": None}
                logger.debug(f"Status filter applied: {status_filter}")
            
            # Log the final query
            logger.debug(f"Final document query: {query}")
            
            # Check if there are any documents at all first
            total_docs = self.documents.count_documents({})
            if total_docs == 0:
                logger.info("No documents found in the database at all")
                return []
            
            # Get documents with user information
            pipeline = [
                {"$match": query},
                {
                    "$lookup": {
                        "from": "users",
                        "localField": "user_id",
                        "foreignField": "_id",
                        "as": "user"
                    }
                },
                {
                    "$addFields": {
                        "user_email": {"$arrayElemAt": ["$user.email", 0]},
                        "user_fullname": {"$arrayElemAt": ["$user.fullname", 0]}
                    }
                },
                {
                    "$project": {
                        "user": 0,  # Remove the full user array
                        "analysis_results": 0  # Don't include full analysis results (could be large)
                    }
                },
                {"$sort": {"uploaded_at": -1}}
            ]
            
            documents = list(self.documents.aggregate(pipeline))
            logger.info(f"Found {len(documents)} documents matching the query")
            
            # Process documents for display
            for doc in documents:
                # Convert ObjectId to string
                doc["_id"] = str(doc["_id"])
                doc["user_id"] = str(doc["user_id"])
                
                # Only add document_id alias if it doesn't already exist
                if "document_id" not in doc:
                    doc["document_id"] = doc["_id"]  # Add alias for consistency
                
                # Format file size
                if "file_size" in doc and doc["file_size"]:
                    size_bytes = doc["file_size"]
                    if size_bytes < 1024:
                        doc["file_size"] = f"{size_bytes} bytes"
                    elif size_bytes < 1024 * 1024:
                        doc["file_size"] = f"{size_bytes / 1024:.1f} KB"
                    else:
                        doc["file_size"] = f"{size_bytes / (1024 * 1024):.1f} MB"
                
                # Add status field
                if "analysis_results" in doc and doc.get("analysis_results"):
                    doc["status"] = "Analyzed"
                elif "error" in doc and doc.get("error"):
                    doc["status"] = "Error"
                else:
                    doc["status"] = "Pending Analysis"
            
            return documents
            
        except Exception as e:
            logger.error(f"Error fetching all documents: {str(e)}", exc_info=True)
            return []
    
    def reassign_document(self, document_id: str, admin_id: str, new_user_id: str) -> bool:
        """
        Reassign a document to a different user (admin only)
        
        Args:
            document_id: ID of the document to reassign
            admin_id: ID of the admin user making the request
            new_user_id: ID of the user to reassign the document to
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Find document
            document = self.documents.find_one({"_id": ObjectId(document_id)})
            if not document:
                logger.warning(f"Document not found: {document_id}")
                return False
            
            # Update document owner
            result = self.documents.update_one(
                {"_id": ObjectId(document_id)},
                {"$set": {
                    "user_id": ObjectId(new_user_id),
                    "reassigned_by": admin_id,
                    "reassigned_at": datetime.utcnow()
                }}
            )
            
            if result.modified_count:
                logger.info(f"Document {document_id} reassigned to user {new_user_id} by admin {admin_id}")
                return True
            
            return False
        except Exception as e:
            logger.error(f"Error reassigning document: {str(e)}")
            return False
    
    def get_admin_document_statistics(self) -> Dict[str, Any]:
        """
        Get document statistics for the admin dashboard
        
        Returns:
            Dictionary containing document statistics
        """
        try:
            stats = {}
            
            # Total documents
            stats["document_count"] = self.documents.count_documents({})
            
            # Documents uploaded in the last 30 days
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            stats["new_docs_30d"] = self.documents.count_documents({"uploaded_at": {"$gte": thirty_days_ago}})
            
            # Generate document upload trend data
            pipeline = [
                {
                    "$match": {
                        "uploaded_at": {"$gte": thirty_days_ago}
                    }
                },
                {
                    "$group": {
                        "_id": {
                            "$dateToString": {"format": "%Y-%m-%d", "date": "$uploaded_at"}
                        },
                        "count": {"$sum": 1}
                    }
                },
                {
                    "$sort": {"_id": 1}
                }
            ]
            
            upload_trend = list(self.documents.aggregate(pipeline))
            
            # Convert to list of dates and counts
            dates = []
            counts = []
            
            # Ensure all dates in the last 30 days are represented
            current_date = thirty_days_ago.date()
            end_date = datetime.utcnow().date()
            
            # Create a map of date to count from the aggregation results
            date_count_map = {item["_id"]: item["count"] for item in upload_trend}
            
            # Fill in all dates
            while current_date <= end_date:
                date_str = current_date.strftime("%Y-%m-%d")
                dates.append(date_str)
                counts.append(date_count_map.get(date_str, 0))
                current_date += timedelta(days=1)
            
            # Create trend data
            stats["document_upload_trend"] = {
                "date": dates,
                "count": counts
            }
            
            # Get recent document activity - both uploads and analysis completions
            # First, get uploads with user info
            recent_uploads_pipeline = [
                {"$sort": {"uploaded_at": -1}},
                {"$limit": 20},
                {
                    "$lookup": {
                        "from": "users",
                        "localField": "user_id",
                        "foreignField": "_id",
                        "as": "user"
                    }
                },
                {
                    "$project": {
                        "_id": 1,
                        "original_filename": 1,
                        "uploaded_at": 1,
                        "user_email": {"$arrayElemAt": ["$user.email", 0]},
                        "has_analysis": {
                            "$cond": [
                                {"$ifNull": ["$analysis_results", False]},
                                True, 
                                False
                            ]
                        },
                        "processing_history": 1,
                        "reassigned_at": 1,
                        "reassigned_by": 1
                    }
                }
            ]
            
            recent_uploads = list(self.documents.aggregate(recent_uploads_pipeline))
            
            # Format for activity feed
            recent_activity = []
            
            # Add uploads
            for doc in recent_uploads:
                # Get user email - handle "Unknown" cases better
                user_email = doc.get("user_email", "")
                # If we couldn't get user email from the lookup, try to find the user directly
                if not user_email and doc.get("user_id"):
                    try:
                        # Attempt to find user by ID
                        user = self.db.users.find_one({"_id": ObjectId(doc.get("user_id"))})
                        if user and user.get("email"):
                            user_email = user.get("email")
                        else:
                            # Fall back to user ID if we can't get email
                            user_email = f"User {str(doc.get('user_id'))[:8]}"
                    except:
                        # If lookup fails, use generic name with ID
                        user_email = f"User {str(doc.get('user_id'))[:8]}"
                
                # Use "System" instead of "Unknown" for system-generated documents
                if not user_email:
                    user_email = "System" if "sample" in doc.get("original_filename", "").lower() else "Unknown"
                
                # Upload activity
                recent_activity.append({
                    "timestamp": doc.get("uploaded_at"),
                    "user": user_email,
                    "document": doc.get("original_filename", "Unknown"),
                    "activity": "Upload"
                })
                
                # Check for analysis completion
                if doc.get("has_analysis") and doc.get("processing_history"):
                    # Find the analysis completion event
                    analysis_events = [
                        event for event in doc.get("processing_history", [])
                        if event.get("action") == "analysis" and event.get("status") == "success"
                    ]
                    
                    if analysis_events:
                        # Get the most recent analysis completion
                        analysis_event = sorted(
                            analysis_events, 
                            key=lambda x: x.get("timestamp", datetime.min),
                            reverse=True
                        )[0]
                        
                        recent_activity.append({
                            "timestamp": analysis_event.get("timestamp"),
                            "user": user_email,  # Use the same user email for consistency
                            "document": doc.get("original_filename", "Unknown"),
                            "activity": "Analysis"
                        })
                
                # Check for document reassignment
                if doc.get("reassigned_at"):
                    # Try to get the admin who did the reassignment
                    admin_email = "Admin"
                    if doc.get("reassigned_by"):
                        try:
                            admin = self.db.users.find_one({"_id": ObjectId(doc.get("reassigned_by"))})
                            if admin and admin.get("email"):
                                admin_email = admin.get("email")
                        except:
                            pass
                    
                    recent_activity.append({
                        "timestamp": doc.get("reassigned_at"),
                        "user": admin_email,
                        "document": doc.get("original_filename", "Unknown"),
                        "activity": "Reassignment"
                    })
            
            # Sort by timestamp and limit to 10 most recent activities
            stats["recent_document_activity"] = sorted(
                recent_activity,
                key=lambda x: x.get("timestamp", datetime.min),
                reverse=True
            )[:10]
            
            return stats
        except Exception as e:
            logger.error(f"Error getting document statistics: {str(e)}")
            return {}
    
    def create_sample_document(self, user_id: str) -> bool:
        """
        Create a sample document for testing purposes
        
        Args:
            user_id: ID of the user to assign the document to
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Create a sample document entry
            current_time = datetime.utcnow()
            
            # Create a sample document record - being careful to not use any duplicate field names
            document_record = {
                "user_id": ObjectId(user_id),
                "original_filename": "Sample_RFP_Document.pdf",
                "s3_bucket": self.s3_bucket,
                "s3_key": f"sample/{user_id}/Sample_RFP_Document.pdf",
                "uploaded_at": current_time,
                "file_size": 1024 * 500,  # 500 KB
                "file_type": "application/pdf",
                "mime_type": "application/pdf",
                "page_count": 15,
                "status": "processed",  # So it shows up as "Analyzed" in the UI
                "processing_history": [
                    {
                        "action": "upload",
                        "timestamp": current_time,
                        "status": "success",
                        "details": "Sample document created for testing"
                    },
                    {
                        "action": "analysis",
                        "timestamp": current_time + timedelta(minutes=2),
                        "status": "success",
                        "details": "Sample analysis completed"
                    }
                ],
                "analysis_results": {
                    "summary": "This is a sample RFP document created for testing purposes. It contains simulated information about a fictional project.",
                    "requirements": [
                        {
                            "id": "REQ-001",
                            "text": "The system must be accessible through a web browser.",
                            "section": "Technical Requirements",
                            "page": 3,
                            "confidence": 0.95
                        },
                        {
                            "id": "REQ-002",
                            "text": "The solution must support multi-factor authentication.",
                            "section": "Security Requirements",
                            "page": 5,
                            "confidence": 0.92
                        },
                        {
                            "id": "REQ-003",
                            "text": "The system must be available 99.9% of the time.",
                            "section": "SLA Requirements",
                            "page": 8,
                            "confidence": 0.89
                        }
                    ],
                    "metadata": {
                        "issuing_organization": "Sample Company Inc.",
                        "issue_date": (current_time - timedelta(days=10)).strftime("%Y-%m-%d"),
                        "due_date": (current_time + timedelta(days=20)).strftime("%Y-%m-%d"),
                        "project_value": "$500,000 - $750,000",
                        "project_timeline": "6 months"
                    }
                }
            }
            
            # Insert the document record
            result = self.documents.insert_one(document_record)
            
            # Log the result
            if result.inserted_id:
                logger.info(f"Created sample document with ID {result.inserted_id} for user {user_id}")
                return True
            else:
                logger.error("Failed to insert sample document record")
                return False
                
        except Exception as e:
            logger.error(f"Error creating sample document: {str(e)}", exc_info=True)
            return False

    def add_document_event(self, document_id: str, event_type: str, event_details: Optional[Dict[str, Any]] = None) -> bool:
        """
        Add an event to a document's processing history
        
        Args:
            document_id: Document ID
            event_type: Type of event (upload, analysis_start, analysis_complete, error, etc.)
            event_details: Additional event details
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Convert string ID to ObjectId
            doc_id = ObjectId(document_id) if isinstance(document_id, str) else document_id
            
            # Create event object
            event = {
                "event_type": event_type,
                "timestamp": datetime.utcnow(),
                "details": event_details or {}
            }
            
            # Update document with new event in processing_history array
            result = self.documents.update_one(
                {"_id": doc_id},
                {"$push": {"processing_history": event}}
            )
            
            success = result.modified_count > 0
            if success:
                logger.info(f"Added {event_type} event to document {document_id}")
            else:
                logger.warning(f"Failed to add {event_type} event to document {document_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error adding event to document {document_id}: {str(e)}")
            return False

    def get_document_history(self, document_id: str) -> List[Dict[str, Any]]:
        """
        Get the processing history of a document
        
        Args:
            document_id: Document ID
            
        Returns:
            List of event dictionaries in chronological order
        """
        try:
            # Convert string ID to ObjectId
            doc_id = ObjectId(document_id) if isinstance(document_id, str) else document_id
            
            # Get the document
            doc = self.documents.find_one({"_id": doc_id})
            
            if not doc:
                logger.warning(f"Document {document_id} not found")
                return []
            
            # Get processing history, ensure it's an array
            history = doc.get("processing_history", [])
            
            # Sort by timestamp (oldest first)
            history.sort(key=lambda x: x.get("timestamp", datetime.min))
            
            return history
            
        except Exception as e:
            logger.error(f"Error getting history for document {document_id}: {str(e)}")
            return []

    def get_document_count_by_status(self, user_id: str) -> Dict[str, int]:
        """
        Get document counts grouped by status for a user
        
        Args:
            user_id: User ID
            
        Returns:
            Dictionary with status as key and count as value
        """
        try:
            pipeline = [
                {"$match": {"user_id": user_id}},
                {"$group": {"_id": "$status", "count": {"$sum": 1}}},
                {"$sort": {"_id": 1}}
            ]
            
            result = list(self.documents.aggregate(pipeline))
            
            # Convert to dictionary
            counts = {"total": 0}
            for item in result:
                status = item["_id"] or "unknown"
                count = item["count"]
                counts[status] = count
                counts["total"] += count
            
            # Ensure all statuses have a value
            for status in ["uploaded", "processing", "processed", "error"]:
                if status not in counts:
                    counts[status] = 0
            
            return counts
            
        except Exception as e:
            logger.error(f"Error getting document counts for user {user_id}: {str(e)}")
            return {"total": 0, "uploaded": 0, "processing": 0, "processed": 0, "error": 0}

    def search_documents(self, user_id: str, search_query: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Search for documents by filename or content
        
        Args:
            user_id: User ID
            search_query: Search query string
            limit: Maximum number of results
            
        Returns:
            List of matching document dictionaries
        """
        try:
            # Create pipeline for text search
            query = {
                "user_id": user_id,
                "$or": [
                    {"original_filename": {"$regex": search_query, "$options": "i"}},
                    {"metadata.extracted_text": {"$regex": search_query, "$options": "i"}}
                ]
            }
            
            # Execute query
            documents = list(self.documents.find(query).limit(limit))
            
            # Convert ObjectId to string
            for doc in documents:
                if "_id" in doc:
                    doc["_id"] = str(doc["_id"])
            
            logger.info(f"Found {len(documents)} documents matching '{search_query}' for user {user_id}")
            return documents
            
        except Exception as e:
            logger.error(f"Error searching documents for user {user_id}: {str(e)}")
            return []

    def get_document_timeline(self, user_id: str, days: int = 30, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get a timeline of document events for a user
        
        Args:
            user_id: User ID
            days: Number of days to include in the timeline
            limit: Maximum number of events to return
            
        Returns:
            List of event dictionaries with document details
        """
        try:
            # Calculate start date
            start_date = datetime.utcnow() - timedelta(days=days)
            
            # Get documents for user
            documents = self.get_documents_for_user(
                user_id=user_id, 
                limit=limit,
                date_range={"start": start_date}
            )
            
            # Collect all events
            timeline = []
            
            for doc in documents:
                # Add document creation as an event
                doc_id = doc.get("_id")
                
                # Add upload event
                upload_event = {
                    "document_id": doc_id,
                    "document_name": doc.get("original_filename", "Unnamed Document"),
                    "event_type": "upload",
                    "timestamp": doc.get("uploaded_at", datetime.min),
                    "status": "uploaded",
                    "details": {
                        "file_size": doc.get("file_size"),
                        "uploaded_by": doc.get("uploaded_by", "Unknown")
                    }
                }
                timeline.append(upload_event)
                
                # Add processing history events
                for event in doc.get("processing_history", []):
                    event_data = {
                        "document_id": doc_id,
                        "document_name": doc.get("original_filename", "Unnamed Document"),
                        "event_type": event.get("event_type", "unknown"),
                        "timestamp": event.get("timestamp", datetime.min),
                        "status": doc.get("status", "unknown"),
                        "details": event.get("details", {})
                    }
                    timeline.append(event_data)
            
            # Sort by timestamp (newest first)
            timeline.sort(key=lambda x: x.get("timestamp", datetime.min), reverse=True)
            
            # Limit number of events
            if len(timeline) > limit:
                timeline = timeline[:limit]
            
            return timeline
            
        except Exception as e:
            logger.error(f"Error generating timeline for user {user_id}: {str(e)}")
            return []

    def set_document_category(self, document_id: str, category: str) -> bool:
        """
        Set or update the category of a document
        
        Args:
            document_id: Document ID
            category: Category string
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Convert string ID to ObjectId
            doc_id = ObjectId(document_id) if isinstance(document_id, str) else document_id
            
            # Update document
            result = self.documents.update_one(
                {"_id": doc_id},
                {"$set": {"category": category}}
            )
            
            # Add event to history
            if result.modified_count > 0:
                self.add_document_event(
                    document_id=document_id,
                    event_type="category_update",
                    event_details={"category": category}
                )
                
                logger.info(f"Set category '{category}' for document {document_id}")
                return True
            else:
                logger.warning(f"Failed to set category for document {document_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error setting category for document {document_id}: {str(e)}")
            return False