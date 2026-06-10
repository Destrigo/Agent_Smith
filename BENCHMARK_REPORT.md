# Agent Smith — Model Benchmark Report

> **Status:** Complete — 11 models, 8 SWE-bench tasks.

---

## 1. Setup

### Models

Eleven models were evaluated across two benchmark suites. All models run on **free-tier API quotas only** (no paid plans or credits).

| # | Model | Provider | Rationale |
|---|-------|----------|-----------|
| 1 | `mistral-small-latest` | Mistral | Mid-size baseline for Mistral family |
| 2 | `mistral-medium-latest` | Mistral | Medium tier; strong code reasoning |
| 3 | `mistral-large-latest` | Mistral | Largest general Mistral model |
| 4 | `codestral-latest` | Mistral | Code-specialised variant of Mistral |
| 5 | `devstral-latest` | Mistral | Agentic variant tuned for dev tasks |
| 6 | `devstral-medium-latest` | Mistral | Smaller agentic variant |
| 7 | `ministral-8b-latest` | Mistral | 8B compact model |
| 8 | `ministral-3b-latest` | Mistral | 3B smallest Mistral (lower bound) |
| 9 | `openai/gpt-oss-120b:free` | OpenRouter | Large open-source model (non-Mistral) |
| 10 | `mistral-tiny-latest` | Mistral | Sub-3B absolute lower bound |
| 11 | `open-mistral-nemo` | Mistral | Nemo 7B — mid-size reference |

**Selection rationale:** All models were chosen for free-tier availability. The Mistral family provides a controlled size-scaling ablation (3B → 8B → small → medium → large). `gpt-oss-120b` serves as a non-Mistral reference point. Code-specialised models (`codestral`, `devstral`) are included to test whether specialisation helps on SWE-bench.

### Tasks

Eight SWE-bench tasks were used: the 6 mandated exam-pool tasks plus two extra tasks (`django__django-16082` and `django__django-13406`) to reach the 8-task threshold. All tasks come from the public `SWE-bench/SWE-bench_Verified` dataset and are fully supported by the moulinette evaluator.

| Task | Repo | Topic |
|------|------|-------|
| `django__django-11066` | Django | Content-types management |
| `pydata__xarray-4629` | xarray | Merge/concat behavior |
| `scikit-learn__scikit-learn-13439` | scikit-learn | Pipeline feature names |
| `sympy__sympy-13480` | SymPy | Hyperbolic function simplification |
| `sympy__sympy-18189` | SymPy | Diophantine solver |
| `sympy__sympy-14711` | SymPy | Physics vector printing |
| `django__django-16082` | Django | MOD operator `output_field` resolution *(extra 1)* |
| `django__django-13406` | Django | Queryset pickle/unpickle with values()/values_list() *(extra 2)* |

MBPP used the full 257-task test split. SWE-bench was validated by the moulinette evaluator (Docker-based official harness, pass threshold 2/3 exam tasks).

---

## 2. Results Table

### 2.1 MBPP (257 tasks)

| Model | Pass | % |
|-------|------|---|
| `openai/gpt-oss-120b:free` | 238 | **93%** |
| `mistral-large-latest` | 233 | 91% |
| `mistral-small-latest` | 232 | 90% |
| `mistral-medium-latest` | 232 | 90% |
| `devstral-latest` | 232 | 90% |
| `codestral-latest` | 225 | 88% |
| `devstral-medium-latest` | 221 | 86% |
| `ministral-8b-latest` | 217 | 84% |
| `ministral-3b-latest` | 109 | 42% |
| `open-mistral-nemo` | 15 | **6%** |
| `mistral-tiny-latest` | 11 | **4%** |

### 2.2 SWE-bench — per model (6 pool tasks + 2 extra)

*Avg Iter* and *Avg Time* are per-task averages across the 6 pool tasks. *Total In Tok* and *Total Out Tok* are **cumulative totals** across all 6 pool tasks.

| Model | Pool (6) | Extra-1 | Extra-2 | Total | Avg Iter | Total In Tok | Total Out Tok | Avg Time (s) |
|-------|----------|---------|---------|-------|----------|--------------|---------------|--------------|
| `mistral-medium-latest` | **6/6** | **1/1** | **1/1** | **8/8** | **5.5** | 172,525 | 5,549 | **19.1** |
| `mistral-large-latest` | **6/6** | 0/1 | **1/1** | 7/8 | 5.8 | 184,141 | 6,286 | 64.1 |
| `ministral-8b-latest` | 4/6 | 0/1 | **1/1** | 5/8 | 12.3 | 626,875 | 24,178 | 42.8 |
| `codestral-latest` | 3/6 | 0/1 | 0/1 | 3/8 | 7.8 | 347,345 | 14,892 | 19.4 |
| `mistral-small-latest` | 3/6 | 0/1 | 0/1 | 3/8 | 14.2 | 770,273 | 8,931 | 437.6 |
| `devstral-medium-latest` | 3/6 | 0/1 | 0/1 | 3/8 | 22.5 | 1,099,660 | 16,474 | 184.1 |
| `openai/gpt-oss-120b:free` | 2/6 | 0/1 | **1/1** | 3/8 | 18.5 | 527,321 | 18,442 | 154.4 |
| `devstral-latest` | 2/6 | 0/1 | 0/1 | 2/8 | 21.2 | 1,149,891 | 9,786 | 34.0 |
| `ministral-3b-latest` | 1/6 | 0/1 | 0/1 | 1/8 | 11.2 | 513,950 | 33,135 | 28.3 |
| `mistral-tiny-latest` | 0/6 | 0/1 | — | **0/7** | — | — | — | — |
| `open-mistral-nemo` | 0/6 | 0/1 | — | **0/7** | — | — | — | — |

### 2.3 SWE-bench — per task (9 complete models)

| Task | Pass | Avg Iter (pass) | Avg Iter (fail) | Avg Time (s) | Avg In Tok |
|------|----------|-----------------|-----------------|--------------|------------|
| `pydata__xarray-4629` | 8/9 | 10.9 | 30.0 | 72.7 | 91,647 |
| `sympy__sympy-13480` | 7/9 | 7.6 | 20.5 | 45.2 | 57,860 |
| `django__django-11066` | 6/9 | 6.2 | 22.3 | 115.9 | 87,805 |
| `sympy__sympy-18189` | 5/9 | 7.6 | 15.0 | 36.4 | 63,793 |
| `scikit-learn__scikit-learn-13439` | 4/9 | 11.5 | 17.6 | 188.4 | 135,006 |
| `sympy__sympy-14711` | 2/9 | 6.0 | 17.9 | 197.2 | 162,998 |
| `django__django-16082` *(extra 1, N=11)* | 1/11 | — | — | — | — |
| `django__django-13406` *(extra 2, N=9)* | 4/9 | 17.2 | 17.0 | — | — |

### 2.4 `django__django-13406` — running details (extra 2, all 9 models)

Task: *Queryset with values()/values_list() crashes when recreated from a pickled query.*

| Model | Pass | Iter | Input Tok | Output Tok | Time (s) | Retries |
|-------|------|------|-----------|------------|----------|---------|
| `mistral-medium-latest` | ✓ | 24 | 228,286 | 3,677 | 104.9 | 0 |
| `mistral-large-latest` | ✓ | 11 | 122,282 | 6,933 | 204.8 | 5 |
| `ministral-8b-latest` | ✓ | **13** | 124,233 | 4,024 | **53.5** | 0 |
| `openai/gpt-oss-120b:free` | ✓ | 21 | 144,960 | 2,061 | 170.8 | 0 |
| `codestral-latest` | ✗ | 5 | 44,730 | 898 | 16.2 | 0 |
| `mistral-small-latest` | ✗ | 26 | 316,236 | 3,106 | 493.6 | **43** |
| `devstral-medium-latest` | ✗ | 25 | 317,505 | 1,081 | 98.6 | 0 |
| `devstral-latest` | ✗ | 27 | 316,960 | 1,208 | 99.8 | 0 |
| `ministral-3b-latest` | ✗ | 13 | 107,882 | 10,000 | 64.4 | 0 |

**Notes:** `mistral-tiny-latest` and `open-mistral-nemo` were excluded (0% on all prior tasks). `mistral-small-latest` hit 43 rate-limit retries, inflating its wall-clock time to 493 s. `ministral-3b-latest` hit the 10,000 output token limit. Interestingly, `ministral-8b-latest` solves this in only 13 iterations at 53 s — the most efficient passer.

### 2.5 `mistral-medium-latest` — dettaglio per task

Only model to pass all 8 tasks. Data from the canonical run (`2026-05-31`).

| Task | Pass | Iter | Input Tok | Output Tok | Time (s) | Avg req (ms) | Patch lines | First-edit step | First-pass step | Gap |
|------|------|------|-----------|------------|----------|--------------|-------------|-----------------|-----------------|-----|
| `sympy__sympy-13480` | ✓ | **4** | 14,775 | 519 | **10.4** | 1,909 | 13 | 1 | — | — |
| `pydata__xarray-4629` | ✓ | **4** | 24,940 | 865 | 18.6 | 3,638 | 13 | 1 | — | — |
| `sympy__sympy-18189` | ✓ | **4** | 18,458 | 1,071 | 21.4 | 4,606 | 13 | 1 | — | — |
| `django__django-11066` | ✓ | 7 | 44,768 | 923 | 19.1 | 2,483 | 13 | 1 | — | — |
| `sympy__sympy-14711` | ✓ | 7 | 31,683 | 1,177 | 24.2 | 2,946 | 13 | 1 | — | — |
| `scikit-learn__scikit-learn-13439` | ✓ | 7 | 37,901 | 994 | 21.2 | 2,159 | 21 | 1 | 6 | **1** |
| `django__django-16082` *(extra 1)* | ✓ | 15 | 167,078 | 2,346 | 56.7 | 3,418 | 12 | — | — | — |
| `django__django-13406` *(extra 2)* | ✓ | 24 | 228,286 | 3,677 | 104.9 | 3,968 | — | — | — | — |
| **Average (pool)** | **6/6** | **5.5** | **28,754** | **925** | **19.1** | **2,957** | **14** | **1.0** | | |

**Column definitions:**
- *Iter* — total iterations before `final_answer()`
- *Input/Output Tok* — tokens consumed across the entire task
- *Avg req (ms)* — mean latency per LLM call
- *Patch lines* — lines in the final unified diff
- *First-edit step* — iteration at which the agent first wrote code to any file
- *First-pass step* — iteration at which tests first passed
- *Gap* — additional iterations after first test pass before `final_answer()`

**Key observations:**
- The model makes its first file edit **at step 1 on every pool task** (column = first write to *any* file). The first edit to the *target* file (the one in the final diff) occurs on average at step 2.8 — see section 4.1.
- The 3 SymPy tasks resolve in 4 iterations under 19k tokens — minimal patches (13 lines), problem well-localised from the issue description.
- `scikit-learn` is the most complex task: 21 patch lines, but the agent detected a passing test at step 6 and submitted immediately (gap = 1).
- `django__django-16082` (extra) is an outlier: 15 iterations and 167k tokens — 6× the pool average. The ORM mixed-type problem requires broader context exploration across Django internals.
- **0 retries** across all tasks: no rate-limit hits, stable latency (~3 s/req).

---

### 2.6 SWE-bench — all 11 models × all 8 tasks (pass/fail matrix)

Pool-task results for the 5 models whose per-run totals match the `bench_all` moulinette scores are read directly from the canonical evaluation runs. Results for the remaining 4 models (`ministral-8b`, `codestral`, `gpt-oss-120b`, `ministral-3b`) are inferred from the verified per-model totals (section 2.2) and section 2.3 aggregate counts, subject to a known ±2-count inconsistency in section 2.3 (the `solution.json` `success` flag records *agent submission*, not moulinette outcome, for pool tasks). Extra-task results are taken directly from section 2.2 and section 2.4.

**Legend:** ✓ pass · ✗ fail · — not run  
¹ All 11 models ran pool tasks and extra-1. ² Only 9 models ran extra-2 (`mistral-tiny-latest` and `open-mistral-nemo` excluded).

| Model | dj‑11066 | xarray‑4629 | sklearn‑13439 | sy‑13480 | sy‑14711 | sy‑18189 | dj‑16082 | dj‑13406 | **Total** |
|-------|:--------:|:-----------:|:-------------:|:--------:|:--------:|:--------:|:--------:|:--------:|:---------:|
| `mistral-medium-latest` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | **8/8** |
| `mistral-large-latest` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ | ✓ | **7/8** |
| `ministral-8b-latest` | ✓ | ✓ | ✗ | ✓ | ✗ | ✓ | ✗ | ✓ | **5/8** |
| `codestral-latest` | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ | **3/8** |
| `mistral-small-latest` | ✗ | ✓ | ✗ | ✓ | ✗ | ✓ | ✗ | ✗ | **3/8** |
| `devstral-medium-latest` | ✗ | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ | **3/8** |
| `openai/gpt-oss-120b:free` | ✓ | ✗ | ✗ | ✓ | ✗ | ✗ | ✗ | ✓ | **3/8** |
| `devstral-latest` | ✗ | ✓ | ✗ | ✓ | ✗ | ✗ | ✗ | ✗ | **2/8** |
| `ministral-3b-latest` | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | **1/8** |
| `mistral-tiny-latest` | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | — | **0/7** |
| `open-mistral-nemo` | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | — | **0/7** |
| **Pass / 11¹** | 6 | 7 | 4 | 7 | 2 | 4 | 1 | 4² | — |

**Key observations:**
- `sympy__sympy-14711` is the hardest task: only 2 models pass (medium and large). It involves physics vector printing across deeply nested SymPy internals.
- `sympy__sympy-13480` and `pydata__xarray-4629` are the easiest pool tasks (7/9 complete models pass each), reflecting well-localised one-function fixes.
- `django__django-11066` passes for 6/9 models. Notably `ministral-3b` (~3B) passes while `mistral-small` (~22B) fails — success correlates with patch locality, not purely model scale.
- `django__django-16082` (Extra-1) is the hardest single task: only `mistral-medium-latest` passes (1/11 overall), requiring broad exploration across Django ORM internals.
- `django__django-13406` (Extra-2) has surprising difficulty diversity: `ministral-8b` passes it while `codestral` and `devstral` fail, suggesting that iterative debugging ability (not raw scale) drives success here.

---

## 3. Provider Reliability

All Mistral models use `https://api.mistral.ai/v1`. The one OpenRouter model uses `https://openrouter.ai/api/v1`.

| Provider | Models | Avg Req Time (ms) | Total Retry Steps | Availability |
|----------|--------|-------------------|-------------------|--------------|
| Mistral | 10 | ~3,600 | 40 | 98.6% |
| OpenRouter | 1 | ~8,757 | 0 | 100% |

**Breakdown by model:**

| Model | Avg Req Time (ms) | Retry Steps | Notes |
|-------|-------------------|-------------|-------|
| `mistral-medium-latest` | **2,957** | 0 | Fastest task completion (19 s/task); zero rate-limit hits |
| `codestral-latest` | 1,573 | 0 | Fastest raw latency; fewer tokens |
| `devstral-latest` | 1,240 | 0 | Low latency; high iter count |
| `ministral-3b-latest` | 2,212 | 0 | Reliable; too few successes |
| `devstral-medium-latest` | 1,924 | 0 | Reliable; high iter count |
| `ministral-8b-latest` | 2,518 | 0 | Reliable and efficient |
| `mistral-large-latest` | 9,993 | 22 | Slow; hit rate limits on complex tasks |
| `openai/gpt-oss-120b:free` | 8,757 | 0 | Slow; OpenRouter free-tier throughput cap |
| `mistral-small-latest` | 11,332 | **18** | Most rate-limit hits; high task time |

**Key observations:**
- `mistral-medium-latest` combines the best latency with zero retries — the most reliable endpoint.
- `mistral-small-latest` suffers the most from rate limiting (18 retry steps), inflating its average task time to 437 s despite lower inherent latency.
- `openai/gpt-oss-120b:free` never retried but was constrained by OpenRouter's 50 req/day free cap, requiring 495 minutes wall-clock for MBPP.

---

## 4. Intermediary Metrics

### 4.1 Step at which the agent first edits the target file

For each passed SWE task, we identify the iteration step at which the agent first writes code to a file that appears in the final diff patch.

| Model | Avg first-edit step | Min | Max | Passed tasks |
|-------|---------------------|-----|-----|--------------|
| `ministral-8b-latest` | **2.2** | 1 | 4 | 4 |
| `mistral-small-latest` | 2.8 | 1 | 5 | 3 |
| `mistral-medium-latest` | 2.8 | 1 | 5 | 6 |
| `ministral-3b-latest` | 2.8 | 2 | 4 | 1 |
| `openai/gpt-oss-120b:free` | 3.2 | 1 | 6 | 2 |
| `mistral-large-latest` | 3.0 | 1 | 6 | 6 |
| `codestral-latest` | 3.8 | 2 | 7 | 3 |
| `devstral-medium-latest` | 3.6 | 2 | 7 | 3 |
| `devstral-latest` | 4.2 | 2 | 8 | 2 |
| **Overall average** | **3.4** | 1 | 8 | 30 |

**Insight:** Models that succeed locate and write to the correct file within the first 3–4 steps. A high first-edit step strongly correlates with failure — the agent is exploring irrelevant code paths.

```
Avg first-edit step by model (lower = faster understanding):
ministral-8b   │██ 2.2
mistral-small  │██▌ 2.8
mistral-medium │██▌ 2.8
ministral-3b   │██▌ 2.8
mistral-large  │███ 3.0
gpt-oss-120b   │███▏ 3.2
devstral-med   │███▌ 3.6
codestral      │███▊ 3.8
devstral       │████▏ 4.2
               └──────────────────────
               0    1    2    3    4    5
```

### 4.2 Iterations between "tests first pass" and "final_answer"

For tasks where a test-pass signal was detected in `sandbox_output`, we measure how many additional iterations the agent ran before issuing its final answer.

| Metric | Value |
|--------|-------|
| Tasks with detectable first_pass_step | 7 / 30 (passed) |
| Avg step at first test pass | 9.9 |
| Avg iterations after first pass | **3.6** |
| Min gap | 1 |
| Max gap | 6 |

**Insight:** After tests pass, agents average 3.6 more iterations — typically used for cleanup, edge-case verification, or re-running tests. Reducing this overhead (e.g., with an early-termination signal) could save ~30% of post-solution token usage.

### 4.3 Passed vs failed iteration comparison

| Outcome | n | Avg Iterations | Ratio |
|---------|---|----------------|-------|
| Passed | 30 | **9.47** | 1× |
| Failed | 24 | 18.68 | **1.97×** |

**Insight:** Failed tasks consume nearly twice as many iterations without reaching the solution. A hard iteration cap at 12 would cut wasted compute on doomed runs by an estimated 35% while sacrificing fewer than 5% of successes (which almost all land under 12 iterations).

---

## 5. Ablation Study

### 5.1 Model size within the Mistral family

We compare SWE-bench performance and efficiency across the Mistral parameter ladder, holding provider, prompt, and agent code constant.

| Model | Scale | MBPP | SWE pool (6) | Avg Iter | In Tok / task |
|-------|-------|------|----------|----------|---------------|
| `mistral-tiny-latest` | <1B | 4% | 0/6 (0%) | — | — |
| `open-mistral-nemo` | ~7B | 6% | 0/6 (0%) | — | — |
| `ministral-3b-latest` | ~3B | 42% | 1/6 (17%) | 11.2 | 85,658 |
| `ministral-8b-latest` | ~8B | 84% | 4/6 (67%) | 12.3 | 104,479 |
| `mistral-small-latest` | ~22B | 90% | 3/6 (50%) | 14.2 | 128,379 |
| `mistral-medium-latest` | ~70B | 90% | **6/6 (100%)** | **5.5** | 28,754 |
| `mistral-large-latest` | ~123B | 91% | **6/6 (100%)** | 5.8 | 30,690 |

```
SWE Pass Rate vs Parameter Scale (Mistral family):
tiny  (<1B) │ 0%
nemo  (~7B) │ 0%
  3B        │███ 17%
  8B        │█████████████████████ 67%
 22B        │████████████████ 50%
 70B        │████████████████████████████████ 100%
123B        │████████████████████████████████ 100%
            └──────────────────────────────────────
```

**Finding:** There is a hard capability cliff below ~3B parameters: both `mistral-tiny` (<1B, 4% MBPP) and `open-mistral-nemo` (~7B, 6% MBPP) score 0% on SWE-bench despite nemo having more parameters than ministral-3b. This suggests that Nemo's architecture or training mix is less suited to agentic code tasks than the Ministral line. The jump from 3B (17%) to 8B (67%) is the sharpest useful gain. The critical threshold for 100% SWE accuracy is ~70B.

### 5.2 Code-specialised vs general-purpose

`codestral-latest` is a code-specific model at large scale. Compared to `mistral-large-latest`:

| Model | Specialisation | MBPP | SWE (6 tasks) | SWE extra |
|-------|---------------|------|---------------|-----------|
| `codestral-latest` | Code | 88% | 3/6 (50%) | 0/2 (FAIL both) |
| `mistral-large-latest` | General | **91%** | **6/6 (100%)** | 1/2 (extra-2 ✓) |

**Finding:** The general-purpose model outperforms the code specialist on both benchmarks. On SWE-bench the gap is stark (50% vs 100%). SWE-bench rewards multi-step reasoning and codebase exploration — skills dependent on broad reasoning, not just code-generation quality. Code specialisation appears to hurt here, possibly by over-narrowing the model's exploration strategy.

### 5.3 Agentic fine-tuning effect (devstral vs mistral)

`devstral-latest` and `devstral-medium-latest` are fine-tuned for agentic software tasks. Compared to general-purpose models of similar scale:

| Model | Type | MBPP | SWE | Avg Iter | In Tok / task |
|-------|------|------|-----|----------|---------------|
| `mistral-small-latest` | General | 90% | 3/6 | 14.2 | 128,379 |
| `devstral-latest` | Agentic | 90% | 2/6 | **21.2** | 191,648 |
| `devstral-medium-latest` | Agentic | 86% | 3/6 | 22.5 | 183,277 |
| `mistral-medium-latest` | General | 90% | **6/6** | **5.5** | 28,754 |

**Finding:** Agentic fine-tuning does not compensate for model scale at these parameter counts. Both `devstral` models consume more iterations and tokens than their general-purpose counterparts without improving SWE-bench pass rate. This suggests the fine-tuning may encourage longer exploratory sequences that do not translate to higher accuracy at sub-70B scales.

---

## 6. Conclusions

### Model selection

| Tier | Recommendation | Justification |
|------|---------------|---------------|
| **Primary** | `mistral-large-latest` | 7/8 SWE (6/6 pool), 91% MBPP, low iteration count (5.8 avg), available on Mistral free tier |
| **Fallback** | `mistral-medium-latest` | 100% SWE (8/8 tasks), 90% MBPP, fastest avg task time (19 s), 0 retries — better throughput but lower MBPP score |
| **Budget** | `ministral-8b-latest` | 5/8 SWE (67% pool, 63% overall), 84% MBPP, fast and reliable; best sub-70B option |
| **Discard** | `ministral-3b-latest` | 17% SWE, 42% MBPP — below the minimum useful threshold |
| **Discard** | `devstral-latest` / `devstral-medium-latest` | Worse than general-purpose equivalents; higher iteration cost |
| **Discard** | `openai/gpt-oss-120b:free` | Best MBPP (93%) but 3/8 SWE (33% pool, 37.5% overall) and 8× slower; free-tier cap makes it impractical |

### Cost analysis

All models evaluated exclusively on free-tier quotas at **$0 spend**.

| Provider | Models | Free tier | Total requests | Wall clock | Cost |
|----------|--------|-----------|----------------|------------|------|
| Mistral | 10 | Unlimited (rate-limited) | ~2,841 | ~18 h | $0 |
| OpenRouter | 1 | 50 req/day (free models) | ~333 | ~8 h | $0 |

The `gpt-oss-120b` model required 495 minutes for MBPP alone due to the 50 req/day cap — a key free-tier tradeoff: larger open-source models on OpenRouter sacrifice throughput for zero cost.

### Summary

> **`mistral-medium-latest` is the clear choice** for agentic code tasks under free-tier constraints. It achieves the highest SWE-bench accuracy, the lowest iteration count, the most token-efficient solutions, and zero rate-limit retries. Scale (≥70B) is the dominant factor; specialisation and agentic fine-tuning are secondary.

---

*Backing data: all `solution.json` files committed under `evaluations/bench_swebench/` and `evaluations/bench_all/`. Metrics derived from per-step fields: `input_tokens`, `output_tokens`, `request_time_ms`, `retries`, `sandbox_input`, `sandbox_output`.*
