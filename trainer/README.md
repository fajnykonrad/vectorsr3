# The Kangaroo Trainer

A learning platform on the board: adaptive practice per topic, an Elo rating
per topic, a 3-rung hint ladder that ends in the answer only on purpose, and
a step-by-step explanation after a wrong answer, served from an offline
solution bank generated with a 4B model.

## The pieces

| File | What it is |
| --- | --- |
| `topics.py` | The 9 topics: anchor sentences for tagging, strategy cues for hints |
| `elo.py` | The rating model: score from an attempt, Elo update for both sides |
| `selector.py` | Picks the next topic (75% adaptive + 25% uniform) and problem |
| `db.py` | SQLite: users, attempts, ratings, problem difficulty |
| `problems.py` | Loads train/val.jsonl plus data/tags.json (UTF-8) |
| `hints.py` | The 3-rung hint ladder (leak-checked) + the explanation chain |
| `server.py` | The web server (stdlib only) + JSON API, bank and prefetch logic |
| `static/index.html` | The page: practice view, chronometer, statistics tab, login gate |
| `build_tags.py` | Tags every problem with a topic using anchor embeddings |
| `smoke.py` | Simulated students that prove the selector adapts |

In `laptop/` (they run where the big model lives, not on the board):

| File | What it is |
| --- | --- |
| `build_solutions.py` | Generates the solution bank with the local 4B, validated |
| `watch_solutions.py` | Shows bank entries while the generation runs |
| `board_check.py` | Verifies the board serves a bank explanation end-to-end |
| `diag_hints.py`, `diag_ladder.py`, `diag_latency.py` | Board diagnostics |

## Run it

On the laptop for development (stub data until preparation finishes):

```bash
.venv/Scripts/python -m trainer.server --port 8000
```

On the board it runs as a systemd service (`math-trainer`, port 8001,
restarts on failure and after reboots - see `board/systemd/` and the main
README). A sailor opens the page, picks a name (or creates one) and plays;
the choice is remembered per browser and every progress record is per name.

## The solution bank (how the explanations are made)

The 0.8B on the board cannot write a correct worked solution. So the
explanations are generated once, on a laptop, by `laptop/build_solutions.py`:

1. For every train/val problem with readable options (eng, cat), it prompts
   **Qwen3.5-4B** (local GGUF, `--reasoning-budget 0`: thinking doubled the
   cost without raising the pass rate) with the problem, its options, the
   correct option's value and the topic's method, and asks for exactly
   3 numbered steps that **check** the correct option rather than derive it.
2. Each candidate must pass `consistent()`: the correct option's value has
   to appear in the **final sentence** (the landing - a bare "6" earlier in
   the text is not enough) and no other letter may be named as correct. One
   retry at temperature 0, then the entry is marked `rejected`.
3. Entries whose text hedges ("Wait, let me recalculate...") are demoted as
   well: 1,771 attempts produced 1,051 clean explanations (levels 0-6).
4. Everything is appended to `data/solutions.jsonl` line by line with a
   flush, so a killed run resumes where it stopped. `--retry-rejected`
   re-attempts the failures.

At startup the trainer loads the `ok` entries into memory and, when a
student fails a problem, `explain_answer()` serves them in this order:

1. **Bank** - 0 ms, 0 tokens, offline.
2. **0.8B verify-backwards** - same scaffold with the options and the
   correct value in the prompt, validated with the same `consistent()`, one
   cold retry.
3. **Deterministic fallback** - the worked neighbour from the retrieval
   index plus the topic's method cue. Always right.

The explanation is generated while the student reads the problem
(`prefetch_explanation`) and shown only after a wrong answer; a correct
answer discards it.

## The hint ladder

1. **The method** - the topic's strategy cue, written by hand, no model.
2. **A first-step hint from the model** - grounded: the prompt carries the
   problem plus its worked solution (the bank entry when there is one, else
   the similar solved problem from retrieval), with the landing sentence
   dropped so the answer is not in front of the model. It only compresses
   the first step (<= 35 words, in the problem's language). The leak check
   rejects any hint naming an option value or the correct letter; one colder
   retry, then rung 1. The board prefills at ~11 tokens/s, so the prompt is
   trimmed (solution to ~200 chars, problem to ~300) and the timeout is 45 s.
3. **The reveal** - the correct letter with its value, only on purpose.

Each hint used scales the attempt score by 0.85.

## The statistics tab

`/api/stats` returns everything in one call: totals (accuracy, current and
best streak, mean time, hints used), the general Elo replayed attempt by
attempt (sparkline), rating bars per topic with accuracy, accuracy per
level, a topic x level heatmap, and the full attempt history (when, answer
vs correct, time, hints, Elo delta).

## API

| Endpoint | What it does |
| --- | --- |
| `GET /api/next?user=` | The next problem (no answer in it), prefetches its explanation |
| `POST /api/answer` | Records the attempt, updates Elo, attaches the explanation on a wrong answer |
| `GET /api/hint?...&rung=1..3` | One rung of the hint ladder |
| `GET /api/stats?user=` | Everything the statistics tab renders |
| `GET /api/users` | Existing sailors with attempt counts (the login gate) |
| `GET /image/<id>_<lang>.png` | The problem image, when exported |

## Test it without a student

```bash
.venv/bin/python -m trainer.smoke
```

Five simulated students, each strong in one topic (80% right) and weak in
another (25%). The checks prove the weak topic gets picked more over time
and ends rated below the strong one.

## The rating model, in one paragraph

Problems start at 800 + 100 per level (grade band 0-7) + 120 per difficulty
(easy / medium / hard, from the exercise number: 1-10, 11-20, 21-30); users
start at 700 overall and 800 per topic. An attempt becomes a score in [0, 1]:
correctness sets the side (right 0.76-1.00, wrong 0.24-0.00) and the
certainty slider, 1 to 5, sets how far from the middle. A fast correct answer
gains 0.10, a slow one loses 0.10, and each hint rung used scales the score
by 0.85. Both sides then follow Elo with K = 56 for the user's first 10
attempts in a topic, then 40, and K = 8 for the problem, so problem
difficulty drifts toward what students make of it. The next topic is chosen
with probability 75% softmax(gap to the user's average rating) + 25% uniform,
the next difficulty follows the topic rating, and the next problem is the one
whose rating sits nearest to the topic rating + 60, never one of the last 20
seen.
