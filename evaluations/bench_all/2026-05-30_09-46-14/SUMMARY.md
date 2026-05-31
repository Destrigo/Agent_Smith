# Benchmark Report — 2026-05-30_09-46-14

## Models Tested

| # | Model | Provider | MBPP (257 tasks) | SWE-bench (6 tasks) | Time |
|---|-------|----------|-----------------|---------------------|------|
| 1 | `mistral-small-latest` | mistral | 3/3 (100.0%) | -/- (-) | 0m |
| 2 | `mistral-medium-latest` | mistral | 3/3 (100.0%) | -/- (-) | 0m |
| 3 | `mistral-large-latest` | mistral | 3/3 (100.0%) | -/- (-) | 0m |
| 4 | `codestral-latest` | mistral | 3/3 (100.0%) | -/- (-) | 0m |
| 5 | `devstral-latest` | mistral | 3/3 (100.0%) | -/- (-) | 0m |
| 6 | `ministral-8b-latest` | mistral | 3/3 (100.0%) | -/- (-) | 0m |
| 7 | `nvidia/nemotron-3-super-120b-a12b:free` | openrouter | 3/3 (100.0%) | -/- (-) | 1m |
| 8 | `openai/gpt-oss-120b:free` | openrouter | 3/3 (100.0%) | -/- (-) | 0m |
| 9 | `moonshotai/kimi-k2.6:free` | openrouter | 3/3 (100.0%) | -/- (-) | 3m |
| 10 | `google/gemma-4-31b-it:free` | openrouter | 1/3 (33.3%) | -/- (-) | 3m |
| 11 | `poolside/laguna-m.1:free` | openrouter | 0/3 (0%) | -/- (-) | 4m |

## Results Directory

```
/home/marcotarantino/workstation/agent_smith/evaluations/bench_all/2026-05-30_09-46-14
```

## Notes

- MBPP pass threshold (exam): 4/5 random tasks
- SWE-bench pass threshold (exam): 2/3 random tasks from pool of 6
- Detailed logs per model: `bench_all/<datetime>/<model>/mbpp.log` and `swe.log`
- Individual task solutions: inside `evaluations/bench_mbpp/` and `evaluations/bench_swebench/`
