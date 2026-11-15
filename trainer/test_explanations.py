#!/usr/bin/env python3
"""Measure the explain prompt against a real endpoint: landing rate, latency.

    .venv/bin/python -m trainer.test_explanations --url http://127.0.0.1:8083/v1/chat/completions --limit 20

Posts the explain prompt to a model for N problems, checks every answer
with the same consistent() code the server uses, and prints the rate,
the latency and samples. The pass rate is what a precomputed solution
bank would keep; the rejects are what it would throw away.
"""
import argparse
import json
import random
import statistics
import time
import urllib.request

from .hints import _explain_messages, clean_math_text, consistent, strategy_cue
from .problems import load


def call_factory(url):
    def call(messages, timeout=90.0, temperature=0.4, max_tokens=200):
        body = {"messages": messages, "max_tokens": max_tokens,
                "temperature": temperature, "cache_prompt": True}
        request = urllib.request.Request(
            url, data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read())["choices"][0]["message"]["content"]
    return call


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--url", default="http://127.0.0.1:8083/v1/chat/completions")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--languages", default="eng")
    parser.add_argument("--ids", default="", help="comma-separated problem ids first")
    args = parser.parse_args()

    problems = [p for p in load() if p.get("options")]
    if args.languages:
        keep = set(args.languages.split(","))
        problems = [p for p in problems if p["language"] in keep]
    if args.ids:
        wanted = [x for x in args.ids.split(",") if x]
        by_id = {p["id"]: p for p in problems}
        picked = [by_id[x] for x in wanted if x in by_id]
        rest = [p for p in problems if p["id"] not in set(wanted)]
        random.Random(42).shuffle(rest)
        problems = picked + rest
    else:
        random.Random(42).shuffle(problems)
    problems = problems[:args.limit]
    if not problems:
        raise SystemExit("no problems with options")

    call = call_factory(args.url)
    rows = []
    for i, problem in enumerate(problems, 1):
        t0 = time.time()
        try:
            text = call(_explain_messages(problem, problem["label"],
                                          strategy_cue(problem)))
            text = clean_math_text(text.strip().strip('"'))
            ok = consistent(text, problem, problem["label"])
        except Exception as error:
            text, ok = f"ERROR: {error}", False
        dt = time.time() - t0
        rows.append((problem, text, ok, dt))
        print("." if ok else "X", end="", flush=True)
        if i % 20 == 0:
            print(f"  [{i}/{len(problems)}]", flush=True)

    served = [r for r in rows if r[2]]
    failed = [r for r in rows if not r[2]]
    seconds = [r[3] for r in rows]
    print(f"\n\n{len(problems)} problems: {len(served)} pass the check, "
          f"{len(failed)} rejected ({100 * len(served) / len(problems):.0f}%)")
    print(f"Latency: mean {statistics.mean(seconds):.1f} s, "
          f"worst {max(seconds):.1f} s")
    levels = sorted({p["level"] for p, _t, _ok, _d in rows})
    print("By level: " + ", ".join(
        f"L{k}: {sum(1 for p, _t, ok, _d in rows if p['level'] == k and ok)}"
        f"/{sum(1 for p, _t, _ok, _d in rows if p['level'] == k)}"
        for k in levels))
    print("\nSample explanations that PASS:")
    for problem, text, ok, _dt in served[:3]:
        print(f"  [{problem['id']}] {text[:220]}")
    if failed:
        print("Sample explanations that FAIL:")
        for problem, text, _ok, _dt in failed[:3]:
            print(f"  [{problem['id']} label={problem['label']}] {text[:220]}")


if __name__ == "__main__":
    main()
