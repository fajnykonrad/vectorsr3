"""Load the problem bank: JSONL plus tags, ready for the selector."""
import json
import os

from .topics import TOPIC_IDS


def load(data_dir="data", languages=None):
    """Every problem from train.jsonl and val.jsonl, with its topic and difficulty.

    Problems without a tag get "other". Problems whose options OCR could not
    read keep options = {} and are still pickable, but the selector prefers
    ones with options.

    difficulty comes from the exercise number, the way Kangaroo scores its
    thirty problems per level: 1-10 easy, 11-20 medium, 21-30 hard.
    """
    tags = {}
    tags_path = os.path.join(data_dir, "tags.json")
    if os.path.exists(tags_path):
        with open(tags_path) as f:
            tags = json.load(f)

    problems = []
    for split in ("train", "val"):
        path = os.path.join(data_dir, f"{split}.jsonl")
        if not os.path.exists(path):
            continue
        with open(path) as f:
            for line in f:
                if not line.strip():
                    continue
                p = json.loads(line)
                topic = tags.get(p["id"], "other")
                if topic not in TOPIC_IDS:
                    topic = "other"
                p["topic"] = topic
                p["difficulty"] = difficulty_of(p["id"])
                p["split"] = split
                problems.append(p)
    if languages:
        keep = set(languages)
        problems = [p for p in problems if p["language"] in keep]
    return problems


def difficulty_of(problem_id):
    """0 easy, 1 medium, 2 hard, from the exercise number in the id."""
    try:
        number = int(problem_id.split("_")[2])
    except (IndexError, ValueError):
        return 0
    return min(2, (number - 1) // 10)


DIFFICULTY_NAMES = ("easy", "medium", "hard")


def problem_ratings_from(con):
    """{problem_id: rating} for every problem the database has seen."""
    return {row["id"]: row["rating"]
            for row in con.execute("SELECT id, rating FROM problems")}
