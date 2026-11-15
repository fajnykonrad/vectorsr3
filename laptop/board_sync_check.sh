#!/usr/bin/env bash
# Compare the board's working tree against origin/main, file by file.
cd ~/vectorsr3 || exit 1
git fetch origin -q
echo "=== HEAD vs origin/main ==="
git log --oneline -1
git log --oneline -1 origin/main
echo
echo "=== uncommitted changes (should be empty) ==="
git status --short
echo
echo "=== key files: identical to origin/main? ==="
for f in trainer/hints.py trainer/server.py trainer/static/index.html \
         trainer/README.md README.md laptop/build_solutions.py \
         laptop/board_check.py laptop/diag_ladder.py \
         docs/trainer-demo.png METODO_FINAL.md \
         copilot/pipeline.py predict.py; do
    if git diff --quiet origin/main -- "$f" 2>/dev/null; then
        echo "OK    $f"
    else
        echo "DIFF  $f"
    fi
done
echo
echo "=== data files the board needs (not in git, by design) ==="
for f in data/solutions.jsonl data/tags.json data/index.db data/train.jsonl \
         data/val.jsonl; do
    if [ -s "$f" ]; then
        echo "OK    $f ($(wc -c < "$f") bytes)"
    else
        echo "MISS  $f"
    fi
done
echo
echo "=== services ==="
systemctl is-active math-llm math-embed math-trainer
