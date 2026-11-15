#!/usr/bin/env python3
"""Verify the new 3-rung ladder and the bank explanation on the board."""
import json
import time
import urllib.request

def get(url, timeout=40):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read())

def post(url, body, timeout=60):
    request = urllib.request.Request(url, data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as r:
        return json.loads(r.read())

base = "http://127.0.0.1:8001"

t0 = time.time()
r1 = get(f"{base}/api/hint?user=diag2&problem=lvl-0_2015_10&rung=1")
print(f"RUNG 1 ({time.time()-t0:.1f}s):", json.dumps(r1, ensure_ascii=False)[:160])

t0 = time.time()
r2 = get(f"{base}/api/hint?user=diag2&problem=lvl-0_2015_10&rung=2")
print(f"RUNG 2 ({time.time()-t0:.1f}s):", json.dumps(r2, ensure_ascii=False)[:220])

t0 = time.time()
r3 = get(f"{base}/api/hint?user=diag2&problem=lvl-0_2015_10&rung=3")
print(f"RUNG 3 ({time.time()-t0:.1f}s):", r3["label"], "->",
      r3["options"].get(r3["label"]))

t0 = time.time()
payload = {"user": "diag2", "problem": "lvl-0_2015_10", "answer": "A",
           "certainty": 3, "seconds": 15, "hint_rung": 0}
r = post(f"{base}/api/answer", payload, timeout=60)
e = r.get("explanation", {})
print(f"EXPLAIN ({time.time()-t0:.1f}s): source={e.get('source')} "
      f"neighbour={'YES (bad)' if e.get('neighbour') else 'none (good)'}")
print("  text:", e.get("text", "")[:200])
