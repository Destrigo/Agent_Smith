# Agent Smith — Live Coding Guide

This document walks through every step the evaluator will ask during the live session.
Keep this open alongside the IDE.

---

## 0. Before the Evaluator Arrives

```bash
cd ~/workstation/agent_smith
cp .env.example .env          # already done — keys are in .env
uv sync                       # confirm deps are installed
docker info                   # confirm Docker is running
make setup-docker             # pull base image if not cached (~2 min)
```

---

## 1. Launch MBPP + SWE-bench in Background

Open **two terminals** and run these simultaneously so both finish while you answer questions.

```bash
# Terminal 1 — MBPP (~5 min)
./exams/exam_mbpp.sh \
  --student-path . \
  --moulinette-path ./moulinette \
  --env-file .env

# Terminal 2 — SWE-bench (~45 min)
./exams/exam_swebench.sh \
  --student-path . \
  --moulinette-path ./moulinette \
  --env-file .env
```

Both scripts start without errors if the API key and Docker are working.
The evaluator continues with the other questions while these run.

---

## 2. Key Files — Know Where They Are

| What | Path |
|------|------|
| SWE-bench system prompt | `agent/prompts/swebench_prompt.txt` |
| MBPP system prompt | `agent/prompts/mbpp_prompt.txt` |
| Agent loop (iterations, token tracking) | `agent/core/agent_loop.py` |
| Sandbox execution engine | `sandbox/core/sandbox.py` |
| LLM provider registry | `agent/llm/providers.py` |
| StepMetrics model | `models/solution.py` |

---

## 3. Inspect a solution.json

After any exam or benchmark run, use moulinette to display a solution:

```bash
cd moulinette
uv run moulinette_eval display ../evaluations/bench_swebench/<datetime>/<task>/solution.json
```

Key fields to point out:
- `system_prompt` — full prompt sent to the LLM
- `steps[*].sandbox_input` — exact Python code sent to sandbox
- `steps[*].sandbox_output` — what the sandbox returned
- `steps[*].model_name` — which model was used per step
- `iterations`, `total_input_tokens`, `total_output_tokens`

---

## 4. Live Modifications (Execution Trace Spot-Check)

The evaluator will ask you to make **4 modifications**, run the agent on one task,
and verify the change appears in `solution.json`. Each takes ~2 min.

**Revert all changes after each one:** `git checkout -- .`

---

### Modification 1 — System Prompt Marker

**What:** Add `[CORRECTION MARKER 42]` at the very start of the SWE-bench system prompt.

**File:** `agent/prompts/swebench_prompt.txt`

```diff
-You are an expert software engineer fixing bugs in real Python repositories.
+[CORRECTION MARKER 42]
+You are an expert software engineer fixing bugs in real Python repositories.
```

**Verify:** In `solution.json` → `system_prompt` starts with `[CORRECTION MARKER 42]`.

---

### Modification 2 — Sandbox Output Marker

**What:** Inject `print('SANDBOX_MARKER_42')` before every user code execution.

**File:** `sandbox/core/sandbox.py` — find the `exec(code, ns_snapshot)` line (~line 331)

```diff
-                exec(code, ns_snapshot)  # noqa: S102
+                ns_snapshot['print']('SANDBOX_MARKER_42')
+                exec(code, ns_snapshot)  # noqa: S102
```

**Verify:** In `solution.json` → every `steps[*].sandbox_output` contains `SANDBOX_MARKER_42`.

---

### Modification 3 — Sandbox Code Marker

**What:** Prepend `# CORRECTOR_CHECK` to the code string before the sandbox receives it.

**File:** `agent/core/agent_loop.py` — find `code, extraction_note = self.extractor.extract(...)` (~line 83)

```diff
             code, extraction_note = self.extractor.extract(
                 llm_response.content)
+            if code is not None:
+                code = "# CORRECTOR_CHECK\n" + code
```

**Verify:** In `solution.json` → every `steps[*].sandbox_input` starts with `# CORRECTOR_CHECK`.

---

### Modification 4 — Model Name Override

**What:** Override the logged `model_name` to `"correction-model-42"` without changing the actual API call.

**File:** `agent/core/agent_loop.py` — find `model_name=llm_response.model_name` (~line 122)

```diff
-                               model_name=llm_response.model_name,
+                               model_name="correction-model-42",
```

**Verify:** In `solution.json` → every `steps[*].model_name` is `"correction-model-42"` AND the task still solves correctly (the API call is unchanged).

---

### Running a Quick Test for Each Modification

Use one MBPP task (fast, ~30 sec):

```bash
# dump task
cd moulinette
uv run moulinette_eval dump mbpp --output /tmp/test_task.json
cd ..

# run agent
uv run agent-mbpp \
  --task-file /tmp/test_task.json \
  --output /tmp/test_solution.json

# inspect
cd moulinette
uv run moulinette_eval display /tmp/test_solution.json
```

---

## 5. MBPP Results Check (Q8)

After Terminal 1 finishes, verify:

```bash
# The exam script prints a summary. Key things to show:
# - Pass threshold: 4/5 tasks passed
# - Max iterations ≤ 10
# - Max input tokens ≤ 6,000
# - Max output tokens ≤ 1,500
# - Timeout ≤ 120 s per task
# - No crash
```

Check a solution.json to show `total_input_tokens` and `iterations` are within limits.

---

## 6. SWE-bench Results Check (Q14)

After Terminal 2 finishes, verify:

```bash
# - Pass threshold: 2/3 randomly selected tasks
# - Max iterations ≤ 30
# - Max input tokens ≤ 300,000
# - Max output tokens ≤ 10,000
# - Timeout ≤ 900 s
# - Docker container started, ran, cleaned up
```

```bash
docker ps                          # should show nothing (container removed)
docker ps -a | grep sweb.eval      # should show nothing
```

---

## 7. Anti-Cheat — Explaining a SWE Solution (Q13 Part D)

Pick `django__django-11066` (6 iterations, clear reasoning chain):

```bash
cd moulinette
uv run moulinette_eval display \
  ../evaluations/bench_swebench/2026-05-31_16-00-51/django__django-11066/solution.json
```

**Walk through:**

1. **Step 1** — `grep_context("content_type")` → finds the file and buggy line in one shot
2. **Step 2** — `edit_file(...)` → patches the exact string
3. **Steps 3-6** — targeted test run → passes → `final_answer(get_patch())`

Point out:
- The agent never fetches from GitHub or external URLs
- `sandbox_input` shows real Python tool calls, not fabricated output
- `system_prompt` contains no task-specific hints or solutions

---

## 8. Benchmark Report

The report is at `BENCHMARK_REPORT.md` in the repo root.

Sections to highlight:
- **§2.5** — `mistral-medium-latest` per-task deep dive (iterations, tokens, first-edit step)
- **§5.1** — Size scaling ablation: capability cliff below 3B, 100% threshold at ~70B
- **§5.2** — Code-specialised vs general: codestral loses to mistral-large on SWE
- **§6** — Cost analysis: $0 total, all free-tier quotas

---

## 9. Common Questions

**Q: Why Mistral and not OpenAI/Anthropic?**
Free tier with no credit card. Mistral's free API has no daily request cap (only rate limits), making it the only provider viable for running 257 MBPP tasks repeatedly.

**Q: Why mistral-medium over mistral-large?**
Same 100% SWE accuracy, but 3× faster (19 s vs 64 s/task), 0 retries vs 22, and 4× fewer tokens. Scale beyond ~70B gives no accuracy gain here.

**Q: How does the agent avoid looking up solutions?**
The system prompt explicitly forbids fetching from GitHub PRs or external URLs. The sandbox blocks network access. The anti-cheat script (`exams/exam_anticheat.sh`) verifies no hardcoded keys or external fetches exist in the code.

**Q: What is the sandbox?**
A restricted Python `exec()` environment. It blocks `os`, `subprocess`, `sys`, `socket`, file access outside `/testbed`, and network calls. Tools are injected as callable functions into the exec namespace.
