#!/usr/bin/env python3
"""
ingest_book.py — Convenience wrapper for ingesting books.

Usage:
    python scripts/ingest_book.py --file "complex_ptsd.pdf" --title "Complex PTSD" --author "Pete Walker"
"""
import sys
import subprocess
from pathlib import Path

args = sys.argv[1:]
# Inject --type book if not already specified
if "--type" not in args:
    args = ["--type", "book"] + args

script = Path(__file__).parent / "ingest_document.py"
subprocess.run([sys.executable, str(script)] + args)
