#!/usr/bin/env bash
# bench_mbpp.sh — Run the MBPP agent on all (or N) tasks and report pass rate.
#
# Usage:
#   ./scripts/bench_mbpp.sh                   # all 257 tasks
#   ./scripts/bench_mbpp.sh --n 20            # first 20 tasks
#   ./scripts/bench_mbpp.sh --n 20 --shuffle  # 20 random tasks
#   ./scripts/bench_mbpp.sh --n 20 --jobs 4   # 20 tasks, 4 in parallel
#
# Env vars (or set in .env):
#   AGENT_MODEL, AGENT_PROVIDER_URL, AGENT_PROVIDER

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
MOULINETTE_DIR="$PROJECT_DIR/moulinette"

N=0          # 0 = all tasks
JOBS=1       # sequential by default
SHUFFLE=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --n)      N="$2";    shift 2 ;;
        --jobs)   JOBS="$2"; shift 2 ;;
        --shuffle) SHUFFLE=1; shift ;;
        *) echo "Unknown arg: $1"; exit 1 ;;
    esac
done

[ -f "$PROJECT_DIR/.env" ] && set -a && source "$PROJECT_DIR/.env" && set +a

MODEL="${AGENT_MODEL:-mistral-large-latest}"
URL="${AGENT_PROVIDER_URL:-https://api.mistral.ai/v1}"
PROVIDER="${AGENT_PROVIDER:-mistral}"

cd "$MOULINETTE_DIR"
ALL_IDS=$(uv run python -c "
from moulinette.mbpp import InteractMBPP
import random, sys
ids = InteractMBPP().list_tasks(split='test')
if $SHUFFLE: random.shuffle(ids)
if $N > 0:   ids = ids[:$N]
print('\n'.join(str(i) for i in ids))
" 2>/dev/null)
cd "$PROJECT_DIR"

TOTAL=$(echo "$ALL_IDS" | wc -l | tr -d ' ')
DATETIME=$(date +"%Y-%m-%d_%H-%M-%S")
OUT_DIR="$PROJECT_DIR/evaluations/bench_mbpp/$DATETIME"
mkdir -p "$OUT_DIR"

echo "=================================================="
echo "MBPP BENCHMARK"
echo "=================================================="
echo "Model:    $MODEL"
echo "Provider: $PROVIDER"
echo "Tasks:    $TOTAL"
echo "Jobs:     $JOBS"
echo "Output:   $OUT_DIR"
echo "=================================================="

PASS=0
FAIL=0

run_task() {
    local TASK_ID="$1"
    local TASK_FILE="$OUT_DIR/$TASK_ID/task.json"
    local SOL_FILE="$OUT_DIR/$TASK_ID/solution.json"
    mkdir -p "$OUT_DIR/$TASK_ID"

    cd "$MOULINETTE_DIR"
    uv run python -c "
from moulinette.mbpp import InteractMBPP
import json, pathlib
t = InteractMBPP().get_task(task_id=$TASK_ID)
t['task_id'] = str(t['task_id'])  # coerce to str for agent compatibility
pathlib.Path('$TASK_FILE').write_text(json.dumps(t))
" 2>/dev/null
    cd "$PROJECT_DIR"

    uv run agent-mbpp \
        --task-file "$TASK_FILE" \
        --output "$SOL_FILE" \
        --model-name "$MODEL" \
        --provider-url "$URL" \
        --provider "$PROVIDER" \
        > "$OUT_DIR/$TASK_ID/stdout.log" \
        2> "$OUT_DIR/$TASK_ID/stderr.log"
    return $?
}

export -f run_task
export OUT_DIR MODEL URL PROVIDER PROJECT_DIR MOULINETTE_DIR

IDX=0
for TASK_ID in $ALL_IDS; do
    IDX=$((IDX + 1))
    printf "[%3d/%d] Task %s ... " "$IDX" "$TOTAL" "$TASK_ID"

    if run_task "$TASK_ID"; then
        PASS=$((PASS + 1))
        echo "PASS"
    else
        FAIL=$((FAIL + 1))
        echo "FAIL"
    fi
done

echo ""
echo "=================================================="
echo "RESULT: $PASS/$TOTAL passed  ($FAIL failed)"
echo "=================================================="
echo "Solutions: $OUT_DIR"
