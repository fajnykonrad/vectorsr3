"""Show recent bank entries:  python laptop\\watch_solutions.py [how many]."""
import io
import json
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

entries = [json.loads(l) for l in open("data/solutions.jsonl", encoding="utf-8")
           if l.strip()]
ok = [e for e in entries if e["status"] == "ok"]
rej = [e for e in entries if e["status"] != "ok"]
print(f"{len(ok)} ok / {len(rej)} rejected / {len(entries)} total\n")

n = int(sys.argv[1]) if len(sys.argv) > 1 else 6
for e in ok[-n:]:
    print("---", e["id"], f"[{e['language']}] L{e['level']} -> {e['label']}")
    print(e["text"][:350])
    print()
if rej:
    e = rej[-1]
    print("--- LAST REJECTED:", e["id"], f"[{e['language']}]")
    print((e.get("error") or e.get("text") or "(no text)")[:200])
