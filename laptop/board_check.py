#!/usr/bin/env python3
"""End-to-end check on the board: is the bank being served?"""
import json
import urllib.request

payload = json.load(open("/tmp/payload.json"))
request = urllib.request.Request(
    "http://127.0.0.1:8001/api/answer",
    data=json.dumps(payload).encode(),
    headers={"Content-Type": "application/json"})
with urllib.request.urlopen(request, timeout=60) as response:
    result = json.loads(response.read())
explanation = result.get("explanation", {})
print("label:", result.get("label"))
print("source:", explanation.get("source"))
print("neighbour:", (explanation.get("neighbour") or {}).get("id"))
text = explanation.get("text", "")
print("text:", text[:300])
print("---")
print("VERDICT:", "BANK SERVED" if explanation.get("source") == "bank" else "NOT BANK")
