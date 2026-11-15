#!/usr/bin/env python3
"""Measure every remaining no-GPU policy idea on the collected val signals.

    python3 tune_policy2.py            # cat+eng only (the hidden test's languages)

All are deterministic, offline, and implementable in predict.py:
- median-opt: pick the letter holding the median option value (classic MC
  heuristic; only where all five options parse as numbers)
- vote-gate: when the kNN neighbours agree strongly, follow them
- level-prior: for optionless problems, the most common true letter per
  level, learned from train
- topic-gate: keyword-topic weak spots answer D
Each is measured alone and in combination with the shipped mix policy.
"""
import argparse
import json
import re
import sys
from collections import Counter, defaultdict

sys.path.insert(0, ".")
from copilot.model import raw_pick
from copilot.topics import topic_of

LETTERS = "ABCDE"
NUM = re.compile(r"-?\d+(?:[.,]\d+)?")


def load_val(path="data/val.jsonl"):
    rows = {}
    for line in open(path, encoding="utf-8"):
        if line.strip():
            r = json.loads(line)
            rows[f"{r['id']}|{r['language']}"] = r
    return rows


def load_signals(path="data/signals-val.jsonl"):
    out = []
    for line in open(path, encoding="utf-8"):
        if line.strip():
            s = json.loads(line)
            out.append(s)
    return out


def load_train_labels(path="data/train.jsonl"):
    """P(true letter | level) from train, for the level prior."""
    by_level = defaultdict(Counter)
    for line in open(path, encoding="utf-8"):
        if line.strip():
            r = json.loads(line)
            by_level[r["level"]][r["label"]] += 1
    return {level: counter.most_common(1)[0][0] for level, counter in by_level.items()}


def median_letter(problem):
    """The letter holding the median option value, or None if unparseable."""
    options = problem.get("options") or {}
    values = {}
    for letter in LETTERS:
        if letter not in options:
            return None
        match = NUM.search(str(options[letter]))
        if not match:
            return None
        try:
            values[letter] = float(match.group().replace(",", "."))
        except ValueError:
            return None
    ordered = sorted(values, key=values.get)
    return ordered[2]


def evaluate(rows, name, answer_of, baseline_raw):
    hits = sum(1 for r in rows if answer_of(r) == r["signal"]["label"])
    raw_hits = sum(1 for r in rows if baseline_raw(r) == r["signal"]["label"])
    print(f"  {name:44}{100 * hits / len(rows):5.1f}% ({hits})   vs raw {100 * raw_hits / len(rows):.1f}%")
    return hits


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--languages", default="eng,cat")
    args = p.parse_args()
    keep = set(args.languages.split(","))

    val = load_val()
    signals = load_signals()
    level_prior = load_train_labels()
    rows = []
    for s in signals:
        if s["language"] not in keep:
            continue
        problem = val[s["key"]]
        rows.append({"signal": s, "problem": problem,
                     "topic": topic_of(problem), "level": problem.get("level")})
    print(f"{len(rows)} problemas ({args.languages})\n")

    def raw(r):
        return raw_pick(r["signal"]["probs"])

    def always_d(r):
        return "D"

    def mix(r):  # the shipped policy
        return "D" if not r["problem"].get("options") else raw(r)

    def median_opt(r):
        letter = median_letter(r["problem"])
        return letter if letter else raw(r)

    def mix_median(r):
        if not r["problem"].get("options"):
            return "D"
        letter = median_letter(r["problem"])
        return letter if letter else raw(r)

    def vote_gate(threshold):
        def answer(r):
            votes = r["signal"].get("votes") or {}
            if votes and max(votes.values()) >= threshold:
                return max(votes, key=votes.get)
            return raw(r)
        return answer

    def level_prior_optionless(r):
        if not r["problem"].get("options"):
            return level_prior.get(r["level"], "D")
        return raw(r)

    def mix_level_prior(r):
        if not r["problem"].get("options"):
            return level_prior.get(r["level"], "D")
        letter = median_letter(r["problem"])
        return letter if letter else raw(r)

    # topic accuracy of raw, to pick the weak ones (exploratory)
    by_topic = defaultdict(lambda: [0, 0])
    for r in rows:
        by_topic[r["topic"]][1] += 1
        by_topic[r["topic"]][0] += raw(r) == r["signal"]["label"]
    weak = {topic for topic, (hits, n) in by_topic.items() if n >= 15 and hits / n < 0.22}
    print("temas debiles (raw < 22%, n>=15):", sorted(weak), "\n")

    def topic_gate(r):
        return "D" if r["topic"] in weak else raw(r)

    def full_mix(r):
        if not r["problem"].get("options"):
            return level_prior.get(r["level"], "D")
        if r["topic"] in weak:
            return "D"
        letter = median_letter(r["problem"])
        return letter if letter else raw(r)

    evaluate(rows, "raw (actual)", raw, raw)
    hits = sum(r["signal"]["label"] == r["problem"]["label"] for r in rows)
    if hits != len(rows):
        print(f"  ATENCION: {len(rows) - hits} senales con label != problema.label (desalineacion)")
    evaluate(rows, "always D", always_d, raw)
    evaluate(rows, "mix ship (no-opt -> D)", mix, raw)
    evaluate(rows, "median option value", median_opt, raw)
    evaluate(rows, "mix + median for with-options", mix_median, raw)
    for threshold in (0.6, 0.75, 0.875):
        evaluate(rows, f"vote gate >={threshold}", vote_gate(threshold), raw)
    evaluate(rows, "level prior (optionless)", level_prior_optionless, raw)
    evaluate(rows, "mix + level prior", mix_level_prior, raw)
    evaluate(rows, "topic gate (weak -> D)", topic_gate, raw)
    evaluate(rows, "FULL: prior + median + topic gate", full_mix, raw)


if __name__ == "__main__":
    main()
