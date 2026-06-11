#!/usr/bin/env bash
# bench_extra_swe.sh — Run extra SWE-bench tasks (outside EXAM_POOL) across all models.
#
# Usage:
#   ./scripts/bench_extra_swe.sh           # all models, sequential
#   ./scripts/bench_extra_swe.sh --jobs 4  # run N models in parallel per task
#
# Results are saved in evaluations/bench_extra_swe/<datetime>/

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
MOULINETTE_DIR="$PROJECT_DIR/moulinette"

EXTRA_TASKS=(
    "django__django-16082"   # MOD operator output_field
    "django__django-13406"
)

MODELS=(
    "mistral-small-latest|mistral|https://api.mistral.ai/v1"
    "mistral-medium-latest|mistral|https://api.mistral.ai/v1"
    "mistral-large-latest|mistral|https://api.mistral.ai/v1"
    "codestral-latest|mistral|https://api.mistral.ai/v1"
    "devstral-latest|mistral|https://api.mistral.ai/v1"
    "ministral-8b-latest|mistral|https://api.mistral.ai/v1"
    "openai/gpt-oss-120b:free|openrouter|https://openrouter.ai/api/v1"
    "ministral-3b-latest|mistral|https://api.mistral.ai/v1"
    # "mistral-tiny-latest|mistral|https://api.mistral.ai/v1"
    # "open-mistral-nemo|mistral|https://api.mistral.ai/v1"
    "devstral-medium-latest|mistral|https://api.mistral.ai/v1"
)

JOBS=1

while [[ $# -gt 0 ]]; do
    case "$1" in
        --jobs) JOBS="$2"; shift 2 ;;
        *) echo "Unknown arg: $1"; exit 1 ;;
    esac
done

[ -f "$PROJECT_DIR/.env" ] && set -a && source "$PROJECT_DIR/.env" && set +a

DATETIME=$(date +"%Y-%m-%d_%H-%M-%S")
OUT_DIR="$PROJECT_DIR/evaluations/bench_extra_swe/$DATETIME"
LOG_FILE="$OUT_DIR/run.log"
mkdir -p "$OUT_DIR"

log() { printf "[%s] %s\n" "$(date +%H:%M:%S)" "$*" | tee -a "$LOG_FILE"; }

log "=================================================="
log "EXTRA SWE-BENCH RUN"
log "=================================================="
log "Models:      ${#MODELS[@]}"
log "Extra tasks: ${EXTRA_TASKS[*]}"
log "Jobs:        $JOBS"
log "Output:      $OUT_DIR"
log "=================================================="

run_one() {
    local MODEL="$1"
    local PROVIDER="$2"
    local URL="$3"
    local INSTANCE_ID="$4"
    local SHARED_TASK="$5"

    local SAFE_MODEL
    SAFE_MODEL=$(echo "$MODEL" | tr '/: ' '___')
    local SAFE_ID
    SAFE_ID=$(echo "$INSTANCE_ID" | tr '/' '__')
    local TASK_DIR="$OUT_DIR/${SAFE_MODEL}/${SAFE_ID}"
    local SOL_FILE="$TASK_DIR/solution.json"
    local AGENT_LOG="$TASK_DIR/agent.log"
    mkdir -p "$TASK_DIR"
    cp "$SHARED_TASK" "$TASK_DIR/task.json"

    log "  START  [$MODEL] $INSTANCE_ID"
    local START_T
    START_T=$(date +%s)

    cd "$PROJECT_DIR"
    AGENT_MODEL="$MODEL" AGENT_PROVIDER_URL="$URL" AGENT_PROVIDER="$PROVIDER" \
    uv run agent-swebench \
        --task-file "$TASK_DIR/task.json" \
        --output "$SOL_FILE" \
        --model-name "$MODEL" \
        --provider-url "$URL" \
        --provider "$PROVIDER" \
        > "$AGENT_LOG" 2>&1 && local EXEC_OK=1 || local EXEC_OK=0

    local END_T
    END_T=$(date +%s)
    local DUR=$(( END_T - START_T ))

    if [ "$EXEC_OK" -eq 0 ]; then
        echo "FAIL" > "$TASK_DIR/result.txt"
        log "  DONE   [$MODEL] $INSTANCE_ID — FAIL (agent error, ${DUR}s)"
        return
    fi

    cd "$MOULINETTE_DIR"
    if uv run moulinette_eval validate swebench \
            "$TASK_DIR/task.json" "$SOL_FILE" \
            >> "$TASK_DIR/validate.log" 2>&1; then
        echo "PASS" > "$TASK_DIR/result.txt"
        log "  DONE   [$MODEL] $INSTANCE_ID — PASS (${DUR}s)"
    else
        echo "FAIL" > "$TASK_DIR/result.txt"
        log "  DONE   [$MODEL] $INSTANCE_ID — FAIL (validate, ${DUR}s)"
    fi
    cd "$PROJECT_DIR"
}

TASK_DIR_ROOT="$OUT_DIR/_tasks"
mkdir -p "$TASK_DIR_ROOT"

for INSTANCE_ID in "${EXTRA_TASKS[@]}"; do
    log ""
    log "=== Task: $INSTANCE_ID ==="

    SHARED_TASK="$TASK_DIR_ROOT/${INSTANCE_ID}.json"
    if [ ! -f "$SHARED_TASK" ]; then
        log "  Dumping task..."
        cd "$MOULINETTE_DIR"
        uv run moulinette_eval dump swebench \
            --task-id "$INSTANCE_ID" \
            --output "$SHARED_TASK" \
            >> "$TASK_DIR_ROOT/dump.log" 2>&1
        cd "$PROJECT_DIR"
        log "  Task ready: $SHARED_TASK"
    fi

    PIDS=()
    COUNT=0

    for ENTRY in "${MODELS[@]}"; do
        MODEL=$(echo "$ENTRY"   | cut -d'|' -f1)
        PROVIDER=$(echo "$ENTRY" | cut -d'|' -f2)
        URL=$(echo "$ENTRY"     | cut -d'|' -f3)

        run_one "$MODEL" "$PROVIDER" "$URL" "$INSTANCE_ID" "$SHARED_TASK" &
        PIDS+=($!)
        COUNT=$(( COUNT + 1 ))

        if [ "$COUNT" -ge "$JOBS" ]; then
            for PID in "${PIDS[@]}"; do wait "$PID" || true; done
            PIDS=()
            COUNT=0
        fi
    done
    for PID in "${PIDS[@]}"; do wait "$PID" || true; done
done

log ""
log "=================================================="
log "SUMMARY"
log "=================================================="
for INSTANCE_ID in "${EXTRA_TASKS[@]}"; do
    log "Task: $INSTANCE_ID"
    for ENTRY in "${MODELS[@]}"; do
        MODEL=$(echo "$ENTRY" | cut -d'|' -f1)
        SAFE_MODEL=$(echo "$MODEL" | tr '/: ' '___')
        SAFE_ID=$(echo "$INSTANCE_ID" | tr '/' '__')
        RESULT_FILE="$OUT_DIR/${SAFE_MODEL}/${SAFE_ID}/result.txt"
        RESULT=$([ -f "$RESULT_FILE" ] && cat "$RESULT_FILE" || echo "N/A")
        log "  $MODEL: $RESULT"
    done
done

log ""
log "Output: $OUT_DIR"
log "DONE"
