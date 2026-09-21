#!/usr/bin/env python3
"""
cleanup_vectors.py — Utility to clean up chunks and embeddings for orphaned documents.
"""
import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.db.mongodb import connect_to_mongo, close_mongo_connection
from app.db.mongodb import documents_col, document_chunks_col, document_sections_col

async def cleanup():
    await connect_to_mongo()
    
    docs_col = documents_col()
    chunks_col = document_chunks_col()
    sections_col = document_sections_col()

    print("🧹 FootNote Vector Cleanup")
    
    # 1. Get all valid document IDs
    valid_docs_cursor = docs_col.find({}, {"_id": 1})
    valid_doc_ids = set()
    async for d in valid_docs_cursor:
        valid_doc_ids.add(str(d["_id"]))
        
    print(f"Found {len(valid_doc_ids)} valid documents.")

    # 2. Find chunks with invalid document IDs
    invalid_chunks_result = await chunks_col.delete_many({"document_id": {"$nin": list(valid_doc_ids)}})
    print(f"Deleted {invalid_chunks_result.deleted_count} orphaned chunks.")

    # 3. Find sections with invalid document IDs
    invalid_sections_result = await sections_col.delete_many({"document_id": {"$nin": list(valid_doc_ids)}})
    print(f"Deleted {invalid_sections_result.deleted_count} orphaned sections.")

    print("✅ Cleanup complete.")
    
    await close_mongo_connection()

if __name__ == "__main__":
    asyncio.run(cleanup())
