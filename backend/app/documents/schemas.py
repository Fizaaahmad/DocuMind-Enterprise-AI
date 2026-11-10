import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

Status = Literal["pending", "processing", "completed", "failed"]


class DocumentOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    organization_id: uuid.UUID
    uploader_id: uuid.UUID | None
    filename: str
    format: str
    size_bytes: int
    checksum: str | None
    storage_ready: bool
    status: Status
    error: str | None
    section_count: int
    chunk_count: int
    character_count: int
    chunk_size: int
    chunk_overlap: int
    source_metadata: dict
    created_at: datetime
    processing_started_at: datetime | None
    processing_completed_at: datetime | None


class DocumentList(BaseModel):
    items: list[DocumentOutput]
    total: int
    page: int
    page_size: int


class SectionOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    ordinal: int
    label: str
    page_number: int | None
    text: str


class ContentOutput(BaseModel):
    document_id: uuid.UUID
    sections: list[SectionOutput]
    total: int
    page: int
    page_size: int
