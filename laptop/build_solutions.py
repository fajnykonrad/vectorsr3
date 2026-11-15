#!/usr/bin/env python3
"""Precompute step-by-step explanations with the 4B model (laptop only).

    python laptop/build_solutions.py --limit 25     # smoke batch first
    python laptop/build_solutions.py                # the whole bank, resumable

Every explanation is validated with the same consistent() check the trainer
serves through; entries with status "rejected" are kept for inspection but
never served. One JSON line per problem, flushed as it goes, so a killed run
resumes where it stopped (existing ids are skipped unless --retry-rejected).

The bank key is (id, language): the same Kangaroo problem id exists in
several languages and the trainer serves whichever line it loaded last.
"""
import argparse
import json
import os
import re
import sys
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from trainer.hints import _explain_messages, clean_math_text, consistent  # noqa: E402
from trainer.problems import load  # noqa: E402


def call(url, messages, temperature, max_tokens, timeout=180.0):
    body = json.dumps({"messages": messages, "max_tokens": max_tokens,
                       "temperature": temperature,
                       "cache_prompt": True}).encode()
    request = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = json.loads(response.read())
    return data["choices"][0]["message"]["content"]


def strip_think(text):
    """The server separates reasoning; strip it if it ever leaks through."""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()


def solve(problem, url):
    """Best explanation for one problem, or status rejected. Deterministic
    ladder: temperature 0.4, then 0.0."""
    messages = _explain_messages(problem, problem["label"],
                                 strategy_hint(problem))
    text, last_error = None, None
    for temperature in (0.4, 0.0):
        try:
            raw = call(url, messages, temperature, max_tokens=450)
        except Exception as error:
            last_error = str(error)
            break  # server trouble: retrying the same way will not help
        text = clean_math_text(strip_think(raw).strip().strip('"'))
        if consistent(text, problem, problem["label"]):
            return text, "ok", None
        text = None
    return text, "rejected", last_error


def strategy_hint(problem):
    from trainer.topics import TOPICS
    return TOPICS.get(problem.get("topic", "other"),
                      TOPICS["other"])["strategy"]


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--languages", default="eng,cat")
    parser.add_argument("--limit", type=int, default=0, help="0 = everything")
    parser.add_argument("--url", default="http://127.0.0.1:8083/v1/chat/completions")
    parser.add_argument("--data", default="data")
    parser.add_argument("--out", default="data/solutions.jsonl")
    parser.add_argument("--workers", type=int, default=2,
                        help="match llama-server --parallel, or less")
    parser.add_argument("--retry-rejected", action="store_true",
                        help="re-attempt ids that previously failed")
    args = parser.parse_args()

    problems = load(args.data, [x for x in args.languages.split(",") if x])
    problems = [p for p in problems if p.get("options")]
    problems.sort(key=lambda p: (p["id"], p["language"]))
    done = {}
    if os.path.exists(args.out):
        with open(args.out, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    entry = json.loads(line)
                    done[(entry["id"], entry["language"])] = entry["status"]
    todo = [p for p in problems
            if (p["id"], p["language"]) not in done
            or (args.retry_rejected
                and done[(p["id"], p["language"])] == "rejected")]
    if args.limit:
        todo = todo[:args.limit]
    print(f"{len(problems)} problems with options, {len(done)} already in the "
          f"bank, {len(todo)} to generate with {args.workers} worker(s)")

    if not todo:
        summarize(args.out, problems)
        return

    lock = threading.Lock()
    counters = {"n": 0, "ok": 0, "seconds": 0.0}

    def work(problem):
        t0 = time.time()
        text, status, error = solve(problem, args.url)
        entry = {"id": problem["id"], "language": problem["language"],
                 "level": problem.get("level"), "label": problem["label"],
                 "text": text, "status": status, "seconds": round(time.time() - t0, 1)}
        if error:
            entry["error"] = error[:200]
        with lock:
            with open(args.out, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
                f.flush()
            counters["n"] += 1
            counters["ok"] += status == "ok"
            counters["seconds"] += entry["seconds"]
            n = counters["n"]
            if n % 10 == 0 or n == len(todo):
                rate = counters["ok"] / n
                per = counters["seconds"] / n
                left = (len(todo) - n) * per / max(1, args.workers)
                print(f"  {n}/{len(todo)}  ok {rate:.0%}  "
                      f"{per:.1f} s/problem  eta {left / 60:.0f} min", flush=True)

    started = time.time()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        list(pool.map(work, todo))
    print(f"Done in {(time.time() - started) / 60:.0f} min")
    summarize(args.out, problems)


def summarize(out, problems=None):
    statuses = {}
    with open(out, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                entry = json.loads(line)
                statuses[(entry["id"], entry["language"])] = entry
    ok = [e for e in statuses.values() if e["status"] == "ok"]
    print(f"\nBank: {len(ok)} ok / {len(statuses)} attempted "
          f"({100 * len(ok) / max(1, len(statuses)):.0f}%)")
    by_level = {}
    for entry in statuses.values():
        by_level.setdefault(entry["level"], [0, 0])
        by_level[entry["level"]][0 if entry["status"] == "ok" else 1] += 1
    print("By level: " + ", ".join(
        f"L{k}: {v[0]}/{v[0] + v[1]}" for k, v in sorted(by_level.items(),
                                                         key=lambda x: (x[0] is None, x[0]))))
    by_language = {}
    for entry in statuses.values():
        by_language.setdefault(entry["language"], [0, 0])
        by_language[entry["language"]][0 if entry["status"] == "ok" else 1] += 1
    print("By language: " + ", ".join(
        f"{k}: {v[0]}/{v[0] + v[1]}" for k, v in sorted(by_language.items())))


if __name__ == "__main__":
    main()
