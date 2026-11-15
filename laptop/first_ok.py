import json
ok = None
for line in open("data/solutions.jsonl", encoding="utf-8"):
    if line.strip():
        e = json.loads(line)
        if e["status"] == "ok":
            ok = e
            break
print("first ok id:", ok["id"], "| language:", ok["language"], "| label:", ok["label"])
