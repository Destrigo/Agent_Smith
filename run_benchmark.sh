#!/usr/bin/env bash
# =============================================================================
# run_benchmark.sh — Multi-model benchmark runner for Agent Smith
#
# Dumps N tasks, runs every free OpenRouter model on each task, writes
# per-run solution JSONs, appends rows to a CSV, then builds
# BENCHMARK_REPORT.md via eval/report_builder.py.
#
# Usage:
#   ./run_benchmark.sh [OPTIONS]
#
# Options:
#   -b, --benchmark  mbpp | swebench | both      (default: mbpp)
#   -n, --n-tasks    number of tasks per bench    (default: 7)
#   -d, --dry-run    print commands, don't run
#   -m, --models     comma-separated model list   (overrides built-in list)
#   -r, --results    output directory             (default: results/<timestamp>)
#   -h, --help       show this message
#
# Requirements:
#   .env file at project root with OPENROUTER_API_KEY=sk-or-...
#   uv, jq
# =============================================================================
set -euo pipefail
IFS=$'\n\t'

# ── locate project root ───────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ── default configuration ─────────────────────────────────────────────────────
BENCHMARK="mbpp"
N_TASKS=7
DRY_RUN=false
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
RESULTS_DIR="${SCRIPT_DIR}/results/${TIMESTAMP}"
CUSTOM_MODELS=""

PROVIDER_URL="https://openrouter.ai/api/v1"
PROVIDER="openrouter"
MAX_ITER_MBPP=10
MAX_ITER_SWEBENCH=30

# ── 10 free OpenRouter models ─────────────────────────────────────────────────
# All carry the :free suffix — they are available at no cost on OpenRouter.
# Models are ordered roughly by expected coding capability (best first).
DEFAULT_FREE_MODELS=(
    "qwen/qwen3-235b-a22b:free"          # Qwen3 MoE 235B — strongest free model
    "deepseek/deepseek-r1-0528:free"     # DeepSeek-R1 (May 2025 update)
    "deepseek/deepseek-r1:free"          # DeepSeek-R1 baseline
    "google/gemini-2.5-flash-preview-05-20:free"  # Gemini 2.5 Flash
    "meta-llama/llama-4-maverick:free"   # Llama 4 Maverick
    "meta-llama/llama-4-scout:free"      # Llama 4 Scout (lighter)
    "microsoft/phi-4-reasoning:free"     # Phi-4 Reasoning
    "mistralai/devstral-small:free"      # Devstral Small (code-focused)
    "qwen/qwen3-32b:free"                # Qwen3 32B (dense)
    "qwen/qwen3-8b:free"                 # Qwen3 8B  (fast baseline)
)

# ── Task seeds — one per task; fixed seeds guarantee reproducibility ───────────
# Running the same seed twice gives the same task, so re-runs are comparable.
MBPP_SEEDS=(11 22 33 44 55 66 77)
SWEBENCH_SEEDS=(101 202 303 404 505 606 707)

# ── helpers ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GRN='\033[0;32m'; YLW='\033[1;33m'
BLD='\033[1m';    RST='\033[0m'

log()  { echo -e "$(date '+%H:%M:%S') ${BLD}[INFO]${RST}  $*" | tee -a "$LOG"; }
warn() { echo -e "$(date '+%H:%M:%S') ${YLW}[WARN]${RST}  $*" | tee -a "$LOG"; }
ok()   { echo -e "$(date '+%H:%M:%S') ${GRN}[PASS]${RST}  $*" | tee -a "$LOG"; }
fail() { echo -e "$(date '+%H:%M:%S') ${RED}[FAIL]${RST}  $*" | tee -a "$LOG"; }

run() {
    # run CMD — honours DRY_RUN; returns exit code without aborting the script
    if [[ "$DRY_RUN" == "true" ]]; then
        echo "  [DRY] $*" | tee -a "$LOG"
        return 0
    fi
    "$@"
}

usage() {
    grep '^#' "$0" | grep -v '#!/' | sed 's/^# \?//'
    exit 0
}

# ── argument parsing ──────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        -b|--benchmark)  BENCHMARK="$2";       shift 2 ;;
        -n|--n-tasks)    N_TASKS="$2";         shift 2 ;;
        -d|--dry-run)    DRY_RUN=true;         shift   ;;
        -m|--models)     CUSTOM_MODELS="$2";   shift 2 ;;
        -r|--results)    RESULTS_DIR="$2";     shift 2 ;;
        -h|--help)       usage ;;
        *) echo "Unknown option: $1"; usage ;;
    esac
done

# ── resolve model list ────────────────────────────────────────────────────────
if [[ -n "$CUSTOM_MODELS" ]]; then
    IFS=',' read -ra MODELS <<< "$CUSTOM_MODELS"
else
    MODELS=("${DEFAULT_FREE_MODELS[@]}")
fi

# Clamp N_TASKS to available seeds
MAX_SEEDS=${#MBPP_SEEDS[@]}
if (( N_TASKS > MAX_SEEDS )); then
    warn "N_TASKS=${N_TASKS} > available seeds (${MAX_SEEDS}); clamping."
    N_TASKS=$MAX_SEEDS
fi

# ── bootstrap ─────────────────────────────────────────────────────────────────
mkdir -p "$RESULTS_DIR"
LOG="${RESULTS_DIR}/run.log"
CSV="${RESULTS_DIR}/summary.csv"
touch "$LOG"

log "Results directory : $RESULTS_DIR"
log "Benchmark         : $BENCHMARK"
log "Tasks per bench   : $N_TASKS"
log "Models            : ${#MODELS[@]}"
log "Dry-run           : $DRY_RUN"

# ── load API key ──────────────────────────────────────────────────────────────
if [[ -f "${SCRIPT_DIR}/.env" ]]; then
    # shellcheck disable=SC2046
    export $(grep -v '^#' "${SCRIPT_DIR}/.env" | xargs)
fi

if [[ -z "${OPENROUTER_API_KEY:-}" ]]; then
    echo -e "${RED}ERROR: OPENROUTER_API_KEY not set. Create .env with OPENROUTER_API_KEY=sk-or-...${RST}"
    exit 1
fi
log "API key loaded (${#OPENROUTER_API_KEY} chars)"

# ── CSV header ────────────────────────────────────────────────────────────────
echo "benchmark,model,task_id,seed,success,iterations,total_requests,\
input_tokens,output_tokens,total_time_s,avg_req_ms,total_retries,\
first_edit_step,first_pass_step,steps_after_pass,error" > "$CSV"

# ── helper: parse one solution JSON → CSV row ─────────────────────────────────
append_csv_row() {
    local bench="$1" model="$2" seed="$3" sol_json="$4"

    if [[ ! -f "$sol_json" ]]; then
        echo "${bench},${model},MISSING,${seed},false,0,0,0,0,0,0,0,,,,file_not_found" >> "$CSV"
        return
    fi

    # jq -e returns exit 1 if the field is null/false
    local task_id success iters reqs in_tok out_tok time_s retries error
    task_id=$(jq -r '.task_id // "unknown"'               "$sol_json")
    success=$(jq -r '.success'                             "$sol_json")
    iters=$(jq -r   '.iterations // 0'                    "$sol_json")
    reqs=$(jq -r    '.total_requests // 0'                "$sol_json")
    in_tok=$(jq -r  '.total_input_tokens // 0'            "$sol_json")
    out_tok=$(jq -r '.total_output_tokens // 0'           "$sol_json")
    time_s=$(jq -r  '.total_time_seconds // 0'            "$sol_json")
    error=$(jq -r   '.error // ""'                        "$sol_json" | tr ',' ';')

    # per-step derived metrics
    local avg_ms retries first_edit first_pass steps_after
    avg_ms=$(jq -r '
        if (.steps | length) > 0 then
            ([.steps[].request_time_ms] | add) / (.steps | length)
        else 0 end' "$sol_json")

    retries=$(jq -r '[.steps[].retries // 0] | add // 0' "$sol_json")

    first_edit=$(jq -r '
        first(.steps[] | select(.sandbox_input | contains("edit_file("))) |
        .step // ""' "$sol_json" 2>/dev/null || echo "")

    first_pass=$(jq -r '
        first(.steps[] | select(.sandbox_output | ascii_downcase | contains("passed"))) |
        .step // ""' "$sol_json" 2>/dev/null || echo "")

    steps_after=$(jq -r '
        if (.steps | length) > 0 then
            (.iterations // 0) -
            (first(.steps[] |
                select(.sandbox_output | ascii_downcase | contains("passed"))).step
            // .iterations // 0)
        else 0 end' "$sol_json" 2>/dev/null || echo "0")

    printf '%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%.1f,%s,%s,%s,%s,"%s"\n' \
        "$bench" "$model" "$task_id" "$seed" "$success" "$iters" "$reqs" \
        "$in_tok" "$out_tok" "$time_s" "$avg_ms" "$retries" \
        "${first_edit:-}" "${first_pass:-}" "${steps_after:-0}" "$error" \
        >> "$CSV"
}

# ── helper: run one benchmark for one model over N tasks ─────────────────────
run_bench() {
    local bench="$1" model="$2"
    local safe_model="${model//:/_}"      # filesystem-safe name
    local safe_model="${safe_model//\//_}"
    local model_dir="${RESULTS_DIR}/${bench}/${safe_model}"
    mkdir -p "$model_dir"

    local seeds_arr
    if [[ "$bench" == "mbpp" ]]; then
        seeds_arr=("${MBPP_SEEDS[@]:0:$N_TASKS}")
    else
        seeds_arr=("${SWEBENCH_SEEDS[@]:0:$N_TASKS}")
    fi

    local passed=0 failed=0
    for seed in "${seeds_arr[@]}"; do
        local task_json="${model_dir}/task_seed${seed}.json"
        local sol_json="${model_dir}/solution_seed${seed}.json"

        # ── 1. dump task ──────────────────────────────────────────────────
        log "  [${bench}] model=$(basename "$model") seed=${seed} → dumping task"
        if ! run bash -c "cd '${SCRIPT_DIR}/moulinette' && \
            uv run python -m moulinette dump ${bench} \
                --seed ${seed} --output '${task_json}'" 2>>"$LOG"; then
            warn "  dump failed for seed ${seed} — skipping"
            append_csv_row "$bench" "$model" "$seed" "$sol_json"
            continue
        fi

        # ── 2. run agent ──────────────────────────────────────────────────
        local max_iter
        [[ "$bench" == "mbpp" ]] && max_iter=$MAX_ITER_MBPP || max_iter=$MAX_ITER_SWEBENCH

        log "  [${bench}] model=$(basename "$model") seed=${seed} → running agent (max_iter=${max_iter})"
        local start_ts; start_ts=$(date +%s)

        if run uv run agent-"${bench}" \
                --task-file  "$task_json" \
                --output     "$sol_json" \
                --model-name "$model" \
                --provider-url "$PROVIDER_URL" \
                --provider   "$PROVIDER" \
                --max-iterations "$max_iter" \
                2>>"$LOG"; then
            local end_ts; end_ts=$(date +%s)
            local elapsed=$(( end_ts - start_ts ))
            ok "  [${bench}] model=$(basename "$model") seed=${seed} → done in ${elapsed}s"
            (( passed++ )) || true
        else
            local end_ts; end_ts=$(date +%s)
            local elapsed=$(( end_ts - start_ts ))
            fail "  [${bench}] model=$(basename "$model") seed=${seed} → agent exited non-zero (${elapsed}s)"
            (( failed++ )) || true
        fi

        # ── 3. append CSV row ─────────────────────────────────────────────
        append_csv_row "$bench" "$model" "$seed" "$sol_json"
    done

    log "  [${bench}] model=$(basename "$model") finished: ${passed} passed, ${failed} failed"
}

# ── main loop ─────────────────────────────────────────────────────────────────
BENCHES=()
case "$BENCHMARK" in
    both)     BENCHES=("mbpp" "swebench") ;;
    mbpp)     BENCHES=("mbpp") ;;
    swebench) BENCHES=("swebench") ;;
    *) echo "Unknown benchmark: $BENCHMARK"; exit 1 ;;
esac

total_runs=$(( ${#MODELS[@]} * ${#BENCHES[@]} * N_TASKS ))
log "Starting ${total_runs} total agent runs (${#MODELS[@]} models × ${N_TASKS} tasks × ${#BENCHES[@]} bench)"
echo ""

run_index=0
for bench in "${BENCHES[@]}"; do
    log "════════ Benchmark: ${bench^^} ════════"
    for model in "${MODELS[@]}"; do
        (( run_index++ )) || true
        log "── Model ${run_index}/${#MODELS[@]}: ${model}"
        run_bench "$bench" "$model"
        echo ""
    done
done

# ── summary stats from CSV ────────────────────────────────────────────────────
log "════════ Summary ════════"
log "CSV written to: $CSV"

if [[ "$DRY_RUN" == "false" ]] && command -v python3 &>/dev/null; then
    python3 - "$CSV" <<'PYEOF'
import csv, sys, collections

path = sys.argv[1]
by_model = collections.defaultdict(lambda: {"pass": 0, "total": 0})
total_pass = 0; total = 0

with open(path) as f:
    for row in csv.DictReader(f):
        key = row["model"]
        by_model[key]["total"] += 1
        total += 1
        if row["success"].lower() == "true":
            by_model[key]["pass"] += 1
            total_pass += 1

print(f"\n{'Model':<45} {'Pass':>6} {'Rate':>7}")
print("-" * 60)
for model, s in by_model.items():
    rate = s['pass'] / s['total'] * 100 if s['total'] else 0
    print(f"{model:<45} {s['pass']:>3}/{s['total']:<3}  {rate:>5.1f}%")
print("-" * 60)
overall = total_pass / total * 100 if total else 0
print(f"{'TOTAL':<45} {total_pass:>3}/{total:<3}  {overall:>5.1f}%\n")
PYEOF
fi

# ── generate BENCHMARK_REPORT.md ──────────────────────────────────────────────
log "Building BENCHMARK_REPORT.md …"
if [[ "$DRY_RUN" == "false" ]]; then
    run uv run python -m eval.report_builder \
        --solutions-dir "$RESULTS_DIR" \
        --output        "${RESULTS_DIR}/BENCHMARK_REPORT.md" \
        2>>"$LOG" && \
    log "Report: ${RESULTS_DIR}/BENCHMARK_REPORT.md" || \
    warn "report_builder failed — check $LOG for details"
fi

log "All done. Results in: $RESULTS_DIR"
