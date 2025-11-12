"""
Database Schemas

Define your MongoDB collection schemas here using Pydantic models.
These schemas are used for data validation in your application.

Each Pydantic model represents a collection in your database.
Model name is converted to lowercase for the collection name:
- User -> "user" collection
- Product -> "product" collection
- BlogPost -> "blogs" collection
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict

# Example schemas (kept for reference)

class User(BaseModel):
    """
    Users collection schema
    Collection name: "user" (lowercase of class name)
    """
    name: str = Field(..., description="Full name")
    email: str = Field(..., description="Email address")
    address: str = Field(..., description="Address")
    age: Optional[int] = Field(None, ge=0, le=120, description="Age in years")
    is_active: bool = Field(True, description="Whether user is active")

class Product(BaseModel):
    """
    Products collection schema
    Collection name: "product" (lowercase of class name)
    """
    title: str = Field(..., description="Product title")
    description: Optional[str] = Field(None, description="Product description")
    price: float = Field(..., ge=0, description="Price in dollars")
    category: str = Field(..., description="Product category")
    in_stock: bool = Field(True, description="Whether product is in stock")

# App-specific schemas

class Job(BaseModel):
    """
    Dubbing jobs submitted by users
    Collection name: "job"
    """
    source_type: str = Field(..., description="'text' or 'audio'")
    source_text: Optional[str] = Field(None, description="Original text if provided")
    source_language: Optional[str] = Field(None, description="Detected or provided source language code")
    target_language: str = Field(..., description="Target language code (e.g., 'hi', 'ta')")
    translation: Optional[str] = Field(None, description="Translated text")
    audio_filename: Optional[str] = Field(None, description="Generated audio file name under outputs/")
    status: str = Field("pending", description="Job status: pending, completed, failed")
    meta: Optional[Dict] = Field(default_factory=dict, description="Additional metadata")

# Note: The Flames database viewer will automatically:
# 1. Read these schemas from GET /schema endpoint
# 2. Use them for document validation when creating/editing
# 3. Handle all database operations (CRUD) directly
# 4. You don't need to create any database endpoints!
