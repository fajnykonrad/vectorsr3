# How this copilot is trained on M3Kang

The board runs a 0.8B model that only does inference (llama.cpp), so there is
no gradient training of the network. What we train instead is everything
around it, and all of it is learned from the M3Kang training problems:

1. **A knowledge bank** (`data/index.db`): every training problem embedded
   with bge-small. Its nearest neighbours give the model solved examples
   (`--rag K`) and vote with their labels (the kNN prior).
2. **A letter-bias correction** (fitted letter offsets): on the board the raw
   model answered D 21 times and A 14 times out of 40. A small multinomial
   logistic fit learns one offset per letter so that the fused answer is
   right more often.
3. **A kNN weight**: how much the neighbours' answers should count against
   the model's own letter distribution.

The fusion ships per problem group (with / without OCR options) only when
5-fold cross-validation by problem id says it generalizes beyond a margin
(--margin, 2.0 points). A group without shipped offsets answers with the
model's raw distribution, so a fit that overfits one group cannot hurt the
other. The first version shipped both groups and lost 4.9 held-out points;
the letter tables (fused C 71 vs truth 39) and the per-group breakdown
caught it.

At answer time (`copilot/pipeline.py`) every letter A..E gets

    score(L) = log p_model(L) + offset_L + knn_weight * vote_L

and the argmax is the answer. Deterministic, one letter, no network, and the
60-second budget is untouched: the fusion costs one extra embedding call
(a fraction of a second) plus a loop over the index in memory.

## The training loop

| Step | Where | Command | Time |
| --- | --- | --- | --- |
| 1. Prepare data | Laptop | `python3 laptop/prepare_m3kang.py --languages eng,cat` | ~30 min |
| 2. Copy data | Laptop | `adb push data\train.jsonl data\val.jsonl .../data/` | 1 min |
| 3. Build the index | Board | `python3 build_index.py` | ~4 min |
| 4. Collect signals | Board or laptop | `python3 collect.py` | ~9 s per problem |
| 5. Fit the fusion | Laptop | `python3 fit_model.py` | seconds |
| 6. Measure | Board | `python3 eval.py --limit 50 --name fused-v1` | ~10 min |
| 7. Ship | Laptop | `adb push data\model.json .../data/` | 1 min |

Steps 4 and 5 are the actual training: collect the raw model's letter
distribution and the neighbour votes on the training problems, then fit the
6 parameters (5 offsets + weight) by maximum likelihood, with problems split
by id into a fit part and a held-out part. `fit_model.py` prints both, so the
held-out numbers are honest and never saw the fit.

Run step 4 on the board (tmux, it takes a while), or from the laptop with the
servers forwarded over SSH:

    ssh -L 8081:127.0.0.1:8081 -L 8082:127.0.0.1:8082 arduino@BOARD_IP
    python3 collect.py --limit 300

`collect.py` resumes: keys already in `data/signals.jsonl` are skipped.

## Ablations, one change at a time

`eval.py --name` records every run in `results/ablations.csv`. The flags that
isolate each piece:

| Run | Command |
| --- | --- |
| Raw model, nothing fitted | `python3 eval.py --limit 50 --no-fusion --name raw` |
| Offsets only (no votes) | fit with `--no-index` signals, or set knn_weight to 0 in `data/model.json` |
| Full fusion | `python3 eval.py --limit 50 --name fused-v1` |
| Fusion + few-shot example | `python3 eval.py --limit 50 --rag 1 --name fused-rag1` |
| Hybrid retrieval (lexical bonus) | `RAG_LEXICAL=0.1 python3 eval.py --limit 50 --name fused-lex` |

`FUSION=0` also disables the fusion without editing anything. Before you
report a number, run `--limit 0` on the whole validation set.

## Files

| File | What |
| --- | --- |
| `collect.py` | appends the raw model's signals (probs, votes) to `data/signals.jsonl` |
| `fit_model.py` | fits offsets + kNN weight per group (CV-gated), writes `data/model.json` |
| `diagnose_fusion.py` | per-group accuracy of raw / votes / fused rules on fit and held-out parts |
| `copilot/model.py` | loads `data/model.json` and picks the fused letter (strict group policy) |
| `copilot/pipeline.py` | the answer pipeline the official run measures |
| `copilot/topics.py` | a rule-based topic per problem, for the error analysis |
| `selftest.py` | checks the whole fit + fusion maths on synthetic signals, no server needed |

## Rules this keeps

- One letter A..E per problem, always (grammar at the server, fusion in Python)
- At most 60 seconds per problem (`MARGIN` keeps 3 s free)
- No network at answer time; both servers are on the board
- Temperature 0 and a fixed seed, so the same answers every run

## Honest expectations

The board's raw model is close to random (22.5% on the measured subset,
always-D floor 25%). The fusion attacks measurable waste: the letter bias and
the unused neighbour signal. What it cannot do is make the 0.8B model reason;
for that, better option OCR (`--save-images` and look at the empty ones), a
bigger model in `config.env`, or better retrieval are the levers.
