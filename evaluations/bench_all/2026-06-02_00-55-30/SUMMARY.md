# Benchmark Report — 2026-06-02_00-55-30

## Models Tested

| # | Model | Provider | MBPP (257 tasks) | SWE-bench (6 tasks) | Time |
|---|-------|----------|------------------|---------------------|------|
| 1 | `devstral-medium-latest` | mistral | 221/257 (86%) | 3/6 (50%) | 286m |

## Results Directory

```
/Users/jennyzhang/Documents/jiemin_zhang/common_core/Agent_Smith/evaluations/bench_all/2026-06-02_00-55-30
```

## Notes

- MBPP pass threshold (exam): 4/5 random tasks
- SWE-bench pass threshold (exam): 2/3 random tasks from pool of 6
- Detailed logs per model: `bench_all/<datetime>/<model>/mbpp.log` and `swe.log`
- Individual task solutions: inside `evaluations/bench_mbpp/` and `evaluations/bench_swebench/`

## Ablation Study

*(Fill in manually: one before/after comparison of a prompt or tool change.)*

| Change | Model | Task | Pass Before | Pass After | Iter Before | Iter After |
| ------ | ----- | ---- | ----------- | ---------- | ----------- | ---------- |

## Conclusions

*(Fill in: which models to use, which to discard, based on data above.)*
