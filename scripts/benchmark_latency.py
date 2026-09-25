"""
benchmark_latency.py — Run latency benchmarks on the RAG pipeline.

Usage:
    python scripts/benchmark_latency.py baseline
    python scripts/benchmark_latency.py phase1
"""
import sys
import asyncio
import json
import time
from pathlib import Path
from statistics import median, quantiles

# Add backend dir to PYTHONPATH to allow imports
sys.path.append(str(Path(__file__).parent.parent / "backend"))

from app.rag.pipeline import run_rag_pipeline
from app.db.mongodb import connect_to_mongo, close_mongo_connection, documents_col
from app.config.settings import settings


QUERIES = [
    "What is the main topic of the first chapter?",
    "Can you explain this in detail?",
    "Who are the key characters mentioned?",
    "Summarize the conclusion.",
    "What are the most important takeaways from this text?",
] * 4  # 20 queries total


async def run_benchmark(label: str):
    await connect_to_mongo()
    
    # 1. Find a document to use for testing
    col = documents_col()
    doc = await col.find_one({"status": "ready"})
    
    if not doc:
        print("NOT MEASURED: No 'ready' documents found in MongoDB.")
        await close_mongo_connection()
        return

    doc_id = str(doc["_id"])
    doc_title = doc.get("title", "Test Document")
    
    print(f"Starting benchmark '{label}' on document: {doc_title} ({doc_id})")
    print(f"Running {len(QUERIES)} queries...")
    
    results = []
    
    # Warmup
    print("Running warmup query...")
    await run_rag_pipeline(
        query="warmup",
        document_id=doc_id,
        document_title=doc_title,
    )

    # Benchmark
    for i, query in enumerate(QUERIES, 1):
        print(f"  [{i}/{len(QUERIES)}] {query[:40]}...")
        result = await run_rag_pipeline(
            query=query,
            document_id=doc_id,
            document_title=doc_title,
        )
        if result.timings:
            results.append(result.timings)
    
    await close_mongo_connection()
    
    if not results:
        print("No timings collected. Did you instrument pipeline.py?")
        return
        
    # Aggregate stats
    stages = list(results[0].keys())
    stats = {}
    
    for stage in stages:
        values = [r.get(stage, 0) for r in results]
        stats[stage] = {
            "mean": round(sum(values) / len(values), 2),
            "p50": round(median(values), 2),
            "p95": round(quantiles(values, n=20)[18], 2) if len(values) > 1 else values[0]
        }
        
    # Total latency
    total_latencies = [sum(r.values()) for r in results]
    stats["total"] = {
        "mean": round(sum(total_latencies) / len(total_latencies), 2),
        "p50": round(median(total_latencies), 2),
        "p95": round(quantiles(total_latencies, n=20)[18], 2) if len(total_latencies) > 1 else total_latencies[0]
    }
    
    print("\n--- Benchmark Results ---")
    for stage, stage_stats in stats.items():
        if stage == "total":
            print(f"\nTOTAL:")
        else:
            print(f"{stage}:")
        print(f"  mean: {stage_stats['mean']} ms")
        print(f"  p50:  {stage_stats['p50']} ms")
        print(f"  p95:  {stage_stats['p95']} ms")
        
    # Save to disk
    out_dir = Path(__file__).parent.parent / "docs" / "perf"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{label}.json"
    
    with open(out_file, "w") as f:
        json.dump(stats, f, indent=2)
        
    print(f"\nResults saved to {out_file}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python benchmark_latency.py <label>")
        sys.exit(1)
        
    label = sys.argv[1]
    asyncio.run(run_benchmark(label))
