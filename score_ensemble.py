#!/usr/bin/env python3
"""Vote across ensemble views: soft vote over the letters' probabilities.

    python3 score_ensemble.py                    # all view files it finds
    python3 score_ensemble.py --views base value-first eliminate

Reads data/signals-val-view-<name>.jsonl (each row: one problem, one prompt
view). The options-reversed view's letters are mapped back with its
letter_map. A letter's ensemble score is the mean of exp(logprob) across
the views that saw the problem (a view that is missing a problem still
counts for the others). Prints each view alone, then the vote.
"""
import argparse
import json
import math
import os
import sys
from collections import defaultdict

sys.path.insert(0, ".")
LETTERS = "ABCDE"
FLOOR = -12.0


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--views", nargs="*", help="view names (default: every view file in data/)")
    return p.parse_args()


def load_rows(path):
    rows = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                row = json.loads(line)
                rows[row["key"]] = row
    return rows


def main():
    args = parse_args()
    names = args.views or sorted({f[len("signals-val-view-"):-len(".jsonl")]
                                  for f in os.listdir("data")
                                  if f.startswith("signals-val-view-") and f.endswith(".jsonl")})
    if not names:
        sys.exit("No view files in data/. Run collect_views.py first.")
    files = {name: load_rows(f"data/signals-val-view-{name}.jsonl") for name in names}
    labels = {row["key"]: row["label"] for name in names for row in files[name].values()}
    print(f"views: {', '.join(names)}   problems with all views: "
          f"{min(len(rows) for rows in files.values())}")

    # each view alone
    for name in names:
        hits = sum(row["answer"] == row["label"] for row in files[name].values())
        print(f"  {name:14} {hits}/{len(files[name])} = {100 * hits / len(files[name]):.1f}%")

    # soft vote: mean of exp(logprob) per letter, across the views that saw it
    covered = set.intersection(*(set(rows) for rows in files.values())) \
        if len(names) > 1 else set()
    hits = votes_correct = 0
    for key in sorted(covered):
        label = labels[key]
        scores = {letter: 0.0 for letter in LETTERS}
        for name in names:
            row = files[name][key]
            mapping = row["letter_map"]
            for letter in LETTERS:
                scores[mapping[letter]] += math.exp(row["probs"].get(letter, FLOOR))
        best = max(LETTERS, key=lambda letter: scores[letter])
        votes_correct += best == label
    n = len(covered)
    if n:
        print(f"\nENSEMBLE soft vote on {n} problems with every view:")
        print(f"  {votes_correct}/{n} = {100 * votes_correct / n:.1f}%")
    else:
        print("\n(no problem has every view yet — collect more or wait)")


if __name__ == "__main__":
    main()
