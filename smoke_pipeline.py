"""Smoke of the shipped pipeline: heuristics first, LLM where it must.

    python3 smoke_pipeline.py
"""
import json
import sys

sys.path.insert(0, ".")
from copilot.pipeline import solve

rows = [json.loads(l) for l in open("data/sample_problems.jsonl", encoding="utf-8")]
for r in rows:
    res = solve(r)
    mark = "OK " if res["answer"] == r["label"] else "mal"
    print(f"{r['id']}: {res['answer']} [{mark}] [{res['status']}] en {res['seconds']}s (verdad {r['label']})")
