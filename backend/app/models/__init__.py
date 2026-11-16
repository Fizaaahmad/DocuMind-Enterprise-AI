"""Import ORM models so Alembic sees all application metadata."""

from app.models.documents import Document, DocumentChunk, DocumentJob, DocumentSection
from app.models.identity import AuthSession, Membership, Organization, RefreshToken, User
from app.models.intelligence import AIUsage, ChunkEmbedding, Conversation, Message
from app.models.structured import (
    AnalysisItem,
    AnalysisRun,
    AnalysisTemplate,
    ReviewEvent,
    RevisionSection,
    SourceRevision,
)

__all__ = [
    "AnalysisItem",
    "AnalysisRun",
    "AnalysisTemplate",
    "ReviewEvent",
    "RevisionSection",
    "SourceRevision",
    "AIUsage",
    "ChunkEmbedding",
    "Conversation",
    "Message",
    "AuthSession",
    "Membership",
    "Organization",
    "RefreshToken",
    "User",
    "Document",
    "DocumentChunk",
    "DocumentJob",
    "DocumentSection",
]
