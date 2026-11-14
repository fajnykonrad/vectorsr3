"""A retrieval index in SQLite: one solved M3Kang problem per row."""
import json
import os
import re
import sqlite3
from array import array

from .embed import embed
from .llm import format_problem

SCHEMA = """
CREATE TABLE IF NOT EXISTS problems (
    key TEXT PRIMARY KEY,   -- id|language
    problem TEXT NOT NULL,  -- the full problem as JSON
    vec BLOB NOT NULL       -- float32 vector
)"""

# RAG_LEXICAL adds a keyword-overlap bonus to the embedding similarity, so
# neighbours that share rare words with the query rank higher. 0 keeps the
# pure embedding search; try 0.1 with eval.py --name and keep what wins.
LEXICAL = float(os.environ.get("RAG_LEXICAL", "0") or 0)
WORD = re.compile(r"\w+", re.UNICODE)


def tokenize(text):
    return {token for token in WORD.findall(text.lower()) if token.isalpha()}


def build(db_path, problems, batch=16):
    db = sqlite3.connect(db_path)
    db.execute(SCHEMA)
    for i in range(0, len(problems), batch):
        chunk = problems[i:i + batch]
        vectors = embed([format_problem(p) for p in chunk])
        db.executemany("INSERT OR REPLACE INTO problems VALUES (?, ?, ?)", [
            (f"{p['id']}|{p['language']}", json.dumps(p, ensure_ascii=False), array("f", v).tobytes())
            for p, v in zip(chunk, vectors)])
        db.commit()
        yield min(i + batch, len(problems))
    db.close()


class Index:
    """Loads every vector into memory once, so each search is a plain loop."""

    def __init__(self, db_path):
        db = sqlite3.connect(db_path)
        self.rows = []
        for key, problem, blob in db.execute("SELECT key, problem, vec FROM problems"):
            vec = array("f")
            vec.frombytes(blob)
            stored = json.loads(problem)
            tokens = tokenize(format_problem(stored)) if LEXICAL else frozenset()
            self.rows.append((key, stored, vec, tokens))
        db.close()

    def search(self, problem, k=1, exclude_id=None):
        """Return up to k (score, problem) pairs, most similar first.

        exclude_id skips the same problem in other languages, so validation
        never retrieves its own translation. With RAG_LEXICAL set, the score
        is cosine similarity plus that weight times the share of the query's
        words the stored problem also has.
        """
        query = embed([format_problem(problem)], query=True)[0]
        query_tokens = tokenize(format_problem(problem))
        scored = []
        for _key, stored, vec, tokens in self.rows:
            if exclude_id and stored["id"] == exclude_id:
                continue
            score = sum(a * b for a, b in zip(query, vec))
            if LEXICAL and tokens:
                overlap = len(query_tokens & tokens)
                if overlap:
                    score += LEXICAL * overlap / len(query_tokens)
            scored.append((score, stored))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return scored[:k]
