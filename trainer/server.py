#!/usr/bin/env python3
"""The learning platform: a web server for the trainer, on the board or a laptop.

    python3 -m trainer.server --host 0.0.0.0            # on the board
    .venv/bin/python -m trainer.server                  # on the laptop, for dev

Endpoints:
    GET  /                     the web page
    GET  /image/<id>_<lang>.png  the problem image, when exported
    GET  /api/next?user=NAME   the next problem (no answer in it)
    POST /api/answer           record an attempt, update the ratings
    GET  /api/hint             climb one rung of the hint ladder
    GET  /api/stats?user=NAME  ratings per topic and recent attempts

Uses only the standard library plus the copilot package that is already here.
The embedding index and the language model are optional: without them, hint
rungs 1 and 3 fall back to topic neighbours and the strategy cue.
"""
import argparse
import json
import os
import random
import time
import urllib.error
import urllib.request
from collections import defaultdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .db import LOCK, connect, ensure_user, recent_seen, record_attempt, user_ratings
from .hints import hint_rung
from .problems import load, problem_ratings_from
from .selector import RECENT, pick_problem, pick_topic
from .topics import TOPICS

STATIC = os.path.join(os.path.dirname(__file__), "static")
LLM_URL = "http://127.0.0.1:8081/v1/chat/completions"


def llm_call(messages, timeout=20.0):
    """One chat completion from llama-server; raises on any failure."""
    body = json.dumps({"messages": messages, "max_tokens": 90,
                       "temperature": 0.7, "cache_prompt": True}).encode()
    request = urllib.request.Request(
        LLM_URL, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = json.loads(response.read())
    return data["choices"][0]["message"]["content"]


def make_index(index_path):
    if not os.path.exists(index_path):
        return None
    try:
        from copilot.rag import Index
        return Index(index_path)
    except Exception as error:
        print(f"index unavailable ({error}); hint rung 1 uses topic neighbours")
        return None


class Trainer:
    def __init__(self, data_dir, db_path, index_path, languages=None):
        self.problems = load(data_dir, languages)
        if not self.problems:
            raise SystemExit(f"no problems in {data_dir}: run laptop/prepare_m3kang.py")
        self.by_id = {p["id"]: p for p in self.problems}
        self.con = connect(db_path)
        self.index = make_index(index_path)
        self.rng = random.Random(42)
        self.data_dir = data_dir
        print(f"{len(self.problems)} problems, index: {'yes' if self.index else 'no'}")

    def sanitized(self, problem):
        """What the browser may see: no label, no split."""
        return {k: v for k, v in problem.items() if k not in ("label", "split")}

    def next_problem(self, user_id):
        rating_map = {t: v[0] for t, v in user_ratings(self.con, user_id).items()}
        topic = pick_topic(rating_map, self.rng)
        problem = pick_problem(self.problems, topic, rating_map,
                               problem_ratings_from(self.con),
                               recent_seen(self.con, user_id, RECENT), self.rng)
        return problem

    def stats(self, user_id):
        with LOCK:
            ratings = user_ratings(self.con, user_id)
            rows = self.con.execute(
                "SELECT problem_id, topic, correct, certainty, seconds, hint_rung, "
                "elo_before, elo_after, ts FROM attempts WHERE user_id = ? "
                "ORDER BY ts DESC LIMIT 15", (user_id,)).fetchall()
            counts = defaultdict(int)
            for row in self.con.execute(
                    "SELECT topic, COUNT(*) AS n FROM attempts WHERE user_id = ? "
                    "GROUP BY topic", (user_id,)):
                counts[row["topic"]] = row["n"]
        return {
            "ratings": {t: {"rating": round(ratings.get(t, (800.0, 0))[0]),
                            "n": ratings.get(t, (0, 0))[1]} for t in TOPICS},
            "attempts": [{"problem": r["problem_id"], "topic": r["topic"],
                          "correct": bool(r["correct"]), "certainty": r["certainty"],
                          "seconds": round(r["seconds"], 1),
                          "hint_rung": r["hint_rung"],
                          "elo_after": round(r["elo_after"])} for r in rows],
            "attempt_counts": dict(counts),
        }


class Handler(BaseHTTPRequestHandler):
    trainer = None  # set in main()

    def log_message(self, fmt, *args):  # quiet: one line per request is noise
        pass

    def _send(self, code, body, content_type="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code, payload):
        self._send(code, json.dumps(payload, ensure_ascii=False).encode())

    def _user(self, params):
        name = (params.get("user") or "guest").strip()[:40] or "guest"
        return ensure_user(self.trainer.con, name)

    def do_GET(self):
        path, _, query = self.path.partition("?")
        params = dict(p.split("=", 1) for p in query.split("&") if "=" in p)
        trainer = self.trainer
        try:
            if path == "/":
                with open(os.path.join(STATIC, "index.html"), "rb") as f:
                    self._send(200, f.read(), "text/html; charset=utf-8")
            elif path.startswith("/image/"):
                name = os.path.basename(path[len("/image/"):])
                full = os.path.join(trainer.problems_dir, "images", name)
                with open(full, "rb") as f:
                    self._send(200, f.read(), "image/png")
            elif path == "/api/next":
                user_id = self._user(params)
                forced = trainer.by_id.get(params.get("problem"))
                problem = forced or trainer.next_problem(user_id)
                self._json(200, {"problem": trainer.sanitized(problem),
                                 "topic": problem.get("topic")})
            elif path == "/api/hint":
                user_id = self._user(params)
                problem = trainer.by_id.get(params.get("problem"))
                if problem is None:
                    return self._json(404, {"error": "unknown problem"})
                rung = max(1, min(4, int(params.get("rung") or 1)))
                result = hint_rung(rung, problem, problem["label"],
                                   index=trainer.index, problems=trainer.problems,
                                   llm=llm_call if rung == 3 else None)
                result.setdefault("rung", rung)
                self._json(200, result)
            elif path == "/api/stats":
                user_id = self._user(params)
                self._json(200, trainer.stats(user_id))
            else:
                self._json(404, {"error": "not found"})
        except Exception as error:  # never let one request kill the server
            self._json(500, {"error": str(error)})

    def do_POST(self):
        if self.path != "/api/answer":
            return self._json(404, {"error": "not found"})
        try:
            length = int(self.headers.get("Content-Length") or 0)
            data = json.loads(self.rfile.read(length) or b"{}")
            trainer = self.trainer
            user_id = self._user(data)
            problem = trainer.by_id.get(data.get("problem"))
            if problem is None:
                return self._json(404, {"error": "unknown problem"})
            answer = str(data.get("answer") or "").strip().upper()[:1]
            certainty = int(data.get("certainty") or 3)
            seconds = float(data.get("seconds") or 0)
            hint_rung_used = int(data.get("hint_rung") or 0)
            result = record_attempt(trainer.con, user_id, problem, answer,
                                    answer == problem["label"], certainty,
                                    seconds, hint_rung_used)
            result["label"] = problem["label"]
            result["options"] = problem.get("options") or {}
            self._json(200, result)
        except Exception as error:
            self._json(500, {"error": str(error)})


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--data", default="data")
    parser.add_argument("--db", default="data/trainer.db")
    parser.add_argument("--index", default="data/index.db")
    parser.add_argument("--languages", default="", help="e.g. eng or eng,cat")
    args = parser.parse_args()

    Handler.trainer = Trainer(args.data, args.db, args.index,
                              languages=[x for x in args.languages.split(",") if x])
    Handler.trainer.problems_dir = args.data
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Trainer on http://{args.host}:{args.port}  (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped")


if __name__ == "__main__":
    main()
