"""Store and read the original uploaded file in MongoDB GridFS.

Parsed pages and embeddings stay in their own collections. This store keeps the
uploaded bytes so the reader can show the file unchanged.
"""
import asyncio
from pathlib import Path
from typing import AsyncIterator, Optional

from bson import ObjectId
from bson.errors import InvalidId
from gridfs.errors import NoFile

from app.db.mongodb import document_files_bucket, documents_col, get_database
import structlog

logger = structlog.get_logger()

CONTENT_TYPES = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "txt": "text/plain; charset=utf-8",
    "md": "text/markdown; charset=utf-8",
    "epub": "application/epub+zip",
}


def content_type_for(file_format: str) -> str:
    return CONTENT_TYPES.get((file_format or "").lower(), "application/octet-stream")


async def delete_original_file(document_id: str, storage_id: Optional[str] = None) -> None:
    bucket = document_files_bucket()
    ids: list[ObjectId] = []
    seen: set[ObjectId] = set()

    def add(file_id: ObjectId) -> None:
        if file_id not in seen:
            seen.add(file_id)
            ids.append(file_id)

    if storage_id:
        try:
            add(ObjectId(storage_id))
        except InvalidId:
            logger.warning("Invalid stored file id", document_id=document_id, storage_id=storage_id)

    files = get_database()["document_files.files"]
    async for item in files.find({"metadata.document_id": document_id}, {"_id": 1}):
        add(item["_id"])

    for file_id in ids:
        try:
            await bucket.delete(file_id)
        except NoFile:
            logger.debug("Stored file already gone", document_id=document_id, storage_id=str(file_id))


async def save_original_file(
    document_id: str,
    user_id: str,
    filename: str,
    file_format: str,
    data: bytes,
) -> str:
    """Replace any previous copy and store the uploaded bytes."""
    await delete_original_file(document_id)
    bucket = document_files_bucket()
    file_id = await bucket.upload_from_stream(
        filename or f"{document_id}.{file_format or 'bin'}",
        data,
        metadata={
            "document_id": document_id,
            "user_id": user_id,
            "format": file_format,
            "content_type": content_type_for(file_format),
        },
    )
    logger.info("Original file stored", document_id=document_id, bytes=len(data))
    return str(file_id)


async def ensure_original_file(doc: dict) -> str:
    """Return the GridFS id, copying a legacy disk upload into the database if needed."""
    file_info = doc.get("file") or {}
    storage_id = file_info.get("storage_id")
    if storage_id:
        return storage_id

    path = file_info.get("path")
    if not path:
        raise FileNotFoundError("Original file is not stored for this document")

    def _read() -> bytes:
        with open(path, "rb") as handle:
            return handle.read()

    if not Path(path).is_file():
        raise FileNotFoundError("Original file is not stored for this document")

    data = await asyncio.to_thread(_read)
    storage_id = await save_original_file(
        doc["_id"],
        doc.get("user_id", ""),
        file_info.get("filename") or "document",
        file_info.get("format") or "",
        data,
    )
    await documents_col().update_one(
        {"_id": doc["_id"]},
        {"$set": {"file.storage_id": storage_id}},
    )
    return storage_id


async def stream_original_file(storage_id: str) -> AsyncIterator[bytes]:
    bucket = document_files_bucket()
    grid_out = await bucket.open_download_stream(ObjectId(storage_id))
    while True:
        chunk = await grid_out.read(1024 * 1024)
        if not chunk:
            break
        yield chunk
