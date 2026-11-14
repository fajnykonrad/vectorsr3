#!/usr/bin/env python3
"""Build the retrieval index on your laptop, without the board.

Same schema and same text processing as build_index.py on the board, but the
embeddings come from sentence-transformers (BAAI/bge-small-en-v1.5), the
original model the board's GGUF was converted from. The vectors differ from
the board's by a hair (full precision vs Q8), which is harmless for ranking;
if you want bit-identical behaviour, run build_index.py on the board later.

    pip install sentence-transformers        # once, in .venv
    python3 laptop/build_index_local.py
    python3 laptop/build_index_local.py --only-with-options --languages eng
"""
import argparse
import json
import os
import sys
import time
from array import array

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from copilot.llm import format_problem  # noqa: E402

# copilot/embed.py cuts every text at 1400 characters; keep the same cut here
MAX_CHARS = 1400
MODEL = "BAAI/bge-small-en-v1.5"  # 384 dimensions, the model behind the board's GGUF


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--input", default="data/train.jsonl")
    p.add_argument("--db", default="data/index.db")
    p.add_argument("--languages", default="", help="e.g. eng,cat (default: all in the file)")
    p.add_argument("--only-with-options", action="store_true")
    p.add_argument("--batch", type=int, default=32)
    return p.parse_args()


def main():
    args = parse_args()
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        sys.exit("sentence-transformers is not installed:\n"
                 "  .venv\\Scripts\\activate\n  pip install sentence-transformers")

    languages = set(filter(None, args.languages.split(",")))
    with open(args.input, encoding="utf-8") as f:
        problems = [json.loads(line) for line in f if line.strip()]
    problems = [x for x in problems
                if (not languages or x["language"] in languages)
                and (x.get("options") or not args.only_with_options)]
    if not problems:
        sys.exit("No problems matched. Check --languages and --only-with-options.")
    if os.path.exists(args.db):
        os.remove(args.db)

    import sqlite3
    db = sqlite3.connect(args.db)
    db.execute("""CREATE TABLE IF NOT EXISTS problems (
        key TEXT PRIMARY KEY, problem TEXT NOT NULL, vec BLOB NOT NULL)""")

    model = SentenceTransformer(MODEL)
    start = time.perf_counter()
    for i in range(0, len(problems), args.batch):
        chunk = problems[i:i + args.batch]
        vectors = model.encode([format_problem(p)[:MAX_CHARS] for p in chunk],
                               normalize_embeddings=True).tolist()
        db.executemany("INSERT OR REPLACE INTO problems VALUES (?, ?, ?)", [
            (f"{p['id']}|{p['language']}", json.dumps(p, ensure_ascii=False),
             array("f", v).tobytes())
            for p, v in zip(chunk, vectors)])
        db.commit()
        rate = (i + len(chunk)) / (time.perf_counter() - start)
        print(f"\r{(i + len(chunk))}/{len(problems)} embedded, {rate:.0f}/s", end="", flush=True)
    db.close()
    print(f"\nWrote {args.db} ({os.path.getsize(args.db) / 1e6:.1f} MB) "
          f"in {time.perf_counter() - start:.0f} s")


if __name__ == "__main__":
    main()
