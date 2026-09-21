#!/usr/bin/env python3
"""
evaluate_rag.py — Simple evaluation script for RAG retrieval and generation.
Requires some pre-indexed documents and test questions.
"""
import asyncio
import sys
import time
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.db.mongodb import connect_to_mongo, close_mongo_connection
from app.rag.pipeline import run_rag_pipeline
from app.config.settings import settings


# Example evaluation dataset for "Complex PTSD"
TEST_DATA = [
    {
        "question": "What is an emotional flashback?",
        "expected_concept": "sudden and often prolonged regression to the frightening and abandoned feeling-states of childhood",
        "document_title": "Complex PTSD",
    },
    {
        "question": "What are the four Fs?",
        "expected_concept": "fight, flight, freeze, fawn",
        "document_title": "Complex PTSD",
    },
    {
        "question": "What is toxic shame?",
        "expected_concept": "loathing of oneself, feeling fatally flawed",
        "document_title": "Complex PTSD",
    }
]


async def evaluate():
    await connect_to_mongo()

    from app.db.mongodb import documents_col
    
    print("🧠 FootNote RAG Evaluation\n")
    
    # Find a ready document to test against
    doc = await documents_col().find_one({"status": "ready"})
    if not doc:
        print("❌ No ready documents found. Please ingest a document first.")
        await close_mongo_connection()
        return

    doc_id = doc["_id"]
    title = doc["title"]
    print(f"Testing against document: {title} ({doc_id})\n")

    passed = 0
    total = len(TEST_DATA)

    for idx, test in enumerate(TEST_DATA, 1):
        print(f"Test {idx}/{total}: {test['question']}")
        
        start = time.time()
        result = await run_rag_pipeline(
            query=test['question'],
            document_id=doc_id,
            document_title=title,
        )
        latency = time.time() - start

        print(f"  └─ Intent: {result.intent.value}")
        print(f"  └─ Passages retrieved: {len(result.passages)}")
        print(f"  └─ Latency: {latency:.2f}s")
        print(f"  └─ Answer snippet: {result.answer[:100]}...\n")
        
        # Simple string matching evaluation for concept presence (in real eval, use LLM-as-a-judge)
        concept = test['expected_concept'].lower()
        if any(concept in p.content.lower() for p in result.passages):
            print("  ✅ Retrieval: PASSED (Expected concept found in passages)")
            passed += 1
        else:
            print("  ❌ Retrieval: FAILED (Expected concept not found in passages)")
            
    print(f"\n📊 Evaluation complete: {passed}/{total} retrieval tests passed.")

    await close_mongo_connection()

if __name__ == "__main__":
    asyncio.run(evaluate())
