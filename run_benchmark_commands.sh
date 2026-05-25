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
