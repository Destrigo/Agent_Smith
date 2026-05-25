# MBPP — 10 modelli × 7 task = 70 runs (default)
./run_benchmark.sh

# SWE-bench — stessa cosa
./run_benchmark.sh --benchmark swebench

# Entrambi (non ti conviene — troppo tempo)
./run_benchmark.sh --benchmark both

# Test veloce con 2 task prima di partire sul serio
./run_benchmark.sh --dry-run --n-tasks 2



results/20260525_170031/
├── summary.csv              ← all data
├── BENCHMARK_REPORT.md      ← auto-generated
├── run.log                  ← log complete
└── mbpp/
    ├── qwen_qwen3-235b-a22b_free/
    │   ├── task_seed11.json
    │   ├── solution_seed11.json
    │   └── ...
    └── ...


# 1. Avvia prima solo SWE-bench con 5 modelli veloci (3 task = minimo)
./run_benchmark.sh --benchmark swebench --n-tasks 3 \
  --models "qwen/qwen3-8b:free,google/gemini-2.5-flash-preview-05-20:free,\
meta-llama/llama-4-scout:free,mistralai/devstral-small:free,qwen/qwen3-32b:free"

# 2. Copia il report nella root
cp results/*/BENCHMARK_REPORT.md BENCHMARK_REPORT.md

# 3. Scrivi manualmente ablation + conclusions in BENCHMARK_REPORT.md

# 4. Committa tutto (report + solution.json)
git add results/ BENCHMARK_REPORT.md
git commit -m "feat: add benchmark results"
