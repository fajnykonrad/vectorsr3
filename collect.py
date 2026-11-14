#!/usr/bin/env python3
"""Collect the raw model's signals on the training problems.

For every training problem this appends one line to data/signals.jsonl:

    {"key", "id", "language", "level", "has_options", "label",
     "answer", "probs", "votes", "seconds", "prompt_tokens"}

- probs: the model's own log-probability for each letter A..E at the answer
  position (the grammar-constrained first token). This is the raw model,
  before any fusion, so fit_model.py can learn corrections from it.
- votes: the share of the nearest training problems in the retrieval index
  whose answer is each letter. The query never retrieves itself.

Run it on the board, or from the laptop with the servers forwarded:

    ssh -L 8081:127.0.0.1:8081 -L 8082:127.0.0.1:8082 arduino@BOARD_IP
    python3 collect.py --limit 300          # in the forwarded terminal

About 9 s per problem: 300 problems is about 45 minutes. It resumes: keys
already in the output file are skipped, so you can stop and start again.
"""
import argparse
import json
import os
import socket
import sys
import time
import urllib.error

from copilot.config import CONFIG
from copilot.llm import URL as LLM_URL, answer_distribution
from copilot.pipeline import MARGIN, TIME_LIMIT, label_votes


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--input", default="data/train.jsonl")
    p.add_argument("--output", default="data/signals.jsonl")
    p.add_argument("--index", default="data/index.db")
    p.add_argument("--no-index", action="store_true", help="skip the kNN votes (not useful for fitting)")
    p.add_argument("--languages", default="", help="e.g. eng (default: every language in the file)")
    p.add_argument("--limit", type=int, default=0, help="stop after N new rows (0 means all)")
    p.add_argument("--neighbours", type=int, default=8)
    return p.parse_args()


def existing_keys(path):
    keys = set()
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                if line.strip():
                    keys.add(json.loads(line).get("key"))
    return keys


def main():
    args = parse_args()
    if not os.path.exists(args.input):
        sys.exit(f"{args.input} not found. Run laptop/prepare_m3kang.py first (README step 9).")

    index = None
    if not args.no_index:
        if not os.path.exists(args.index):
            sys.exit(f"{args.index} not found. Build it first: python3 build_index.py")
        from copilot.rag import Index
        index = Index(args.index)

    languages = set(filter(None, args.languages.split(",")))
    with open(args.input) as f:
        problems = [json.loads(line) for line in f if line.strip()]
    problems = [p for p in problems if not languages or p["language"] in languages]
    done = existing_keys(args.output)
    todo = [p for p in problems if f"{p['id']}|{p['language']}" not in done]
    if args.limit:
        todo = todo[:args.limit]
    print(f"{len(problems)} problems, {len(done)} already collected, {len(todo)} to go")

    correct = misses = 0
    with open(args.output, "a") as out:
        for n, problem in enumerate(todo, 1):
            start = time.perf_counter()
            key = f"{problem['id']}|{problem['language']}"
            try:
                votes = {}
                if index is not None:
                    neighbours = index.search(problem, k=args.neighbours, exclude_id=problem["id"])
                    votes = label_votes(neighbours)
                remaining = TIME_LIMIT - (time.perf_counter() - start) - MARGIN
                letter, probs, timings = answer_distribution(problem, (),
                                                             timeout=max(remaining, 1.0))
            except (socket.timeout, TimeoutError, urllib.error.URLError, OSError) as error:
                print(f"[{n}/{len(todo)}] {key} failed: {error}", file=sys.stderr)
                misses += 1
                continue
            row = {"key": key, "id": problem["id"], "language": problem["language"],
                   "level": problem.get("level"), "has_options": bool(problem.get("options")),
                   "label": problem["label"], "answer": letter, "probs": probs, "votes": votes,
                   "seconds": round(time.perf_counter() - start, 2),
                   "prompt_tokens": timings.get("prompt_n", 0)}
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
            out.flush()
            correct += row["answer"] == row["label"]
            print(f"[{n}/{len(todo)}] {key} -> {row['answer']} (truth {row['label']}) "
                  f"in {row['seconds']:.1f} s, "
                  f"raw accuracy so far {100 * correct / max(correct + misses, 1):.1f}%",
                  flush=True)
    print(f"\nCollected {correct + misses} new signals ({misses} failed) into {args.output}")
    print(f"Raw model accuracy on them: {100 * correct / max(correct + misses, 1):.1f}%")
    print("Next: python3 fit_model.py")


if __name__ == "__main__":
    main()
