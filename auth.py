#!/usr/bin/env python3
import os
import uuid
import hashlib
import logging
import secrets
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple
from bson.objectid import ObjectId

from dotenv import load_dotenv
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)

class UserAuth:
    def __init__(self, db):
        """
        Initialize the UserAuth class with a MongoDB database instance
        
        Args:
            db: MongoDB database instance
        """
        self.db = db
        self.users = db.users
        self.sessions = db.sessions
        self.registration_attempts = db.registration_attempts
        
        # Create indexes if they don't exist
        self._setup_indexes()
    
    def _setup_indexes(self):
        """Create necessary database indexes"""
        try:
            # Email must be unique
            self.users.create_index("email", unique=True)
            
            # For session lookup
            self.sessions.create_index("token", unique=True)
            self.sessions.create_index("expiry", expireAfterSeconds=0)

            # Registration attempt tracking
            self.registration_attempts.create_index("email")
            self.registration_attempts.create_index(
                "timestamp", expireAfterSeconds=86400
            )
            
            logger.info("Database indexes created/verified")
        except Exception as e:
            logger.error(f"Failed to create indexes: {str(e)}")
    
    def _hash_password(self, password: str, salt: Optional[str] = None) -> Tuple[str, str]:
        """
        Hash a password with a salt using PBKDF2
        
        Args:
            password: The password to hash
            salt: Optional salt, will generate if not provided
            
        Returns:
            Tuple containing (hashed_password, salt)
        """
        if not salt:
            salt = secrets.token_hex(16)
        
        key = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt.encode('utf-8'),
            100000
        ).hex()
        
        return key, salt
    
    def register_user(self, email: str, password: str, fullname: str, company: str = "") -> bool:
        """
        Register a new user
        
        Args:
            email: User's email
            password: User's password
            fullname: User's full name
            company: User's company (optional)
            
        Returns:
            bool: True if registration successful, False otherwise
            
        Raises:
            ValueError: If email already exists or domain is not allowed
        """
        try:
            # Verify email domain is allowed
            allowed_domains = [d.strip().lower() for d in os.getenv("ALLOWED_EMAIL_DOMAINS", "asetpartners.com").split(",")]
            if not any(email.lower().endswith(f"@{domain}") for domain in allowed_domains):
                logger.warning(f"Registration attempt with unauthorized domain: {email.split('@')[-1]}")
                raise ValueError("Registration is restricted to corporate email addresses.")

            # Rate limiting - max 5 attempts in 5 minutes per email
            window_start = datetime.utcnow() - timedelta(minutes=5)
            attempts = self.registration_attempts.count_documents({
                "email": email.lower(),
                "timestamp": {"$gte": window_start}
            })
            if attempts >= 5:
                logger.warning(f"Rate limit exceeded for registration: {email}")
                raise ValueError("Too many registration attempts. Please try again later.")
            self.registration_attempts.insert_one({"email": email.lower(), "timestamp": datetime.utcnow()})
            
            # Check if email already exists
            if self.users.find_one({"email": email.lower()}):
                raise ValueError("Email already registered")
            
            # Hash password
            hashed_password, salt = self._hash_password(password)
            
            # Create user document
            user = {
                "email": email.lower(),
                "password_hash": hashed_password,
                "password_salt": salt,
                "fullname": fullname,
                "company": company,
                "role": "user",  # Default role
                "created_at": datetime.utcnow(),
                "last_login": None,
                "active": False,  # Account inactive until approved
                "pending_approval": True,
                "registration_date": datetime.utcnow()
            }
            
            # Insert user
            result = self.users.insert_one(user)
            logger.info(f"User registered (pending approval): {email}")
            return bool(result.inserted_id)
            
        except ValueError as e:
            logger.warning(f"Registration failed: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Registration error: {str(e)}")
            return False
    
    def login(self, email: str, password: str) -> Optional[str]:
        """
        Authenticate a user and create a session
        
        Args:
            email: User's email
            password: User's password
            
        Returns:
            str: Session token if successful, None otherwise
        """
        try:
            # Find user by email
            user = self.users.find_one({"email": email.lower()})
            if not user:
                logger.warning(f"Login attempt for non-existent user: {email}")
                return None
            
            # Check if account is pending approval
            if user.get("pending_approval", False):
                logger.warning(f"Login attempt for pending approval account: {email}")
                raise ValueError("Your account is pending admin approval. Please check back later.")
            
            # Check if user is active
            if not user.get("active", True):
                logger.warning(f"Login attempt for inactive user: {email}")
                return None
            
            # Verify password
            hashed_password, salt = self._hash_password(password, user["password_salt"])
            if hashed_password != user["password_hash"]:
                logger.warning(f"Failed login attempt for user: {email}")
                return None
            
            # Update last login time
            self.users.update_one(
                {"_id": user["_id"]},
                {"$set": {"last_login": datetime.utcnow()}}
            )
            
            # Create session token
            token = secrets.token_hex(32)
            expiry = datetime.utcnow() + timedelta(days=1)  # 24-hour session
            
            # Store session
            self.sessions.insert_one({
                "user_id": user["_id"],
                "token": token,
                "created_at": datetime.utcnow(),
                "expiry": expiry
            })
            
            logger.info(f"User logged in: {email}")
            return token
            
        except Exception as e:
            logger.error(f"Login error: {str(e)}")
            return None
    
    def validate_session(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Validate a session token and return user info
        
        Args:
            token: Session token
            
        Returns:
            Dict: User info if valid session, None otherwise
        """
        try:
            # Find session
            session = self.sessions.find_one({
                "token": token,
                "expiry": {"$gt": datetime.utcnow()}
            })
            
            if not session:
                return None
            
            # Find user
            user = self.users.find_one({"_id": session["user_id"]})
            if not user:
                return None
            
            # Return user info (excluding sensitive fields)
            return {
                "user_id": str(user["_id"]),
                "email": user["email"],
                "fullname": user["fullname"],
                "company": user.get("company", ""),
                "role": user.get("role", "user")
            }
            
        except Exception as e:
            logger.error(f"Session validation error: {str(e)}")
            return None
    
    def logout(self, token: str) -> bool:
        """
        Invalidate a session token
        
        Args:
            token: Session token
            
        Returns:
            bool: True if logout successful, False otherwise
        """
        try:
            result = self.sessions.delete_one({"token": token})
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Logout error: {str(e)}")
            return False
    
    def change_password(self, user_id: str, current_password: str, new_password: str) -> bool:
        """
        Change a user's password
        
        Args:
            user_id: User ID
            current_password: Current password
            new_password: New password
            
        Returns:
            bool: True if password change successful, False otherwise
        """
        try:
            # Find user
            user = self.users.find_one({"_id": ObjectId(user_id)})
            if not user:
                return False
            
            # Verify current password
            hashed_password, _ = self._hash_password(current_password, user["password_salt"])
            if hashed_password != user["password_hash"]:
                return False
            
            # Hash new password
            new_hashed_password, new_salt = self._hash_password(new_password)
            
            # Update password
            result = self.users.update_one(
                {"_id": ObjectId(user_id)},
                {"$set": {
                    "password_hash": new_hashed_password,
                    "password_salt": new_salt
                }}
            )
            
            # Invalidate all existing sessions
            self.sessions.delete_many({"user_id": ObjectId(user_id)})
            
            return result.modified_count > 0
            
        except Exception as e:
            logger.error(f"Password change error: {str(e)}")
            return False
    
    def create_initial_admin(self, email: str, password: str, fullname: str) -> bool:
        """
        Create an initial admin user if no users exist
        
        Args:
            email: Admin email
            password: Admin password
            fullname: Admin full name
            
        Returns:
            bool: True if admin created, False if users already exist
        """
        try:
            # Check if any users exist
            if self.users.count_documents({}) > 0:
                logger.info("Admin creation skipped - users already exist")
                return False
            
            # Hash password
            hashed_password, salt = self._hash_password(password)
            
            # Create admin user
            user = {
                "email": email.lower(),
                "password_hash": hashed_password,
                "password_salt": salt,
                "fullname": fullname,
                "company": "Admin",
                "role": "admin",
                "created_at": datetime.utcnow(),
                "last_login": None,
                "active": True
            }
            
            # Insert admin
            result = self.users.insert_one(user)
            logger.info(f"Initial admin created: {email}")
            return bool(result.inserted_id)
            
        except Exception as e:
            logger.error(f"Admin creation error: {str(e)}")
            return False
    
    def get_pending_users(self, admin_user_id: str) -> list:
        """
        Get list of users pending approval
        
        Args:
            admin_user_id: ID of the admin user making the request
            
        Returns:
            list: List of pending user records
        """
        # Verify admin privileges
        admin = self.users.find_one({"_id": ObjectId(admin_user_id)})
        if not admin or admin.get("role") != "admin":
            logger.warning(f"Non-admin user attempted to access pending users: {admin_user_id}")
            return []
        
        # Get pending users
        try:
            pending_users = list(self.users.find(
                {"pending_approval": True},
                {"password_hash": 0, "password_salt": 0}  # Exclude sensitive fields
            ))
            
            # Convert ObjectId to string for JSON serialization
            for user in pending_users:
                user["_id"] = str(user["_id"])
                
            return pending_users
        except Exception as e:
            logger.error(f"Error fetching pending users: {str(e)}")
            return []
    
    def approve_user(self, admin_user_id: str, user_id: str, approved: bool = True) -> bool:
        """
        Approve or reject a pending user
        
        Args:
            admin_user_id: ID of the admin user making the approval
            user_id: ID of the user to approve
            approved: True to approve, False to reject
            
        Returns:
            bool: True if successful, False otherwise
        """
        # Verify admin privileges
        admin = self.users.find_one({"_id": ObjectId(admin_user_id)})
        if not admin or admin.get("role") != "admin":
            logger.warning(f"Non-admin user attempted to approve user: {admin_user_id}")
            return False
        
        try:
            if approved:
                # Approve the user
                result = self.users.update_one(
                    {"_id": ObjectId(user_id), "pending_approval": True},
                    {
                        "$set": {
                            "active": True,
                            "pending_approval": False,
                            "approved_by": admin_user_id,
                            "approved_at": datetime.utcnow()
                        }
                    }
                )
                if result.modified_count:
                    user = self.users.find_one({"_id": ObjectId(user_id)})
                    logger.info(f"User approved: {user.get('email')} by admin: {admin.get('email')}")
                    return True
            else:
                # Reject the user
                result = self.users.update_one(
                    {"_id": ObjectId(user_id), "pending_approval": True},
                    {
                        "$set": {
                            "active": False,
                            "pending_approval": False,
                            "rejected_by": admin_user_id,
                            "rejected_at": datetime.utcnow()
                        }
                    }
                )
                if result.modified_count:
                    user = self.users.find_one({"_id": ObjectId(user_id)})
                    logger.info(f"User rejected: {user.get('email')} by admin: {admin.get('email')}")
                    return True
            
            return False
        except Exception as e:
            logger.error(f"Error approving/rejecting user: {str(e)}")
            return False
    
    def get_all_users(self, admin_user_id: str, search_query: str = "", role_filter: Optional[str] = None) -> list:
        """
        Get a list of all users with optional filtering
        
        Args:
            admin_user_id: ID of the admin user making the request
            search_query: Optional search term for email or fullname
            role_filter: Optional role filter ("admin", "user", "inactive")
            
        Returns:
            list: List of user records
        """
        # Verify admin privileges
        admin = self.users.find_one({"_id": ObjectId(admin_user_id)})
        if not admin or admin.get("role") != "admin":
            logger.warning(f"Non-admin user attempted to access all users: {admin_user_id}")
            return []
        
        try:
            # Build query
            query = {}
            
            # Add search if provided
            if search_query:
                query["$or"] = [
                    {"email": {"$regex": search_query, "$options": "i"}},
                    {"fullname": {"$regex": search_query, "$options": "i"}}
                ]
            
            # Add role filter if provided
            if role_filter:
                if role_filter == "inactive":
                    query["active"] = False
                else:
                    query["role"] = role_filter
                    query["active"] = True
            
            # Get users
            users = list(self.users.find(
                query,
                {"password_hash": 0, "password_salt": 0}  # Exclude sensitive fields
            ))
            
            # Convert ObjectId to string for JSON serialization
            for user in users:
                user["_id"] = str(user["_id"])
                
            return users
        except Exception as e:
            logger.error(f"Error fetching users: {str(e)}")
            return []
    
    def update_user_role(self, admin_user_id: str, user_id: str, new_role: str) -> bool:
        """
        Update a user's role
        
        Args:
            admin_user_id: ID of the admin user making the request
            user_id: ID of the user to update
            new_role: New role to assign
            
        Returns:
            bool: True if successful, False otherwise
        """
        # Verify admin privileges
        admin = self.users.find_one({"_id": ObjectId(admin_user_id)})
        if not admin or admin.get("role") != "admin":
            logger.warning(f"Non-admin user attempted to update user role: {admin_user_id}")
            return False
        
        # Validate role
        if new_role not in ["admin", "user"]:
            logger.warning(f"Invalid role specified: {new_role}")
            return False
        
        try:
            # Update user role
            result = self.users.update_one(
                {"_id": ObjectId(user_id)},
                {"$set": {"role": new_role}}
            )
            
            if result.modified_count:
                user = self.users.find_one({"_id": ObjectId(user_id)})
                logger.info(f"User role updated: {user.get('email')} to {new_role} by admin: {admin.get('email')}")
                return True
            
            return False
        except Exception as e:
            logger.error(f"Error updating user role: {str(e)}")
            return False
    
    def update_user_status(self, admin_user_id: str, user_id: str, active: bool) -> bool:
        """
        Update a user's active status
        
        Args:
            admin_user_id: ID of the admin user making the request
            user_id: ID of the user to update
            active: New active status
            
        Returns:
            bool: True if successful, False otherwise
        """
        # Verify admin privileges
        admin = self.users.find_one({"_id": ObjectId(admin_user_id)})
        if not admin or admin.get("role") != "admin":
            logger.warning(f"Non-admin user attempted to update user status: {admin_user_id}")
            return False
        
        try:
            # Update user status
            result = self.users.update_one(
                {"_id": ObjectId(user_id)},
                {"$set": {"active": active}}
            )
            
            if result.modified_count:
                user = self.users.find_one({"_id": ObjectId(user_id)})
                status_str = "activated" if active else "deactivated"
                logger.info(f"User {status_str}: {user.get('email')} by admin: {admin.get('email')}")
                
                # If deactivating, invalidate all existing sessions
                if not active:
                    self.sessions.delete_many({"user_id": ObjectId(user_id)})
                
                return True
            
            return False
        except Exception as e:
            logger.error(f"Error updating user status: {str(e)}")
            return False
    
    def admin_reset_password(self, admin_user_id: str, user_id: str) -> Optional[str]:
        """
        Reset a user's password as an admin
        
        Args:
            admin_user_id: ID of the admin user making the request
            user_id: ID of the user to reset password for
            
        Returns:
            str: The new temporary password if successful, None otherwise
        """
        # Verify admin privileges
        admin = self.users.find_one({"_id": ObjectId(admin_user_id)})
        if not admin or admin.get("role") != "admin":
            logger.warning(f"Non-admin user attempted to reset password: {admin_user_id}")
            return None
        
        try:
            # Generate a secure random password
            temp_password = secrets.token_urlsafe(12)
            
            # Hash the new password
            hashed_password, salt = self._hash_password(temp_password)
            
            # Update user's password
            result = self.users.update_one(
                {"_id": ObjectId(user_id)},
                {"$set": {
                    "password_hash": hashed_password,
                    "password_salt": salt,
                    "password_reset_by": admin_user_id,
                    "password_reset_at": datetime.utcnow(),
                    "password_temp": True
                }}
            )
            
            if result.modified_count:
                user = self.users.find_one({"_id": ObjectId(user_id)})
                logger.info(f"Password reset for user: {user.get('email')} by admin: {admin.get('email')}")
                
                # Invalidate all existing sessions
                self.sessions.delete_many({"user_id": ObjectId(user_id)})
                
                return temp_password
            
            return None
        except Exception as e:
            logger.error(f"Error resetting password: {str(e)}")
            return None
    
    def admin_create_user(self, admin_user_id: str, email: str, password: str, 
                         fullname: str, company: str = "", role: str = "user") -> bool:
        """
        Create a new user as an admin
        
        Args:
            admin_user_id: ID of the admin user making the request
            email: Email address for the new user
            password: Password for the new user
            fullname: Full name of the new user
            company: Company of the new user
            role: Role for the new user (default: "user")
            
        Returns:
            bool: True if user created successfully, False otherwise
        """
        # Verify admin privileges
        admin = self.users.find_one({"_id": ObjectId(admin_user_id)})
        if not admin or admin.get("role") != "admin":
            logger.warning(f"Non-admin user attempted to create user: {admin_user_id}")
            return False
        
        # Validate role
        if role not in ["admin", "user"]:
            logger.warning(f"Invalid role specified: {role}")
            return False
        
        try:
            # Check if email already exists
            if self.users.find_one({"email": email.lower()}):
                logger.warning(f"Email already exists: {email}")
                return False
            
            # Hash password
            hashed_password, salt = self._hash_password(password)
            
            # Create user record
            user = {
                "email": email.lower(),
                "password_hash": hashed_password,
                "password_salt": salt,
                "fullname": fullname,
                "company": company,
                "role": role,
                "created_at": datetime.utcnow(),
                "created_by": admin_user_id,
                "last_login": None,
                "active": True,
                "pending_approval": False
            }
            
            # Insert user
            result = self.users.insert_one(user)
            
            if result.inserted_id:
                logger.info(f"User created by admin: {email}")
                return True
            
            return False
        except Exception as e:
            logger.error(f"Error creating user: {str(e)}")
            return False
    
    def get_admin_statistics(self, admin_user_id: str) -> Dict[str, Any]:
        """
        Get admin dashboard statistics
        
        Args:
            admin_user_id: ID of the admin user making the request
            
        Returns:
            dict: Dictionary containing statistics for admin dashboard
        """
        # Verify admin privileges
        admin = self.users.find_one({"_id": ObjectId(admin_user_id)})
        if not admin or admin.get("role") != "admin":
            logger.warning(f"Non-admin user attempted to access statistics: {admin_user_id}")
            return {}
        
        try:
            # Calculate basic statistics
            stats = {}
            
            # Total users
            stats["user_count"] = self.users.count_documents({})
            
            # Pending approvals
            stats["pending_users_count"] = self.users.count_documents({"pending_approval": True})
            
            # New users in last 30 days
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            stats["new_users_30d"] = self.users.count_documents({"created_at": {"$gte": thirty_days_ago}})
            
            # Active users in last 7 days
            seven_days_ago = datetime.utcnow() - timedelta(days=7)
            stats["active_users_7d"] = self.users.count_documents({"last_login": {"$gte": seven_days_ago}})
            
            # Generate user registration trend data
            pipeline = [
                {
                    "$match": {
                        "created_at": {"$gte": thirty_days_ago}
                    }
                },
                {
                    "$group": {
                        "_id": {
                            "$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}
                        },
                        "count": {"$sum": 1}
                    }
                },
                {
                    "$sort": {"_id": 1}
                }
            ]
            
            reg_trend = list(self.users.aggregate(pipeline))
            
            # Convert to list of dates and counts
            dates = []
            counts = []
            
            # Ensure all dates in the last 30 days are represented
            current_date = thirty_days_ago.date()
            end_date = datetime.utcnow().date()
            
            # Create a map of date to count from the aggregation results
            date_count_map = {item["_id"]: item["count"] for item in reg_trend}
            
            # Fill in all dates
            while current_date <= end_date:
                date_str = current_date.strftime("%Y-%m-%d")
                dates.append(date_str)
                counts.append(date_count_map.get(date_str, 0))
                current_date += timedelta(days=1)
            
            # Create trend data
            stats["user_registration_trend"] = {
                "date": dates,
                "count": counts
            }
            
            # Get recent user login activity
            login_pipeline = [
                {"$sort": {"created_at": -1}},
                {"$limit": 50},
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
                        "user_email": {"$arrayElemAt": ["$user.email", 0]},
                        "timestamp": "$created_at",
                        "activity": {"$literal": "Login"},
                        "details": "$created_at"
                    }
                }
            ]
            
            # Try to get actual session data
            try:
                recent_logins = list(self.sessions.aggregate(login_pipeline))
                
                # Format the data for display
                recent_user_activity = []
                
                # Add recent logins
                for login in recent_logins[:10]:  # Limit to 10 most recent
                    if login.get("user_email"):
                        recent_user_activity.append({
                            "timestamp": login.get("timestamp"),
                            "user": login.get("user_email", "Unknown"),
                            "activity": "Login",
                            "details": f"Session created at {login.get('details').strftime('%Y-%m-%d %H:%M:%S')}"
                        })
                
                # Add recent user approvals/rejections
                user_approval_pipeline = [
                    {
                        "$match": {
                            "$or": [
                                {"approved_at": {"$exists": True}},
                                {"rejected_at": {"$exists": True}}
                            ]
                        }
                    },
                    {"$sort": {"approved_at": -1, "rejected_at": -1}},
                    {"$limit": 10}
                ]
                
                recent_approvals = list(self.users.find(user_approval_pipeline))
                
                for user in recent_approvals:
                    if user.get("approved_at"):
                        recent_user_activity.append({
                            "timestamp": user.get("approved_at"),
                            "user": user.get("email", "Unknown"),
                            "activity": "Approval",
                            "details": f"User approved by {user.get('approved_by', 'admin')}"
                        })
                    elif user.get("rejected_at"):
                        recent_user_activity.append({
                            "timestamp": user.get("rejected_at"),
                            "user": user.get("email", "Unknown"),
                            "activity": "Rejection",
                            "details": f"User rejected by {user.get('rejected_by', 'admin')}"
                        })
                
                # Add recent user creations
                recent_users_pipeline = [
                    {"$sort": {"created_at": -1}},
                    {"$limit": 10},
                    {
                        "$project": {
                            "email": 1,
                            "created_at": 1,
                            "created_by": 1
                        }
                    }
                ]
                
                recent_users = list(self.users.find(recent_users_pipeline))
                
                for user in recent_users:
                    if user.get("created_by"):  # Created by admin, not self-registered
                        recent_user_activity.append({
                            "timestamp": user.get("created_at"),
                            "user": user.get("email", "Unknown"),
                            "activity": "User Creation",
                            "details": f"User created by admin {user.get('created_by', 'Unknown')}"
                        })
                
                # Sort by timestamp descending and limit to 10
                stats["recent_user_activity"] = sorted(
                    recent_user_activity, 
                    key=lambda x: x.get("timestamp", datetime.min), 
                    reverse=True
                )[:10]
                
            except Exception as e:
                logger.error(f"Error getting user activity: {str(e)}")
                stats["recent_user_activity"] = []
                
            return stats
        except Exception as e:
            logger.error(f"Error getting admin statistics: {str(e)}")
            return {}