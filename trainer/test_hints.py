#!/usr/bin/env python3
"""Measure hint rung 3 against a real LLM endpoint: leak rate and latency.

    .venv/bin/python -m trainer.test_hints --url http://127.0.0.1:8081/v1/chat/completions

Posts the rung-3 prompt to the model for N training problems, checks every
hint for leaks with the same code the server uses, and prints the rate plus
the worst offenders. The target is zero leaks and a couple of seconds each.
"""
import argparse
import json
import random
import statistics
import time
import urllib.request

from .hints import leaks, model_hint


def llm_call_factory(url):
    def call(messages, timeout=30.0):
        body = json.dumps({"messages": messages, "max_tokens": 90,
                           "temperature": 0.7, "cache_prompt": True}).encode()
        request = urllib.request.Request(
            url, data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read())
        return data["choices"][0]["message"]["content"]
    return call


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--url", default="http://127.0.0.1:8081/v1/chat/completions")
    parser.add_argument("--limit", type=int, default=40)
    parser.add_argument("--languages", default="eng")
    args = parser.parse_args()

    from .problems import load
    problems = [p for p in load() if p.get("options")]
    if args.languages:
        keep = set(args.languages.split(","))
        problems = [p for p in problems if p["language"] in keep]
    random.Random(42).shuffle(problems)
    problems = problems[:args.limit]
    if not problems:
        raise SystemExit("no problems with options")

    call = llm_call_factory(args.url)
    rows = []
    for i, problem in enumerate(problems, 1):
        t0 = time.time()
        text, status = model_hint(problem, problem["label"], call)
        dt = time.time() - t0
        rows.append((problem, text, status, dt))
        mark = {"ok": "."}.get(status, status[0].upper())
        print(mark, end="", flush=True)
        if i % 40 == 0:
            print(f"  [{i}/{len(problems)}]", flush=True)

    served = [r for r in rows if r[2] == "ok"]
    leaked = sum(1 for r in rows if r[2] == "leaked")
    errors = [r for r in rows if r[2] != "ok" and r[2] != "leaked"]
    print(f"\n\n{len(problems)} problems: {len(served)} served, "
          f"{leaked} leaked (rejected), {len(errors)} errors")
    if served:
        seconds = [r[3] for r in served]
        print(f"Latency: mean {statistics.mean(seconds):.1f} s, "
              f"worst {max(seconds):.1f} s")
    if errors:
        print("\nErrors:")
        for problem, _text, status, _dt in errors[:5]:
            print(f"  {problem['id']}: {status[:100]}")
    if leaked:
        print("\nLeaked hints (rejected by the leak check):")
        for problem, text, status, _dt in rows:
            if status == "leaked":
                print(f"  {problem['id']}: {text!r}")
    print("\nSample hints:")
    for problem, text, status, _dt in [r for r in rows if r[2] == "ok"][:8]:
        print(f"  [{problem['topic']}] {text}")


if __name__ == "__main__":
    main()
