#!/usr/bin/env bash
# bench_all.sh — Run MBPP + SWE-bench sequentially across all configured models.
#
# Usage:
#   ./scripts/bench_all.sh              # all models
#   ./scripts/bench_all.sh --mbpp-only  # skip SWE-bench
#   ./scripts/bench_all.sh --swe-only   # skip MBPP
#   ./scripts/bench_all.sh --n 20       # first 20 MBPP tasks (for quick tests)
#
# Results are saved in evaluations/bench_all/<datetime>/
# A SUMMARY.md is generated at the end.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Format: "model_id|provider|url"
MODELS=(
    # Completed runs (commented out to skip re-running):
    # "mistral-small-latest|mistral|https://api.mistral.ai/v1"           # 232/257 90%  SWE 3/6
    # "mistral-medium-latest|mistral|https://api.mistral.ai/v1"          # 232/257 90%  SWE 6/6
    # "mistral-large-latest|mistral|https://api.mistral.ai/v1"           # 233/257 91%  SWE 6/6
    # "codestral-latest|mistral|https://api.mistral.ai/v1"               # 225/257 88%  SWE 3/6
    # "devstral-latest|mistral|https://api.mistral.ai/v1"                # 232/257 90%  SWE 2/6
    # "ministral-8b-latest|mistral|https://api.mistral.ai/v1"            # 217/257 84%  SWE 4/6
    # "openai/gpt-oss-120b:free|openrouter|https://openrouter.ai/api/v1" # 238/257 93%  SWE 2/6
    # "ministral-3b-latest|mistral|https://api.mistral.ai/v1"            # 109/257 42%  SWE 1/6
    # "devstral-medium-latest|mistral|https://api.mistral.ai/v1"         # 221/257 86%  SWE 3/6
    "mistral-tiny-latest|mistral|https://api.mistral.ai/v1"
    "open-mistral-nemo|mistral|https://api.mistral.ai/v1"
)

RUN_MBPP=1
RUN_SWE=1
MBPP_N=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --mbpp-only) RUN_SWE=0; shift ;;
        --swe-only)  RUN_MBPP=0; shift ;;
        --n)         MBPP_N="$2"; shift 2 ;;
        *) echo "Unknown arg: $1"; exit 1 ;;
    esac
done

[ -f "$PROJECT_DIR/.env" ] && set -a && source "$PROJECT_DIR/.env" && set +a

DATETIME=$(date +"%Y-%m-%d_%H-%M-%S")
OUT_DIR="$PROJECT_DIR/evaluations/bench_all/$DATETIME"
LOG_FILE="$OUT_DIR/run.log"
SUMMARY_FILE="$OUT_DIR/SUMMARY.md"
RESULTS_FILE="$OUT_DIR/results.tsv"
mkdir -p "$OUT_DIR"

log() { printf "[%s] %s\n" "$(date +%H:%M:%S)" "$*" | tee -a "$LOG_FILE"; }

log "=================================================="
log "FULL BENCHMARK RUN"
log "=================================================="
log "Models:  ${#MODELS[@]}"
log "MBPP:    $([ $RUN_MBPP -eq 1 ] && echo yes || echo no)"
log "SWE:     $([ $RUN_SWE  -eq 1 ] && echo yes || echo no)"
log "Output:  $OUT_DIR"
log "=================================================="

printf "model\tprovider\tmbpp_score\tswe_score\telapsed_min\n" > "$RESULTS_FILE"

TOTAL_MODELS=${#MODELS[@]}
MODEL_IDX=0

for ENTRY in "${MODELS[@]}"; do
    MODEL_IDX=$((MODEL_IDX + 1))
    MODEL=$(echo "$ENTRY" | cut -d'|' -f1)
    PROVIDER=$(echo "$ENTRY" | cut -d'|' -f2)
    URL=$(echo "$ENTRY" | cut -d'|' -f3)

    SAFE_MODEL=$(echo "$MODEL" | tr '/: ' '___')
    MODEL_DIR="$OUT_DIR/$SAFE_MODEL"
    mkdir -p "$MODEL_DIR"

    log ""
    log "[$MODEL_IDX/$TOTAL_MODELS] === $MODEL ($PROVIDER) ==="
    MODEL_START=$(date +%s)

    MBPP_SCORE="n/a"
    if [ $RUN_MBPP -eq 1 ]; then
        log "  Running MBPP..."
        MBPP_ARGS=""
        [ -n "$MBPP_N" ] && MBPP_ARGS="--n $MBPP_N"

        MBPP_OUT=$(AGENT_MODEL="$MODEL" AGENT_PROVIDER_URL="$URL" AGENT_PROVIDER="$PROVIDER" \
            "$SCRIPT_DIR/bench_mbpp.sh" $MBPP_ARGS 2>&1 | tee "$MODEL_DIR/mbpp.log")

        MBPP_RESULT=$(echo "$MBPP_OUT" | grep "^RESULT:" | tail -1 || true)
        if [ -n "$MBPP_RESULT" ]; then
            MBPP_PASS=$(echo "$MBPP_RESULT" | grep -o '[0-9]*/' | head -1 | tr -d '/')
            MBPP_TOTAL=$(echo "$MBPP_RESULT" | grep -o '/[0-9]*' | head -1 | tr -d '/')
            if [ -n "$MBPP_PASS" ] && [ -n "$MBPP_TOTAL" ] && [ "$MBPP_TOTAL" -gt 0 ]; then
                MBPP_PCT=$(awk "BEGIN {printf \"%.0f\", $MBPP_PASS * 100 / $MBPP_TOTAL}")
                MBPP_SCORE="${MBPP_PASS}/${MBPP_TOTAL} (${MBPP_PCT}%)"
            fi
        fi
        log "  MBPP: $MBPP_SCORE"
    fi

    SWE_SCORE="n/a"
    if [ $RUN_SWE -eq 1 ]; then
        log "  Running SWE-bench..."
        SWE_OUT=$(AGENT_MODEL="$MODEL" AGENT_PROVIDER_URL="$URL" AGENT_PROVIDER="$PROVIDER" \
            "$SCRIPT_DIR/bench_swebench.sh" 2>&1 | tee "$MODEL_DIR/swe.log")

        SWE_RESULT=$(echo "$SWE_OUT" | grep "^RESULT:" | tail -1 || true)
        if [ -n "$SWE_RESULT" ]; then
            SWE_PASS=$(echo "$SWE_RESULT" | grep -o '[0-9]*/' | head -1 | tr -d '/')
            SWE_TOTAL=$(echo "$SWE_RESULT" | grep -o '/[0-9]*' | head -1 | tr -d '/')
            if [ -n "$SWE_PASS" ] && [ -n "$SWE_TOTAL" ] && [ "$SWE_TOTAL" -gt 0 ]; then
                SWE_PCT=$(awk "BEGIN {printf \"%.0f\", $SWE_PASS * 100 / $SWE_TOTAL}")
                SWE_SCORE="${SWE_PASS}/${SWE_TOTAL} (${SWE_PCT}%)"
            fi
        fi
        log "  SWE:  $SWE_SCORE"
    fi

    MODEL_END=$(date +%s)
    ELAPSED_MIN=$(( (MODEL_END - MODEL_START) / 60 ))
    log "  Done in ${ELAPSED_MIN}m"

    printf "%s\t%s\t%s\t%s\t%s\n" \
        "$MODEL" "$PROVIDER" "$MBPP_SCORE" "$SWE_SCORE" "${ELAPSED_MIN}m" \
        >> "$RESULTS_FILE"
done

log ""
log "Writing summary to $SUMMARY_FILE"

{
    echo "# Benchmark Report — $DATETIME"
    echo ""
    echo "## Models Tested"
    echo ""
    echo "| # | Model | Provider | MBPP (257 tasks) | SWE-bench (6 tasks) | Time |"
    echo "|---|-------|----------|------------------|---------------------|------|"

    IDX=0
    tail -n +2 "$RESULTS_FILE" | while IFS=$'\t' read -r MODEL PROVIDER MBPP_SCORE SWE_SCORE ELAPSED; do
        IDX=$((IDX + 1))
        echo "| $IDX | \`$MODEL\` | $PROVIDER | $MBPP_SCORE | $SWE_SCORE | $ELAPSED |"
    done

    echo ""
    echo "## Results Directory"
    echo ""
    echo "\`\`\`"
    echo "$OUT_DIR"
    echo "\`\`\`"
    echo ""
    echo "## Notes"
    echo ""
    echo "- MBPP pass threshold (exam): 4/5 random tasks"
    echo "- SWE-bench pass threshold (exam): 2/3 random tasks from pool of 6"
    echo "- Detailed logs per model: \`bench_all/<datetime>/<model>/mbpp.log\` and \`swe.log\`"
    echo "- Individual task solutions: inside \`evaluations/bench_mbpp/\` and \`evaluations/bench_swebench/\`"
    echo ""
    echo "## Conclusions"
    echo ""
    echo "*(Fill in: which models to use, which to discard, based on data above.)*"
} > "$SUMMARY_FILE"

log ""
log "=================================================="
log "ALL DONE"
log "=================================================="
log "Summary: $SUMMARY_FILE"
log ""

cat "$SUMMARY_FILE"
