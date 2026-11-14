#!/usr/bin/env python3
"""Tag every problem with a topic, using anchor embeddings.

Writes data/tags.json: {problem_id: topic}. Run it where the bge-small
embedding server from step 6/7 is reachable (on the board it is
127.0.0.1:8082; from the laptop, forward the port first):

    ssh -L 8082:127.0.0.1:8082 arduino@192.168.1.131   # then on the laptop:
    python3 -m trainer.build_tags --embed-url http://127.0.0.1:8082

Each topic has one anchor sentence (trainer/topics.py). A problem gets the
topic of the most similar anchor. Print the topic sizes and a few samples per
topic, so you can judge the quality by eye.
"""
import argparse
import collections
import json
import math
import os
import random
import urllib.request

from .problems import load
from .topics import TOPICS, TOPIC_IDS


def embed(url, texts, query=False, timeout=120):
    prefix = ("Represent this sentence for searching relevant passages: "
              if query else "")
    body = json.dumps({"input": [(prefix + t)[:1400] for t in texts]}).encode()
    request = urllib.request.Request(
        url + "/v1/embeddings", data=body,
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = json.loads(response.read())
    vectors = [item["embedding"] for item in sorted(data["data"], key=lambda d: d["index"])]
    out = []
    for v in vectors:
        norm = math.sqrt(sum(x * x for x in v)) or 1.0
        out.append([x / norm for x in v])
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--embed-url", default="http://127.0.0.1:8082")
    parser.add_argument("--data", default="data")
    parser.add_argument("--languages", default="", help="tag only these, e.g. eng")
    parser.add_argument("--batch", type=int, default=32)
    args = parser.parse_args()

    problems = load(args.data)
    if args.languages:
        keep = set(args.languages.split(","))
        problems = [p for p in problems if p["language"] in keep]
    # one tag per problem id, shared by every language of the same problem
    problems = {p["id"]: p for p in problems}
    print(f"{len(problems)} problems to tag")

    anchors = embed(args.embed_url, [TOPICS[t]["anchor"] for t in TOPIC_IDS])
    ids = list(problems)
    tags = {}
    for i in range(0, len(ids), args.batch):
        chunk = [problems[p]["text"] for p in ids[i:i + args.batch]]
        vectors = embed(args.embed_url, chunk)
        for pid, vec in zip(ids[i:i + args.batch], vectors):
            scores = [sum(a * b for a, b in zip(vec, anchor)) for anchor in anchors]
            tags[pid] = TOPIC_IDS[max(range(len(scores)), key=scores.__getitem__)]
        if (i // args.batch) % 10 == 0:
            print(f"  {min(i + args.batch, len(ids))}/{len(ids)}", flush=True)

    out = os.path.join(args.data, "tags.json")
    with open(out, "w") as f:
        json.dump(tags, f, ensure_ascii=False, indent=0)
    print(f"Wrote {out}")

    counts = collections.Counter(tags.values())
    print("\nTopic sizes:")
    for topic in TOPIC_IDS:
        print(f"  {topic:12} {counts.get(topic, 0):5}")
    rng = random.Random(42)
    print("\nTwo samples per topic, to judge by eye:")
    by_topic = collections.defaultdict(list)
    for pid, topic in tags.items():
        by_topic[topic].append(pid)
    for topic in TOPIC_IDS:
        for pid in rng.sample(by_topic[topic], min(2, len(by_topic[topic]))):
            text = problems[pid]["text"][:80].replace("\n", " ")
            print(f"  [{topic}] {pid}: {text}...")


if __name__ == "__main__":
    main()
