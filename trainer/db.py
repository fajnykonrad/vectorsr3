"""SQLite state for the trainer: users, attempts, ratings, problem difficulty.

One file, data/trainer.db. The schema is small on purpose; the selector reads
problems and ratings into memory (a few thousand rows at most).
"""
import os
import sqlite3
import threading
import time

from .elo import NEW_TOPICS, USER_SEED, attempt_score, problem_seed, update

LOCK = threading.RLock()  # one shared connection, guarded

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id       INTEGER PRIMARY KEY,
    name     TEXT UNIQUE NOT NULL,
    created  REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS attempts (
    id          INTEGER PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id),
    problem_id  TEXT NOT NULL,
    topic       TEXT NOT NULL,
    answer      TEXT,
    correct     INTEGER NOT NULL,
    certainty   INTEGER NOT NULL,
    seconds     REAL NOT NULL,
    hint_rung   INTEGER NOT NULL DEFAULT 0,
    score       REAL NOT NULL,
    elo_before  REAL NOT NULL,
    elo_after   REAL NOT NULL,
    ts          REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS ratings (
    user_id  INTEGER NOT NULL REFERENCES users(id),
    topic    TEXT NOT NULL,
    rating   REAL NOT NULL,
    n        INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, topic)
);
CREATE TABLE IF NOT EXISTS problems (
    id      TEXT PRIMARY KEY,
    rating  REAL NOT NULL,
    n       INTEGER NOT NULL DEFAULT 0
);
"""


def connect(path="data/trainer.db"):
    if os.path.dirname(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
    con = sqlite3.connect(path, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    con.commit()
    return con


def ensure_user(con, name):
    with LOCK:
        row = con.execute("SELECT id FROM users WHERE name = ?", (name,)).fetchone()
        if row:
            return row["id"]
        cur = con.execute("INSERT INTO users (name, created) VALUES (?, ?)",
                          (name, time.time()))
        con.commit()
        return cur.lastrowid


def user_ratings(con, user_id):
    """{topic: (rating, n)} for the topics the user has attempted."""
    with LOCK:
        rows = con.execute("SELECT topic, rating, n FROM ratings WHERE user_id = ?",
                           (user_id,)).fetchall()
    return {row["topic"]: (row["rating"], row["n"]) for row in rows}


def problem_rating(con, problem_id, level):
    """The stored rating, or the seed from the level when never attempted."""
    with LOCK:
        row = con.execute("SELECT rating FROM problems WHERE id = ?",
                          (problem_id,)).fetchone()
    return row["rating"] if row else problem_seed(level)


def recent_seen(con, user_id, n=20):
    with LOCK:
        rows = con.execute(
            "SELECT problem_id FROM attempts WHERE user_id = ? "
            "ORDER BY ts DESC LIMIT ?", (user_id, n)).fetchall()
    return {row["problem_id"] for row in rows}


def record_attempt(con, user_id, problem, answer, correct, certainty,
                   seconds, hint_rung=0):
    """Apply the ELO update for one attempt and store everything about it.

    Returns the attempt as a dict, with the before/after user rating, for the
    API to show the user how their rating moved.
    """
    topic = problem.get("topic", "other")
    with LOCK:
        row = con.execute("SELECT rating, n FROM ratings WHERE user_id = ? AND topic = ?",
                          (user_id, topic)).fetchone()
        user_rating, n = (row["rating"], row["n"]) if row else (USER_SEED, 0)
        prob_rating = problem_rating(con, problem["id"], problem.get("level"))

        score = attempt_score(correct, certainty, seconds, problem.get("level"),
                              hint_rung)
        new_user, new_prob = update(user_rating, prob_rating, score, n)

        ts = time.time()
        cur = con.execute(
            "INSERT INTO attempts (user_id, problem_id, topic, answer, correct, "
            "certainty, seconds, hint_rung, score, elo_before, elo_after, ts) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (user_id, problem["id"], topic, answer, int(bool(correct)),
             int(certainty), float(seconds), int(hint_rung), score,
             user_rating, new_user, ts))
        con.execute(
            "INSERT INTO ratings (user_id, topic, rating, n) VALUES (?, ?, ?, ?) "
            "ON CONFLICT (user_id, topic) DO UPDATE SET rating = ?, n = ?",
            (user_id, topic, new_user, n + 1, new_user, n + 1))
        con.execute(
            "INSERT INTO problems (id, rating, n) VALUES (?, ?, 1) "
            "ON CONFLICT (id) DO UPDATE SET rating = ?, n = n + 1",
            (problem["id"], new_prob, new_prob))
        con.commit()
    return {"attempt_id": cur.lastrowid, "topic": topic, "score": score,
            "elo_before": user_rating, "elo_after": new_user,
            "expected": None, "correct": bool(correct)}
