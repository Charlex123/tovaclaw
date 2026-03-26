"""Data models for the RAG / custom dataset training system."""

from __future__ import annotations

from enum import Enum
from pydantic import BaseModel, Field


class DatasetStatus(str, Enum):
    PENDING = "pending"
    INGESTING = "ingesting"
    READY = "ready"
    FAILED = "failed"


class DatasetCreate(BaseModel):
    """Request to create a new dataset."""
    name: str = Field(..., min_length=1, max_length=200)
    description: str = ""
    metadata: dict | None = None


class DatasetResponse(BaseModel):
    """Dataset metadata response."""
    id: str
    user_id: str
    name: str
    description: str = ""
    status: str = "pending"
    file_count: int = 0
    chunk_count: int = 0
    embedding_model: str = ""
    vector_collection: str = ""
    created_at: str = ""
    updated_at: str = ""


class DatasetQueryRequest(BaseModel):
    """Request to query a dataset via RAG."""
    query: str = Field(..., min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=50)
    filter_metadata: dict | None = None


class DatasetQueryResponse(BaseModel):
    """RAG query results."""
    query: str
    results: list[dict] = []
    answer: str = ""
    dataset_id: str = ""


class DatasetIngestRequest(BaseModel):
    """Request to ingest additional content into a dataset."""
    content: str = Field(default="", description="Raw text/JSON/CSV content to ingest")
    content_type: str = Field(default="text/plain", description="MIME type of the content")
    source_name: str = Field(default="inline", description="Source identifier")
