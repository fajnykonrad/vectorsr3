#!/usr/bin/env python3
"""Probe a model WITH short prompt-based reasoning: read a little, then a letter.

    python3 probe_reason.py --url http://127.0.0.1:8085 --limit 60 --max-tokens 200

The model reasons in plain text (no <think> blocks, the server has reasoning
off), then writes "Answer: X". We parse the last letter it committed to.
Measures accuracy, tokens written, and seconds, so the board budget (60 s)
can be checked before engineering this into predict.py.
"""
import argparse
import json
import re
import sys
import time

sys.path.insert(0, ".")
from copilot.client import post
from copilot.llm import URL, format_problem

LETTERS = "ABCDE"
ANSWER_RE = re.compile(r"answer\s*[:\-]?\s*\(?([A-E])\)?", re.IGNORECASE)


def solve(problem, url, max_tokens, seed):
    text = format_problem(problem) + ("\nThink briefly (a few short lines), then end with 'Answer: X' "
                                      "where X is the letter of the correct option.")
    response = post(url + "/v1/chat/completions", {
        "messages": [{"role": "user", "content": text}],
        "max_tokens": max_tokens,
        "temperature": 0,
        "seed": seed,
    }, timeout=110)
    content = response["choices"][0]["message"]["content"]
    timings = response.get("timings", {})
    matches = ANSWER_RE.findall(content)
    if matches:
        letter = matches[-1].upper()
    else:
        tail = content.strip()[-3:]
        letter = next((l for l in reversed(tail) if l in LETTERS), "")
    return letter, timings.get("predicted_n", 0), timings.get("predicted_ms", 0) / 1000


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--url", default=URL)
    p.add_argument("--input", default="data/val.jsonl")
    p.add_argument("--limit", type=int, default=60)
    p.add_argument("--skip", type=int, default=200)
    p.add_argument("--max-tokens", type=int, default=200)
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()

    rows = [json.loads(line) for line in open(args.input, encoding="utf-8") if line.strip()]
    rows = rows[args.skip:args.skip + args.limit]
    correct = floor = written = 0
    tokens = seconds = 0.0
    for n, row in enumerate(rows, 1):
        try:
            letter, pred_n, pred_s = solve(row, args.url, args.max_tokens, args.seed)
        except Exception as error:
            print(f"[{n}/{len(rows)}] {row['id']} failed: {error}", file=sys.stderr)
            letter, pred_n, pred_s = "", 0, 0
        written += bool(letter)
        correct += letter == row["label"]
        floor += row["label"] == "D"
        tokens += pred_n
        seconds += pred_s
        if n % 10 == 0 or n == len(rows):
            print(f"[{n}/{len(rows)}] acc {100 * correct / n:.1f}%  floor-D {100 * floor / n:.1f}%  "
                  f"mean {tokens / max(written, 1):.0f} tok, {seconds / max(written, 1):.1f} s", flush=True)
    print(f"\nFINAL: {correct}/{len(rows)} = {100 * correct / len(rows):.1f}%   "
          f"(floor-D {100 * floor / len(rows):.1f}%, parse ok {written}/{len(rows)}, "
          f"mean {tokens / max(written, 1):.0f} tokens = {seconds / max(written, 1):.1f} s per problem)")


if __name__ == "__main__":
    main()
