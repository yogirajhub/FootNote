from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class JobStatus(str, Enum):
    queued = "queued"
    processing = "processing"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class ProcessingStage(str, Enum):
    upload = "upload"
    validation = "validation"
    extraction = "extraction"
    structure_detection = "structure_detection"
    chunking = "chunking"
    embedding = "embedding"
    indexing = "indexing"
    completed = "completed"


class ProcessingJobResponse(BaseModel):
    job_id: str
    document_id: str
    status: JobStatus
    current_stage: Optional[ProcessingStage] = None
    progress: int = 0  # 0-100
    pages_processed: int = 0
    chunks_created: int = 0
    embeddings_created: int = 0
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime

    @classmethod
    def from_mongo(cls, doc: dict) -> "ProcessingJobResponse":
        return cls(
            job_id=str(doc["_id"]),
            document_id=doc["document_id"],
            status=doc["status"],
            current_stage=doc.get("current_stage"),
            progress=doc.get("progress", 0),
            pages_processed=doc.get("pages_processed", 0),
            chunks_created=doc.get("chunks_created", 0),
            embeddings_created=doc.get("embeddings_created", 0),
            error=doc.get("error"),
            started_at=doc.get("started_at"),
            completed_at=doc.get("completed_at"),
            created_at=doc["created_at"],
        )
