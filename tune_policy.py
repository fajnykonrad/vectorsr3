#!/usr/bin/env python3
"""Grid-search deterministic answer policies on the collected val signals.

    python3 tune_policy.py [--languages eng,cat]

Policies (all deterministic, all implementable in predict.py without any
extra model call — they only read the probs the model already produced):

    raw            argmax of the model's probabilities
    alwaysD        D for everything
    mix-group      no OCR options -> D; with options -> raw
    fallback-D     raw, but when the model's confidence is too low -> D
                   (two threshold kinds: |best prob| and best-minus-second)

Prints accuracy per threshold over the requested languages, plus the same
table restricted to cat+eng (the hidden test's languages).
"""
import argparse
import json
import sys

sys.path.insert(0, ".")
from copilot.model import raw_pick

LETTERS = "ABCDE"


def load(path):
    rows = [json.loads(line) for line in open(path, encoding="utf-8") if line.strip()]
    return rows


def acc(rows, answer_of):
    hits = sum(answer_of(r) == r["label"] for r in rows)
    return f"{100 * hits / len(rows):5.1f}% ({hits})"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", default="data/signals-val.jsonl")
    p.add_argument("--languages", default="")
    args = p.parse_args()
    rows = load(args.input)
    if args.languages:
        keep = set(args.languages.split(","))
        rows = [r for r in rows if r["language"] in keep]
    print(f"{len(rows)} problemas ({', '.join(sorted({r['language'] for r in rows}))})\n")

    def raw(r):
        return raw_pick(r["probs"])

    def always_d(r):
        return "D"

    def mix_group(r):
        return "D" if not r.get("has_options") else raw(r)

    def fallback_abs(threshold):
        def answer(r):
            probs = r["probs"]
            best = raw(r)
            return "D" if probs.get(best, -12.0) < threshold else best
        return answer

    def fallback_gap(threshold):
        def answer(r):
            probs = r["probs"]
            sorted_probs = sorted((probs.get(l, -12.0) for l in LETTERS), reverse=True)
            best = raw(r)
            if best == "D":
                return "D"
            gap = sorted_probs[0] - sorted_probs[1]
            return "D" if gap < threshold else best
        return answer

    print(f"{'raw':30}{acc(rows, raw)}")
    print(f"{'always D':30}{acc(rows, always_d)}")
    print(f"{'mix group (no-opt -> D)':30}{acc(rows, mix_group)}")
    print()
    print("fallback-D por |prob| del mejor:")
    for threshold in (-8, -6, -5, -4, -3, -2.5, -2, -1.5, -1, 0):
        print(f"{'  < ' + str(threshold):30}{acc(rows, fallback_abs(threshold))}")
    print()
    print("fallback-D por margen best-second:")
    for threshold in (0.5, 1, 1.5, 2, 2.5, 3, 4, 5):
        print(f"{'  gap < ' + str(threshold):30}{acc(rows, fallback_gap(threshold))}")


if __name__ == "__main__":
    main()
