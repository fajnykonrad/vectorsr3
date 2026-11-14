#!/usr/bin/env python3
"""Collect one ensemble view over a problem file — farm-ready.

    python3 collect_views.py --view base --input data/val.jsonl
    python3 collect_views.py --view base --llm-url http://127.0.0.1:8085
    python3 collect_views.py --view reversed --offset 0 --stride 3   # PC 1 of 3
    python3 collect_views.py --view reversed --offset 1 --stride 3   # PC 2 of 3

Each view of the same problem is a different prompt (copilot/views.py); the
answers land in data/signals-val-view-<name>.jsonl and score_ensemble.py
votes across the views. --offset/--stride splits the file across machines,
so several laptops collecting different views (or pieces of one) run in
parallel: every machine needs the GGUF, llama-server running locally, and
this repository. Rows resume by key, as collect.py does.
"""
import argparse
import json
import os
import socket
import sys
import time
import urllib.error

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from copilot.config import CONFIG, ROOT  # noqa: E402
from copilot.llm import URL as DEFAULT_URL, answer_distribution  # noqa: E402
from copilot.views import VIEWS, reverse_options  # noqa: E402

TIME_LIMIT = float(CONFIG["TIME_LIMIT_SECONDS"])


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--view", required=True, choices=sorted(VIEWS))
    p.add_argument("--input", default="data/val.jsonl")
    p.add_argument("--output", default="", help="default: data/signals-val-view-<name>.jsonl")
    p.add_argument("--llm-url", default=DEFAULT_URL, help="your local llama-server (default: this laptop)")
    p.add_argument("--offset", type=int, default=0)
    p.add_argument("--stride", type=int, default=1, help="1 = every problem; 3 = every 3rd (PC 1 of 3)")
    p.add_argument("--limit", type=int, default=0)
    return p.parse_args()


def existing_keys(path):
    keys = set()
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        keys.add(json.loads(line).get("key"))
                    except ValueError:
                        continue
    return keys


def main():
    args = parse_args()
    view = VIEWS[args.view]
    output = args.output or f"data/signals-val-view-{args.view}.jsonl"
    if not os.path.exists(args.input):
        sys.exit(f"{args.input} not found")
    with open(args.input, encoding="utf-8") as f:
        problems = [json.loads(line) for line in f if line.strip()]
    todo = [p for i, p in enumerate(problems) if i % args.stride == args.offset % args.stride]
    done = existing_keys(output)
    todo = [p for p in todo if f"{p['id']}|{p['language']}" not in done]
    if args.limit:
        todo = todo[:args.limit]
    print(f"view '{args.view}': {len(todo)} problems -> {output}")

    correct = written = 0
    with open(output, "a", encoding="utf-8") as out:
        for n, problem in enumerate(todo, 1):
            start = time.perf_counter()
            try:
                asked = reverse_options(problem) if view.get("reverse") else problem
                letter, probs, timings = answer_distribution(
                    asked, (), timeout=TIME_LIMIT - 5,
                    url=args.llm_url + "/v1/chat/completions",
                    system=view.get("system"))
            except (socket.timeout, TimeoutError, urllib.error.URLError, OSError) as error:
                print(f"[{n}/{len(todo)}] {problem['id']} failed: {error}", file=sys.stderr)
                continue
            row = {"view": args.view, "key": f"{problem['id']}|{problem['language']}",
                   "id": problem["id"], "language": problem["language"], "label": problem["label"],
                   "answer": letter, "probs": probs,
                   "letter_map": {"A": "E", "B": "D", "C": "C", "D": "B", "E": "A"}
                   if view.get("reverse") else {l: l for l in "ABCDE"},
                   "seconds": round(time.perf_counter() - start, 2),
                   "prompt_tokens": timings.get("prompt_n", 0)}
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
            out.flush()
            written += 1
            correct += letter == problem["label"]
            print(f"[{n}/{len(todo)}] {row['key']} -> {letter} "
                  f"({100 * correct / max(written, 1):.1f}% so far)", flush=True)
    print(f"\nWrote {written} rows; view accuracy {100 * correct / max(written, 1):.1f}%")


if __name__ == "__main__":
    main()
