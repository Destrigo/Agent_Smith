#!/usr/bin/env bash
# bench_swebench.sh — Run the SWE-bench agent on all (or N) exam pool tasks.
#
# Usage:
#   ./scripts/bench_swebench.sh              # all 6 exam pool tasks
#   ./scripts/bench_swebench.sh --n 3        # first 3 tasks
#   ./scripts/bench_swebench.sh --shuffle    # randomise order
#
# Env vars (or set in .env):
#   AGENT_MODEL, AGENT_PROVIDER_URL, AGENT_PROVIDER

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
MOULINETTE_DIR="$PROJECT_DIR/moulinette"

N=0       # 0 = all tasks
SHUFFLE=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --n)      N="$2"; shift 2 ;;
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
from moulinette.swebench import EXAM_POOL
import random, sys
ids = list(EXAM_POOL)
if $SHUFFLE: random.shuffle(ids)
if $N > 0:   ids = ids[:$N]
print('\n'.join(ids))
" 2>/dev/null)
cd "$PROJECT_DIR"

TOTAL=$(echo "$ALL_IDS" | wc -l | tr -d ' ')
DATETIME=$(date +"%Y-%m-%d_%H-%M-%S")
OUT_DIR="$PROJECT_DIR/evaluations/bench_swebench/$DATETIME"
mkdir -p "$OUT_DIR"

echo "=================================================="
echo "SWE-BENCH BENCHMARK"
echo "=================================================="
echo "Model:    $MODEL"
echo "Provider: $PROVIDER"
echo "Tasks:    $TOTAL"
echo "Output:   $OUT_DIR"
echo "=================================================="

PASS=0
FAIL=0
IDX=0

for INSTANCE_ID in $ALL_IDS; do
    IDX=$((IDX + 1))
    SAFE_ID=$(echo "$INSTANCE_ID" | tr '/' '__')
    TASK_DIR="$OUT_DIR/$SAFE_ID"
    TASK_FILE="$TASK_DIR/task.json"
    SOL_FILE="$TASK_DIR/solution.json"
    mkdir -p "$TASK_DIR"

    printf "[%d/%d] %s ... " "$IDX" "$TOTAL" "$INSTANCE_ID"

    cd "$MOULINETTE_DIR"
    uv run moulinette_eval dump swebench --task-id "$INSTANCE_ID" --output "$TASK_FILE" \
        >> "$TASK_DIR/dump.log" 2>&1

    cd "$PROJECT_DIR"
    AGENT_START=$(date +%s)
    uv run agent-swebench \
        --task-file "$TASK_FILE" \
        --output "$SOL_FILE" \
        --model-name "$MODEL" \
        --provider-url "$URL" \
        --provider "$PROVIDER" \
        > "$TASK_DIR/stdout.log" \
        2> "$TASK_DIR/stderr.log" && EXEC_OK=1 || EXEC_OK=0
    AGENT_END=$(date +%s)
    DURATION=$((AGENT_END - AGENT_START))

    if [ $EXEC_OK -eq 0 ]; then
        echo "FAIL (agent error, ${DURATION}s)"
        FAIL=$((FAIL + 1))
        continue
    fi

    cd "$MOULINETTE_DIR"
    if uv run moulinette_eval validate swebench "$TASK_FILE" "$SOL_FILE" \
            >> "$TASK_DIR/validate.log" 2>&1; then
        echo "PASS (${DURATION}s)"
        PASS=$((PASS + 1))
    else
        echo "FAIL (${DURATION}s)"
        FAIL=$((FAIL + 1))
    fi
    cd "$PROJECT_DIR"
done

echo ""
echo "=================================================="
echo "RESULT: $PASS/$TOTAL passed  ($FAIL failed)"
printf "Score:  %.0f%%\n" "$(echo "scale=2; $PASS * 100 / $TOTAL" | bc)"
echo "=================================================="
echo "Solutions: $OUT_DIR"
