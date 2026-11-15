#!/usr/bin/env python3
"""Marginal letter calibration against the jury's known-uniform distribution.

    python3 calibrate_uniform.py data/signals-demo.jsonl

The demo problems' true letters are uniform (README: every letter correct
10 times). The model's letter marginal is NOT (it over-says D/A). This
script measures a recalibration that does NOT use the demo's labels to fit:
for each letter it divides the model's probability by that letter's marginal
share q_L (estimated from the unlabeled probs themselves), then argmax:

    score(L) = log p(L) - lambda * log q_L      (lambda 0 = raw)

Only lambda is tuned, on the demo set's labels, as a go/no-go check.
If the calibration beats raw on the demo, ship it for the hidden test: the
hidden set is drawn from the same writing process and the same uniform
letter constraint.
"""
import json
import math
import sys
from collections import Counter

sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8")
from copilot.model import raw_pick

LETTERS = "ABCDE"
FLOOR = -12.0


def load(path):
    rows = [json.loads(line) for line in open(path, encoding="utf-8") if line.strip()]
    return [r for r in rows if r.get("probs")]


def marginals(rows):
    """The model's mean probability per letter, over unlabeled probs."""
    sums = {letter: 0.0 for letter in LETTERS}
    for row in rows:
        total = sum(math.exp(row["probs"].get(letter, FLOOR)) for letter in LETTERS)
        for letter in LETTERS:
            sums[letter] += math.exp(row["probs"].get(letter, FLOOR)) / max(total, 1e-9)
    n = len(rows)
    return {letter: value / n for letter, value in sums.items()}


def pick(row, marginals, lam):
    best, best_score = None, None
    for letter in LETTERS:
        score = row["probs"].get(letter, FLOOR) - lam * math.log(marginals[letter])
        if best_score is None or score > best_score:
            best, best_score = letter, score
    return best


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "data/signals-demo.jsonl"
    rows = load(path)
    print(f"{len(rows)} senales del demo set")

    q = marginals(rows)
    print("marginal del modelo (media de p por letra):")
    for letter in LETTERS:
        bar = "#" * int(q[letter] * 100)
        print(f"  {letter}: {q[letter]:.3f} {bar}")
    print("  (uniforme = 0.200 cada una)\n")

    hits_raw = sum(raw_pick(r["probs"]) == r["label"] for r in rows)
    print(f"raw:                    {hits_raw}/{len(rows)} = {100 * hits_raw / len(rows):.1f}%")
    for lam in (0.5, 1.0, 1.5, 2.0, 3.0):
        hits = sum(pick(r, q, lam) == r["label"] for r in rows)
        print(f"calibrada lambda={lam:<4}: {hits}/{len(rows)} = {100 * hits / len(rows):.1f}%")
    answers = Counter(pick(r, q, 1.0) for r in rows)
    print("\ndistribucion de respuestas calibrada (lambda=1):", dict(sorted(answers.items())))


if __name__ == "__main__":
    main()
