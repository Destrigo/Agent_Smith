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

# ── models to benchmark ───────────────────────────────────────────────────────
# Format: "model_id|provider|url"
MODELS=(
    "mistral-small-latest|mistral|https://api.mistral.ai/v1"
    "mistral-medium-latest|mistral|https://api.mistral.ai/v1"
    "mistral-large-latest|mistral|https://api.mistral.ai/v1"
    "codestral-latest|mistral|https://api.mistral.ai/v1"
    "devstral-latest|mistral|https://api.mistral.ai/v1"
    "ministral-8b-latest|mistral|https://api.mistral.ai/v1"
    "nvidia/nemotron-3-super-120b-a12b:free|openrouter|https://openrouter.ai/api/v1"
    "openai/gpt-oss-120b:free|openrouter|https://openrouter.ai/api/v1"
    "moonshotai/kimi-k2.6:free|openrouter|https://openrouter.ai/api/v1"
    "google/gemma-4-31b-it:free|openrouter|https://openrouter.ai/api/v1"
    "poolside/laguna-m.1:free|openrouter|https://openrouter.ai/api/v1"
)

# ── arg parsing ───────────────────────────────────────────────────────────────
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

# ── setup ─────────────────────────────────────────────────────────────────────
[ -f "$PROJECT_DIR/.env" ] && set -a && source "$PROJECT_DIR/.env" && set +a

DATETIME=$(date +"%Y-%m-%d_%H-%M-%S")
OUT_DIR="$PROJECT_DIR/evaluations/bench_all/$DATETIME"
LOG_FILE="$OUT_DIR/run.log"
SUMMARY_FILE="$OUT_DIR/SUMMARY.md"
mkdir -p "$OUT_DIR"

log() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$LOG_FILE"; }

# ── header ────────────────────────────────────────────────────────────────────
log "=================================================="
log "FULL BENCHMARK RUN"
log "=================================================="
log "Models:  ${#MODELS[@]}"
log "MBPP:    $([ $RUN_MBPP -eq 1 ] && echo yes || echo no)"
log "SWE:     $([ $RUN_SWE  -eq 1 ] && echo yes || echo no)"
log "Output:  $OUT_DIR"
log "=================================================="

# ── summary tracking ──────────────────────────────────────────────────────────
declare -A MBPP_SCORE
declare -A SWE_SCORE
declare -A MODEL_TIME

# ── run each model ────────────────────────────────────────────────────────────
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

    # ── MBPP ──────────────────────────────────────────────────────────────────
    MBPP_PASS="-"
    MBPP_TOTAL="-"
    MBPP_PCT="-"

    if [ $RUN_MBPP -eq 1 ]; then
        log "  Running MBPP..."
        MBPP_ARGS=""
        [ -n "$MBPP_N" ] && MBPP_ARGS="--n $MBPP_N"

        MBPP_OUT=$(AGENT_MODEL="$MODEL" AGENT_PROVIDER_URL="$URL" AGENT_PROVIDER="$PROVIDER" \
            "$SCRIPT_DIR/bench_mbpp.sh" $MBPP_ARGS 2>&1 | tee "$MODEL_DIR/mbpp.log")

        MBPP_RESULT=$(echo "$MBPP_OUT" | grep "^RESULT:" | tail -1 || true)
        if [ -n "$MBPP_RESULT" ]; then
            MBPP_PASS=$(echo "$MBPP_RESULT" | grep -oP '\d+(?=/)' || echo "0")
            MBPP_TOTAL=$(echo "$MBPP_RESULT" | grep -oP '(?<=/)\d+' || echo "?")
            if [ "$MBPP_TOTAL" != "?" ] && [ "$MBPP_TOTAL" -gt 0 ]; then
                MBPP_PCT=$(echo "scale=1; $MBPP_PASS * 100 / $MBPP_TOTAL" | bc)%
            fi
        fi
        log "  MBPP: $MBPP_PASS/$MBPP_TOTAL ($MBPP_PCT)"
    fi

    MBPP_SCORE["$MODEL"]="$MBPP_PASS/$MBPP_TOTAL ($MBPP_PCT)"

    # ── SWE-bench ─────────────────────────────────────────────────────────────
    SWE_PASS="-"
    SWE_TOTAL="-"
    SWE_PCT="-"

    if [ $RUN_SWE -eq 1 ]; then
        log "  Running SWE-bench..."
        SWE_OUT=$(AGENT_MODEL="$MODEL" AGENT_PROVIDER_URL="$URL" AGENT_PROVIDER="$PROVIDER" \
            "$SCRIPT_DIR/bench_swebench.sh" 2>&1 | tee "$MODEL_DIR/swe.log")

        SWE_RESULT=$(echo "$SWE_OUT" | grep "^RESULT:" | tail -1 || true)
        if [ -n "$SWE_RESULT" ]; then
            SWE_PASS=$(echo "$SWE_RESULT" | grep -oP '\d+(?=/)' || echo "0")
            SWE_TOTAL=$(echo "$SWE_RESULT" | grep -oP '(?<=/)\d+' || echo "?")
            if [ "$SWE_TOTAL" != "?" ] && [ "$SWE_TOTAL" -gt 0 ]; then
                SWE_PCT=$(echo "scale=1; $SWE_PASS * 100 / $SWE_TOTAL" | bc)%
            fi
        fi
        log "  SWE:  $SWE_PASS/$SWE_TOTAL ($SWE_PCT)"
    fi

    SWE_SCORE["$MODEL"]="$SWE_PASS/$SWE_TOTAL ($SWE_PCT)"

    MODEL_END=$(date +%s)
    ELAPSED=$(( (MODEL_END - MODEL_START) / 60 ))
    MODEL_TIME["$MODEL"]="${ELAPSED}m"
    log "  Done in ${ELAPSED}m"
done

# ── write SUMMARY.md ──────────────────────────────────────────────────────────
log ""
log "Writing summary to $SUMMARY_FILE"

{
    echo "# Benchmark Report — $DATETIME"
    echo ""
    echo "## Models Tested"
    echo ""
    echo "| # | Model | Provider | MBPP (257 tasks) | SWE-bench (6 tasks) | Time |"
    echo "|---|-------|----------|-----------------|---------------------|------|"

    IDX=0
    for ENTRY in "${MODELS[@]}"; do
        IDX=$((IDX + 1))
        MODEL=$(echo "$ENTRY" | cut -d'|' -f1)
        PROVIDER=$(echo "$ENTRY" | cut -d'|' -f2)
        echo "| $IDX | \`$MODEL\` | $PROVIDER | ${MBPP_SCORE[$MODEL]:-n/a} | ${SWE_SCORE[$MODEL]:-n/a} | ${MODEL_TIME[$MODEL]:-?} |"
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
} > "$SUMMARY_FILE"

log ""
log "=================================================="
log "ALL DONE"
log "=================================================="
log "Summary: $SUMMARY_FILE"
log ""

cat "$SUMMARY_FILE"
