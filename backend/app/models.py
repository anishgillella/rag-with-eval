"""Pydantic models for the QA system."""

from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field


# ============================================================================
# API Request/Response Models
# ============================================================================


class QuestionRequest(BaseModel):
    """Request model for asking a question."""

    question: str = Field(..., min_length=5, max_length=500)
    include_sources: bool = False
    include_evaluations: bool = True
    max_sources: Optional[int] = Field(None, ge=1, le=500, description="Maximum number of sources to use. For user-specific queries, set to None to use all messages from that user.")


class EvaluationScore(BaseModel):
    """Single evaluation score."""

    name: str
    score: float = Field(ge=0, le=1)
    reasoning: str
    passed: bool


class MessageSource(BaseModel):
    """Retrieved message source."""

    id: str
    user_id: str
    user_name: str
    timestamp: str
    message: str
    similarity_score: float = Field(ge=0, le=1)
    reranker_score: Optional[float] = None


class EvaluationResults(BaseModel):
    """Complete evaluation results."""

    evaluations: List[EvaluationScore]
    average_score: float = Field(ge=0, le=1)
    all_passed: bool
    timestamp: datetime


class TokenUsageInfo(BaseModel):
    """Token usage information."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0


class QueryMetadata(BaseModel):
    """Metadata about the query analysis."""
    
    query_type: str = Field(
        ...,
        description="Type of query: 'user_specific', 'multi_user', 'factual', 'comparison', 'general'"
    )
    mentioned_users: List[str] = Field(
        default_factory=list,
        description="Users mentioned in the query"
    )
    confidence_factors: dict = Field(
        default_factory=dict,
        description="Factors contributing to confidence score"
    )


class AnswerResponse(BaseModel):
    """Response model for question answers."""

    model_config = {"protected_namespaces": ()}

    answer: str
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence score (0.0-1.0) based on source quality and quantity"
    )
    sources: Optional[List[MessageSource]] = None
    evaluations: Optional[EvaluationResults] = None
    latency_ms: float
    model_used: str = "openai/gpt-4o-mini"
    token_usage: Optional[TokenUsageInfo] = None
    query_metadata: Optional[QueryMetadata] = None
    tips: Optional[str] = None


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    indexing_status: dict
    timestamp: datetime


class IndexingStatusResponse(BaseModel):
    """Indexing status response."""

    complete: bool
    progress_percent: float = Field(ge=0, le=100)
    total_messages: int  # Total messages indexed
    indexed_messages: int  # Same as total_messages (for backward compatibility)
    expected_total_messages: Optional[int] = None  # Total messages according to API
    fetched_messages: Optional[int] = None  # Messages successfully fetched from API
    missed_messages: Optional[int] = None  # Messages that couldn't be fetched
    missed_ranges: Optional[List[str]] = None  # List of skip ranges that failed (e.g., ["2200-2299"])
    last_indexed: Optional[datetime] = None
    next_scheduled_refresh: Optional[datetime] = None
    last_error: Optional[str] = None


# ============================================================================
# Internal Data Models
# ============================================================================


class Message(BaseModel):
    """Message data model."""

    id: str
    user_id: str
    user_name: str
    timestamp: str
    message: str


class PaginatedMessages(BaseModel):
    """Paginated messages response from API."""

    total: int
    items: List[Message]


class RetrievedContext(BaseModel):
    """Retrieved context with metadata."""

    message: Message
    similarity_score: float
    reranker_score: Optional[float] = None
    rank: int


class IndexingMetadata(BaseModel):
    """Metadata for indexing tracking."""

    last_indexed: Optional[datetime] = None
    total_indexed: int = 0
    indexing_complete: bool = False
    next_refresh: Optional[datetime] = None
    last_error: Optional[str] = None
    indexing_start_time: Optional[datetime] = None

