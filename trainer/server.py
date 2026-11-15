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
import threading
import time
import urllib.error
import urllib.request
from collections import defaultdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .db import (LOCK, connect, ensure_user, overall_rating, recent_seen,
                 record_attempt, user_ratings)
from .hints import explain_answer, hint_rung
from .problems import load, problem_ratings_from
from .selector import RECENT, pick_problem, pick_topic
from .topics import TOPICS

STATIC = os.path.join(os.path.dirname(__file__), "static")
LLM_URL = "http://127.0.0.1:8081/v1/chat/completions"


def llm_call(messages, timeout=20.0, temperature=0.7, max_tokens=220):
    """One chat completion from llama-server; raises on any failure.

    temperature and max_tokens are per call: hints and explanations want
    different settings, and a short answer must not pay for a long budget.
    """
    body = json.dumps({"messages": messages, "max_tokens": max_tokens,
                       "temperature": temperature,
                       "cache_prompt": True}).encode()
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
        self.data_dir = data_dir
        self.bank = self.make_bank()
        self.rng = random.Random(42)
        # explanations are generated while the student reads the problem,
        # and shown only after a wrong answer: {id: (event, result)}
        self.explanations = {}
        self._expl_lock = threading.Lock()
        print(f"{len(self.problems)} problems, index: {'yes' if self.index else 'no'}, "
              f"bank: {len(self.bank)}")

    def make_bank(self):
        """Precomputed explanations, status ok only, keyed by problem id.

        One id can have entries in several languages; the trainer serves one
        language per id, so prefer the entry that matches it.
        """
        path = os.path.join(self.data_dir, "solutions.jsonl")
        if not os.path.exists(path):
            return {}
        entries = []
        with open(path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    entry = json.loads(line)
                    if entry.get("status") == "ok" and entry.get("text"):
                        entries.append(entry)
        best = {}
        for entry in entries:
            pid = entry["id"]
            current = best.get(pid)
            served = self.by_id.get(pid)
            matches_served = (served is not None
                              and entry.get("language") == served.get("language"))
            if current is None or matches_served:
                best[pid] = entry
        print(f"bank: {len(best)} explanations from {path}")
        return best

    def prefetch_explanation(self, problem):
        """Generate the wrong-answer explanation in the background."""
        pid = problem["id"]
        with self._expl_lock:
            if pid in self.explanations:
                return
            event, holder = threading.Event(), {}
            self.explanations[pid] = (event, holder)

        def work():
            try:
                holder["value"] = explain_answer(problem, problem["label"],
                                                 llm=llm_call, index=self.index,
                                                 problems=self.problems,
                                                 bank=self.bank)
            except Exception:
                pass  # the answer endpoint generates one on demand instead
            finally:
                event.set()

        threading.Thread(target=work, daemon=True).start()

    def discard_explanation(self, problem):
        """A correct answer needs no explanation: stop the prefetch work."""
        with self._expl_lock:
            self.explanations.pop(problem["id"], None)

    def take_explanation(self, problem):
        """The prefetched explanation, waiting for it briefly; generates one
        only when the prefetch thread died (server down, then the fallback
        path answers at once)."""
        pid = problem["id"]
        with self._expl_lock:
            entry = self.explanations.pop(pid, None)
        if entry is None:
            return explain_answer(problem, problem["label"], llm=llm_call,
                                  index=self.index, problems=self.problems,
                                  bank=self.bank)
        event, holder = entry
        event.wait(timeout=60.0)
        value = holder.get("value")
        if value is None:
            value = explain_answer(problem, problem["label"], llm=llm_call,
                                   index=self.index, problems=self.problems,
                                   bank=self.bank)
        return value

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
        """Everything the stats tab and the quick popover need, in one call."""
        with LOCK:
            overall = overall_rating(self.con, user_id)
            ratings = user_ratings(self.con, user_id)
            rows = self.con.execute(
                "SELECT problem_id, topic, answer, correct, certainty, seconds, "
                "hint_rung, elo_before, elo_after, ts FROM attempts "
                "WHERE user_id = ? ORDER BY ts DESC LIMIT 15", (user_id,)).fetchall()
            counts = defaultdict(int)
            for row in self.con.execute(
                    "SELECT topic, COUNT(*) AS n FROM attempts WHERE user_id = ? "
                    "GROUP BY topic", (user_id,)):
                counts[row["topic"]] = row["n"]
            all_rows = self.con.execute(
                "SELECT problem_id, topic, answer, correct, seconds, hint_rung, "
                "elo_before, elo_after, ts FROM attempts WHERE user_id = ? "
                "ORDER BY ts ASC", (user_id,)).fetchall()

        n = len(all_rows)
        n_correct = sum(r["correct"] for r in all_rows)
        streak = best = 0
        for r in all_rows:  # oldest to newest: the live streak ends today
            streak = streak + 1 if r["correct"] else 0
            best = max(best, streak)

        by_level = defaultdict(lambda: [0, 0])
        heatmap = defaultdict(dict)
        per_topic = defaultdict(lambda: [0, 0])
        for r in all_rows:
            problem = self.by_id.get(r["problem_id"], {})
            key = str(problem.get("level")) if problem else "?"
            by_level[key][1] += 1
            by_level[key][0] += r["correct"]
            heatmap[r["topic"]].setdefault(key, [0, 0])
            heatmap[r["topic"]][key][1] += 1
            heatmap[r["topic"]][key][0] += r["correct"]
            per_topic[r["topic"]][1] += 1
            per_topic[r["topic"]][0] += r["correct"]

        # the general Elo replayed attempt by attempt (same weighted mean the
        # live computation uses, one point per attempt)
        seen = {}
        evolution = []
        for r in all_rows:
            rating, cnt = seen.get(r["topic"], (0.0, 0))
            seen[r["topic"]] = (r["elo_after"], cnt + 1)
            total = sum(c for _, c in seen.values())
            evolution.append([round(r["ts"] * 1000),
                              round(sum(rt * c for rt, c in seen.values()) / total)])
        evolution = evolution[-200:]

        attempts = []
        for r in rows:
            problem = self.by_id.get(r["problem_id"], {})
            attempts.append({
                "problem": r["problem_id"], "topic": r["topic"],
                "level": problem.get("level"), "answer": r["answer"],
                "label": problem.get("label"), "correct": bool(r["correct"]),
                "certainty": r["certainty"], "seconds": round(r["seconds"], 1),
                "hint_rung": r["hint_rung"],
                "elo_after": round(r["elo_after"]),
                "delta": round(r["elo_after"] - r["elo_before"]),
                "ts": round(r["ts"])})
        return {
            "overall": round(overall),
            "ratings": {t: {"rating": round(ratings.get(t, (800.0, 0))[0]),
                            "n": ratings.get(t, (0, 0))[1],
                            "correct": per_topic.get(t, [0, 0])[0],
                            "total": per_topic.get(t, [0, 0])[1]} for t in TOPICS},
            "attempts": attempts,
            "attempt_counts": dict(counts),
            "totals": {"n": n, "correct": n_correct,
                       "accuracy": round(100 * n_correct / n, 1) if n else 0.0,
                       "mean_seconds": round(sum(r["seconds"] for r in all_rows) / n, 1)
                                       if n else 0.0,
                       "streak": streak, "best_streak": best,
                       "hints": sum(r["hint_rung"] for r in all_rows)},
            "by_level": {k: v for k, v in sorted(by_level.items())},
            "heatmap": {t: dict(v) for t, v in heatmap.items()},
            "evolution": evolution,
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
            elif path.startswith("/static/"):
                rel = path[len("/static/"):].split("?")[0]
                full = os.path.normpath(os.path.join(STATIC, rel))
                if not full.startswith(os.path.abspath(STATIC) + os.sep) or \
                        not os.path.isfile(full):
                    return self._json(404, {"error": "not found"})
                ctype = ("application/javascript" if rel.endswith(".js")
                         else "image/png" if rel.endswith(".png")
                         else "text/plain")
                with open(full, "rb") as f:
                    self._send(200, f.read(), ctype + "; charset=utf-8"
                               if ctype.startswith("text") else ctype)
            elif path.startswith("/image/"):
                name = os.path.basename(path[len("/image/"):])
                full = os.path.join(trainer.problems_dir, "images", name)
                with open(full, "rb") as f:
                    self._send(200, f.read(), "image/png")
            elif path == "/api/next":
                user_id = self._user(params)
                forced = trainer.by_id.get(params.get("problem"))
                problem = forced or trainer.next_problem(user_id)
                trainer.prefetch_explanation(problem)
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
            elif path == "/api/explain":
                user_id = self._user(params)
                problem = trainer.by_id.get(params.get("problem"))
                if problem is None:
                    return self._json(404, {"error": "unknown problem"})
                # the prefetch cache (or an on-demand generation) answers
                self._json(200, trainer.take_explanation(problem))
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
            overall_before = overall_rating(trainer.con, user_id)
            correct = answer == problem["label"]
            result = record_attempt(trainer.con, user_id, problem, answer,
                                    correct, certainty, seconds, hint_rung_used)
            overall_after = overall_rating(trainer.con, user_id)
            result["overall_before"] = round(overall_before)
            result["overall_after"] = round(overall_after)
            result["label"] = problem["label"]
            result["options"] = problem.get("options") or {}
            if correct:
                trainer.discard_explanation(problem)  # nothing to explain
            else:
                # the prefetch has been running since the problem was served
                result["explanation"] = trainer.take_explanation(problem)
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
