#!/usr/bin/env python3
"""
ingest_document.py — CLI for ingesting any supported document into FootNote.

Usage:
    python scripts/ingest_document.py --file document.pdf [--title "My Doc"] [--author "Author"] [--type book]
"""
import sys
import os
import argparse
import asyncio
import uuid
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.config.settings import settings
from app.db.mongodb import connect_to_mongo, close_mongo_connection, documents_col
from app.ingestion.parser import parse_document
from app.ingestion.structure_detector import detect_structure
from app.ingestion.chunker import chunk_document
from app.ingestion.indexer import store_sections, store_chunks_with_embeddings
from app.rag.embeddings import embedding_service
from app.schemas.document import DocumentType, DocumentStatus
from datetime import datetime, timezone
import structlog

logger = structlog.get_logger()


async def ingest(args) -> None:
    file_path = os.path.abspath(args.file)
    if not os.path.exists(file_path):
        print(f"Error: File not found: {file_path}")
        sys.exit(1)

    await connect_to_mongo()

    doc_id = f"doc_{uuid.uuid4().hex[:16]}"
    version_id = f"v_{uuid.uuid4().hex[:8]}"
    user_id = args.user_id or settings.demo_user_id
    ext = Path(file_path).suffix.lstrip(".").lower()
    now = datetime.now(timezone.utc)

    print(f"\n📄 FootNote Document Ingestion")
    print(f"   File:  {file_path}")
    print(f"   Title: {args.title or Path(file_path).stem}")
    print(f"   Type:  {args.type}")
    print(f"   ID:    {doc_id}\n")

    # Insert document record
    doc = {
        "_id": doc_id,
        "user_id": user_id,
        "title": args.title or Path(file_path).stem,
        "author": args.author,
        "description": args.description,
        "document_type": args.type,
        "file": {
            "filename": Path(file_path).name,
            "format": ext,
            "size": os.path.getsize(file_path),
            "path": file_path,
        },
        "status": DocumentStatus.processing,
        "processing": None,
        "created_at": now,
        "updated_at": now,
    }
    await documents_col().insert_one(doc)

    print("✓ File uploaded")

    # Parse
    print("⟳ Extracting text...")
    loaded = parse_document(file_path)
    print(f"✓ Text extracted ({loaded.total_pages} pages)")

    # Structure
    print("⟳ Detecting structure...")
    structure = detect_structure(loaded)
    await store_sections(structure.sections, doc_id, version_id)
    print(f"✓ Structure detected ({len(structure.sections)} sections, type: {structure.document_type_hint})")

    # Chunk
    print("⟳ Chunking content...")
    chunks = chunk_document(loaded, structure, doc_id, version_id)
    print(f"✓ Content chunked ({len(chunks)} chunks)")

    # Embed
    print(f"⟳ Generating embeddings with {settings.embedding_model}...")
    texts = [c.content for c in chunks]
    embeddings = embedding_service.embed_texts(texts, batch_size=32)
    print(f"✓ Embeddings generated ({len(embeddings)})")

    # Store
    print("⟳ Storing in MongoDB...")
    stored = await store_chunks_with_embeddings(chunks, embeddings, doc_id, version_id)
    print(f"✓ Vector index created ({stored} chunks indexed)")

    # Update document
    await documents_col().update_one(
        {"_id": doc_id},
        {"$set": {
            "status": DocumentStatus.ready,
            "updated_at": datetime.now(timezone.utc),
            "processing": {
                "pages": loaded.total_pages,
                "chunks": stored,
                "embedding_model": settings.embedding_model,
                "processed_at": datetime.now(timezone.utc),
            },
        }},
    )

    print(f"\n✅ Knowledge base ready! Document ID: {doc_id}")
    print(f"   Open at: http://localhost:3000/documents/{doc_id}/chat\n")

    await close_mongo_connection()


def main():
    parser = argparse.ArgumentParser(description="Ingest a document into FootNote")
    parser.add_argument("--file", required=True, help="Path to document file")
    parser.add_argument("--title", help="Document title (defaults to filename)")
    parser.add_argument("--author", help="Document author")
    parser.add_argument("--description", help="Document description")
    parser.add_argument("--type", default="other", choices=[t.value for t in DocumentType], help="Document type")
    parser.add_argument("--user-id", help="User ID (defaults to demo user)")
    args = parser.parse_args()

    asyncio.run(ingest(args))


if __name__ == "__main__":
    main()
