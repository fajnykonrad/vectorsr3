"""The topic taxonomy: anchors for tagging, strategy cues for hints.

One place for the topic list, so laptop/build_tags.py, the board, and the
tests all agree. The keys are stable ids: never rename them, they are stored
in data/tags.json and in the trainer's SQLite database.
"""

TOPICS = {
    "counting": {
        "anchor": "Counting and combinatorics: counting cases, arranging objects, "
                  "permutations, combinations, paths on a grid, the pigeonhole idea.",
        "strategy": "This is a counting problem: list the cases in a tidy order, "
                    "count them, and cross out duplicates.",
    },
    "geometry": {
        "anchor": "Geometry and spatial reasoning: shapes, angles, area, perimeter, "
                  "folding paper, cubes and their nets, points on a grid.",
        "strategy": "This is a geometry problem: draw it, mark what is given, and "
                    "look for equal lengths or symmetry.",
    },
    "arithmetic": {
        "anchor": "Arithmetic and numbers: the four operations, divisibility, "
                  "remainders, digits, fractions, parity, prime numbers.",
        "strategy": "This is a numbers problem: try small cases, watch the digits "
                    "and remainders, and check divisibility.",
    },
    "patterns": {
        "anchor": "Patterns and sequences: continuing a sequence of numbers or "
                  "figures, finding the rule, how each step changes.",
        "strategy": "This is a pattern problem: write the first steps in a row and "
                    "look for what changes from one step to the next.",
    },
    "logic": {
        "anchor": "Logic and deduction: truth-tellers and liars, elimination, "
                  "who-did-what puzzles, orderings and rankings.",
        "strategy": "This is a logic problem: write what each statement rules out, "
                    "and cross out the impossible cases.",
    },
    "measurement": {
        "anchor": "Measurement and units: length, weight, time, money, calendar "
                  "dates, reading scales, clocks and volumes.",
        "strategy": "This is a measurement problem: write the units at every step "
                    "and convert before you compare.",
    },
    "rates": {
        "anchor": "Rates and proportional reasoning: speed, price per item, work "
                  "over time, sharing fairly, percentages.",
        "strategy": "This is a rate problem: find the rate for one item first, "
                    "then multiply.",
    },
    "games": {
        "anchor": "Games and strategy: two players taking turns, winning moves, "
                  "races, tournaments and matches.",
        "strategy": "This is a game problem: think about what the last move must "
                    "look like, and work backwards.",
    },
    "other": {
        "anchor": "A problem that does not fit any other topic: mixed, unusual, "
                  "or hard to classify.",
        "strategy": "Try a small example first, and keep your work in an ordered "
                    "list.",
    },
}

TOPIC_IDS = list(TOPICS)
