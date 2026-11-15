#!/usr/bin/env python3
"""Time the grounded hint prompt against the board's 0.8B."""
import json
import subprocess
import time
import urllib.request

print(subprocess.run(["free", "-h"], capture_output=True, text=True).stdout)

sol = None
for line in open("/home/arduino/vectorsr3/data/solutions.jsonl", encoding="utf-8"):
    if not line.strip():
        continue
    e = json.loads(line)
    if e["status"] == "ok" and e["id"] == "lvl-0_2015_10":
        sol = e["text"]
        break

body = json.dumps({
    "messages": [
        {"role": "system", "content": "You give ONE short hint for a math problem. You are given the problem and its worked solution. Write ONE sentence of at most 30 words that guides the student to take only the FIRST step of the solution. Never state the final answer, never name any option's value, never say which letter is correct, and never mention that a solution was shown to you. Start with 'Hint: '. Write in the same language as the problem."},
        {"role": "user", "content": "Problem:\n10. On one side of the scale, there are 6 apples, and on the other side, there are 2 melons. If we add one melon to the side with the apples, the scales balance. How many apples does one melon weigh?\n\nWorked solution:\n" + sol[:320] + "\n\nGive one hint about the first step, for the problem above."}],
    "max_tokens": 90, "temperature": 0.4, "cache_prompt": True}).encode()

for attempt in (1, 2):
    t0 = time.time()
    request = urllib.request.Request(
        "http://127.0.0.1:8081/v1/chat/completions", data=body,
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=90) as r:
        d = json.loads(r.read())
    m = d["choices"][0]["message"]
    print(f"attempt {attempt}: {time.time()-t0:.1f}s  "
          f"content={repr((m.get('content') or '')[:160])}")
    print("   timings:", json.dumps(d.get("timings", {}))[:200])
