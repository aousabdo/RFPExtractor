#!/usr/bin/env python3
import os
import uuid
import hashlib
import logging
import secrets
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple
from bson.objectid import ObjectId

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
            ValueError: If email already exists
        """
        try:
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
                "active": True
            }
            
            # Insert user
            result = self.users.insert_one(user)
            logger.info(f"User registered: {email}")
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