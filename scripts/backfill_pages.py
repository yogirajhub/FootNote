#!/usr/bin/env python
"""
Backfill pages and re-run ingestion for existing documents.
Usage: python backfill_pages.py [--all] [--document-id DOC_ID]
"""
import os
import sys
import uuid
import asyncio
import argparse

# Add backend directory to sys.path so we can import app modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.db.mongodb import connect_to_mongo, close_mongo_connection, documents_col
from app.ingestion.pipeline import run_ingestion
from app.schemas.document import DocumentStatus

async def backfill(document_id: str = None, all_docs: bool = False):
    await connect_to_mongo()
    try:
        col = documents_col()
        
        query = {}
        if document_id:
            query["_id"] = document_id
        elif all_docs:
            query["status"] = DocumentStatus.ready
        else:
            print("Must specify --all or --document-id")
            return
            
        docs = await col.find(query).to_list(length=None)
        if not docs:
            print("No documents found matching criteria.")
            return
            
        for doc in docs:
            doc_id = doc["_id"]
            file_path = doc.get("file", {}).get("path")
            
            if not file_path or not os.path.exists(file_path):
                print(f"Skipping {doc_id} - File missing: {file_path}")
                continue
                
            print(f"Backfilling {doc_id} ('{doc.get('title')}') from {file_path}...")
            
            version_id = f"v_{uuid.uuid4().hex[:8]}"
            
            def on_progress(stage, progress):
                print(f"  [{progress}%] {stage}")
                
            try:
                stored = await run_ingestion(doc_id, file_path, version_id, on_progress)
                
                # Update status
                from app.db.mongodb import document_pages_col
                total_pages = await document_pages_col().count_documents({"document_id": doc_id})
                
                await col.update_one(
                    {"_id": doc_id},
                    {"$set": {
                        "processing.pages": total_pages,
                        "processing.chunks": stored,
                    }}
                )
                print(f"Success: {doc_id} (Pages: {total_pages}, Chunks: {stored})")
            except Exception as e:
                print(f"Error processing {doc_id}: {e}")
                
    finally:
        await close_mongo_connection()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill document pages and sections")
    parser.add_argument("--all", action="store_true", help="Process all ready documents")
    parser.add_argument("--document-id", type=str, help="Process a specific document ID")
    
    args = parser.parse_args()
    
    asyncio.run(backfill(args.document_id, args.all))
