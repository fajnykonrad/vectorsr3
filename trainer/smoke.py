#!/usr/bin/env python3
"""Simulated students, to test the adaptive loop before the web page exists.

Each student is strong in one topic (80% right), weak in another (25%), and
average elsewhere (55%). If the selector works, averaged over several
students: the weak topic is picked more over time, and ends rated below the
strong one.

    python3 -m trainer.smoke
"""
import random
import statistics
import tempfile

from .db import connect, ensure_user, record_attempt, user_ratings
from .elo import USER_SEED, par_seconds
from .problems import load
from .selector import RECENT, pick_problem, pick_topic
from .topics import TOPIC_IDS

STRONG = "arithmetic"    # 80% right
WEAK = "geometry"        # 25% right
STUDENTS = 5
ROUNDS = 120
WINDOW = 40              # compare the first WINDOW picks with the last WINDOW


def simulate(problem, rng):
    """One fake attempt: answer, certainty 1-5, seconds."""
    if problem["topic"] == STRONG:
        skill = 0.80
    elif problem["topic"] == WEAK:
        skill = 0.25
    else:
        skill = 0.55
    correct = rng.random() < skill
    certainty = rng.choice((4, 5)) if correct else rng.choice((1, 2))
    par = par_seconds(problem.get("level"))
    return correct, certainty, rng.uniform(10, par)


def run_student(seed, problems):
    rng = random.Random(seed)
    with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
        con = connect(tmp.name)
        user = ensure_user(con, f"simulated-{seed}")
        picks, seen = [], []
        for _ in range(ROUNDS):
            rating_map = {t: v[0] for t, v in user_ratings(con, user).items()}
            topic = pick_topic(rating_map, rng)
            problem = pick_problem(problems, topic, rating_map, {},
                                   set(seen[-RECENT:]), rng)
            correct, certainty, seconds = simulate(problem, rng)
            record_attempt(con, user, problem, "?", correct, certainty, seconds)
            picks.append((topic, problem.get("difficulty", 0)))
            seen.append(problem["id"])
        ratings = {t: v[0] for t, v in user_ratings(con, user).items()}
    return picks, ratings


def main():
    problems = load()
    if not problems:
        raise SystemExit("no problems: run laptop/prepare_m3kang.py first")
    if all(p["topic"] == "other" for p in problems):
        # No tags yet (data prep still running): spread the stub data over the
        # topics so the loop has something to adapt between. Test-only.
        print("(no data/tags.json yet: assigning topics round-robin for this test)")
        for i, problem in enumerate(problems):
            problem["topic"] = TOPIC_IDS[i % len(TOPIC_IDS)]

    uniform = 1.0 / len(TOPIC_IDS)
    results = [run_student(seed, problems) for seed in range(STUDENTS)]
    picks_all = [picks for picks, _ in results]
    ratings_all = [r for _, r in results]

    def topic_share(window, topic):
        return statistics.mean(sum(1 for t, _d in p if t == topic) / len(p)
                               for p in window)

    def difficulty_share(window, difficulty):
        return statistics.mean(sum(1 for _t, d in p if d == difficulty) / len(p)
                               for p in window)

    early = topic_share([p[:WINDOW] for p in picks_all], WEAK)
    late = topic_share([p[-WINDOW:] for p in picks_all], WEAK)
    weak_rating = statistics.mean(r.get(WEAK, USER_SEED) for r in ratings_all)
    strong_rating = statistics.mean(r.get(STRONG, USER_SEED) for r in ratings_all)
    mean_rating = statistics.mean(v for r in ratings_all for v in r.values())

    # a weak student stays around the seed in their weak topic, a strong one
    # climbs far above it; the served difficulty should follow, per topic
    def topic_difficulty_share(student_index, window, topic, difficulty):
        picks = picks_all[student_index][window]
        in_topic = [d for t, d in picks if t == topic]
        if not in_topic:
            return 0.0
        return sum(1 for d in in_topic if d == difficulty) / len(in_topic)

    easy_weak_last = statistics.mean(
        topic_difficulty_share(i, slice(-WINDOW, None), WEAK, 0)
        for i in range(STUDENTS))
    easy_weak_first = statistics.mean(
        topic_difficulty_share(i, slice(None, WINDOW), WEAK, 0)
        for i in range(STUDENTS))
    hard_strong_last = statistics.mean(
        topic_difficulty_share(i, slice(-WINDOW, None), STRONG, 2)
        for i in range(STUDENTS))
    hard_strong_first = statistics.mean(
        topic_difficulty_share(i, slice(None, WINDOW), STRONG, 2)
        for i in range(STUDENTS))

    print(f"{STUDENTS} simulated students, {ROUNDS} rounds each: strong topic "
          f"'{STRONG}' (80% right), weak topic '{WEAK}' (25% right).\n")
    print(f"  '{WEAK}' share of picks: first {WINDOW} rounds {early:.0%}, "
          f"last {WINDOW} rounds {late:.0%} (uniform {uniform:.0%})")
    print(f"  ratings: '{WEAK}' {weak_rating:.0f}, '{STRONG}' {strong_rating:.0f}, "
          f"all topics {mean_rating:.0f}")
    print(f"  difficulty of '{WEAK}' picks: easy first {easy_weak_first:.0%}, "
          f"last {easy_weak_last:.0%} | '{STRONG}' picks: hard first "
          f"{hard_strong_first:.0%}, last {hard_strong_last:.0%}\n")
    checks = [
        ("weak topic is picked more over time", late > early),
        (f"weak topic picked above uniform ({uniform:.0%})", late > uniform * 1.3),
        ("weak topic ends below the average rating", weak_rating < mean_rating),
        ("strong topic ends above the average rating", strong_rating > mean_rating),
        ("strong topic ends above the weak one", strong_rating > weak_rating),
        ("low-rated users get mostly easy problems in that topic",
         easy_weak_last > 0.5),
        ("high-rated users get harder problems over time in their topic",
         hard_strong_last > hard_strong_first),
    ]
    for text, ok in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {text}")
    if not all(ok for _, ok in checks):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
