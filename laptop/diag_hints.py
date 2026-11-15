#!/usr/bin/env python3
"""Diagnose hints on the board: rung 3 through the trainer + raw LLM check."""
import json
import urllib.request

def get(url):
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read())

def post(url, body, timeout=30):
    request = urllib.request.Request(url, data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as r:
        return json.loads(r.read())

# 1. hint rung 3 (current numbering: the model sentence)
try:
    hint = get("http://127.0.0.1:8001/api/hint?user=diag&problem=lvl-0_2015_10&rung=3")
    print("HINT RUNG 3:", json.dumps(hint, ensure_ascii=False)[:400])
except Exception as e:
    print("HINT RUNG 3 FAILED:", e)

# 2. raw model sanity check
try:
    d = post("http://127.0.0.1:8081/v1/chat/completions", {
        "messages": [{"role": "user", "content": "Say hello in exactly 5 words."}],
        "max_tokens": 40, "temperature": 0.5})
    m = d["choices"][0]["message"]
    print("RAW content:", repr((m.get("content") or "")[:150]))
    print("RAW reasoning:", repr((m.get("reasoning_content") or "")[:100]))
except Exception as e:
    print("RAW FAILED:", e)

# 3. what the hint prompt itself returns, same as model_hint
try:
    d = post("http://127.0.0.1:8081/v1/chat/completions", {
        "messages": [
            {"role": "system", "content": "You give ONE sentence of help with a math problem. Never say or compute the final answer, never name any option value, never say which letter is correct. At most 35 words. Start with 'Hint: '."},
            {"role": "user", "content": "Tom has 9 caramels and Anna has 17. How many must Tom give Anna so both have the same?\n\nGive one hint."}],
        "max_tokens": 220, "temperature": 0.7, "cache_prompt": True})
    m = d["choices"][0]["message"]
    print("HINT-PROMPT content:", repr((m.get("content") or "")[:200]))
    print("HINT-PROMPT reasoning:", repr((m.get("reasoning_content") or "")[:100]))
except Exception as e:
    print("HINT-PROMPT FAILED:", e)
