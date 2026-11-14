#!/usr/bin/env python3
"""Quick accuracy read of a model through its llama-server URL.

    python3 probe_model.py --url http://127.0.0.1:8085 --limit 200

Answers the first N validation problems with the grammar + logprobs path
(the same one predict.py uses) and prints the running accuracy plus the
always-D floor of the same sample, so weak vs strong models are obvious.
"""
import argparse
import json
import sys

sys.path.insert(0, ".")
from copilot.llm import URL, answer_distribution


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--url", default=URL)
    p.add_argument("--input", default="data/val.jsonl")
    p.add_argument("--limit", type=int, default=200)
    p.add_argument("--skip", type=int, default=0, help="skip this many problems first")
    args = p.parse_args()

    rows = [json.loads(line) for line in open(args.input, encoding="utf-8") if line.strip()]
    rows = rows[args.skip:args.skip + args.limit]
    correct = floor = 0
    for n, row in enumerate(rows, 1):
        try:
            letter, _probs, _timings = answer_distribution(row, (), timeout=55, url=args.url + "/v1/chat/completions")
        except Exception as error:
            print(f"[{n}/{len(rows)}] {row['id']} failed: {error}", file=sys.stderr)
            letter = ""
        correct += letter == row["label"]
        floor += row["label"] == "D"
        if n % 20 == 0 or n == len(rows):
            print(f"[{n}/{len(rows)}] accuracy {100 * correct / n:.1f}% "
                  f"(always-D floor on the same {n}: {100 * floor / n:.1f}%)", flush=True)
    print(f"\nFINAL: {correct}/{len(rows)} = {100 * correct / len(rows):.1f}%")


if __name__ == "__main__":
    main()
