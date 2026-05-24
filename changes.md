# Changes needed in `jiezhang` branch

These are the changes you need to make in your branch **before the merge**.
Each change includes the reason so you understand why it's required.

---

## 1. Create root-level entry points for the agent CLI

The corrector runs:
```bash
uv run python -m agent_mbpp --help
uv run python -m agent_swebench --help
```
Python's `-m` flag looks for a module at the **root** of the project. Your
files live in `agent/cli/` and are not reachable this way. Without these two
files every CLI test fails immediately.

**Create `agent_mbpp.py` at the repository root:**
```python
"""Root-level entry point — allows: uv run python -m agent_mbpp"""
from agent.cli.agent_mbpp import main

if __name__ == "__main__":
    main()
```

**Create `agent_swebench.py` at the repository root:**
```python
"""Root-level entry point — allows: uv run python -m agent_swebench"""
from agent.cli.agent_swebench import main

if __name__ == "__main__":
    main()
```

---

## 2. Fix `pyproject.toml` — add missing dependencies and packages

Your branch is missing `anthropic`, `httpx`, and `anyio` which the sandbox
and MCP client need. The `mcp_servers` package is also missing from the wheel
packages list. Replace your `pyproject.toml` with the merged version:

```toml
[project]
name = "agent-smith"
version = "1.0.0"
description = "Autonomous coding agent for MBPP and SWE-bench"
requires-python = ">=3.10"

dependencies = [
    "pydantic>=2.0",
    "mcp>=1.0",
    "anthropic>=0.34",
    "httpx>=0.27",
    "anyio>=4.0",
    "requests>=2.31",
    "python-dotenv>=1.0",
    "docker>=7.0",
    "PyYAML>=6.0",
]

[project.scripts]
sandbox        = "sandbox.cli:main"
agent-mbpp     = "agent.cli.agent_mbpp:main"
agent-swebench = "agent.cli.agent_swebench:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = [
    "agent", "sandbox", "models", "mydocker",
    "utils", "tools", "mcp_servers", "eval"
]

[dependency-groups]
dev = ["pytest>=8.0", "pytest-asyncio>=0.23"]

[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
```

---

## 3. Add Docker SIGINT / SIGTERM cleanup in SWE-bench agent

The corrector force-kills the agent mid-task and then checks:
```bash
docker ps | grep sweb.eval   # must return nothing
```
If orphan containers remain it's an automatic fail on the Docker lifecycle
test. Add signal handlers wherever you start the Docker container (likely in
`mydocker/manager.py` or `agent/cli/agent_swebench.py`):

```python
import signal
import sys

def _make_cleanup(container):
    def _handler(signum, frame):
        try:
            container.stop(timeout=5)
            container.remove(force=True)
        except Exception:
            pass
        sys.exit(0)
    return _handler

# After container.start():
handler = _make_cleanup(container)
signal.signal(signal.SIGINT,  handler)
signal.signal(signal.SIGTERM, handler)
```

Also wrap the container lifecycle in a `try/finally` so cleanup runs even on
normal exceptions:
```python
try:
    container.start()
    # ... agent loop ...
finally:
    try:
        container.stop(timeout=5)
        container.remove(force=True)
    except Exception:
        pass
```

---

## 4. Make agent limits configurable via CLI arguments

The subject says: *"max_iterations should be a configurable parameter of your
agent loop."* The corrector verifies the limits strictly and may pass custom
values. If limits are hardcoded and wrong, the limits check fails.

In `agent/cli/agent_mbpp.py` add these arguments with the correct MBPP defaults:
```python
parser.add_argument("--max-iterations",    type=int, default=10)
parser.add_argument("--max-input-tokens",  type=int, default=6000)
parser.add_argument("--max-output-tokens", type=int, default=1500)
parser.add_argument("--timeout",           type=int, default=120)
```

In `agent/cli/agent_swebench.py` add these with SWE-bench defaults:
```python
parser.add_argument("--max-iterations",    type=int, default=30)
parser.add_argument("--max-input-tokens",  type=int, default=300000)
parser.add_argument("--max-output-tokens", type=int, default=10000)
parser.add_argument("--timeout",           type=int, default=900)
```

Pass them through to `AgentState` when creating it:
```python
state = AgentState(
    task_id=...,
    benchmark=...,
    max_iterations=args.max_iterations,
    max_input_tokens=args.max_input_tokens,
    max_output_tokens=args.max_output_tokens,
    max_time_seconds=args.timeout,
)
```

---

## 5. Verify `StepMetrics` fields are populated with real values

The corrector inspects `solution.json` and checks:
- `api_url` and `model_name` are non-empty strings in every step
- Token counts are non-zero and look real (not fabricated)
- `total_input_tokens` equals the sum of per-step `input_tokens`
- `total_output_tokens` equals the sum of per-step `output_tokens`

In `agent/core/agent_loop.py`, when you record a step, make sure you capture
these from the actual LLM response:
```python
step = StepMetrics(
    step=state.iteration,
    input_tokens=response.usage.input_tokens,   # from real API response
    output_tokens=response.usage.output_tokens,
    request_time_ms=elapsed_ms,                 # measure with time.perf_counter()
    api_url=self.llm.base_url,                  # the actual provider URL
    model_name=self.llm.model,                  # the actual model name
    llm_output=raw_llm_text,                    # raw text before code extraction
    sandbox_input=extracted_code,               # code sent to sandbox
    sandbox_output=sandbox_result_str,          # sandbox output string
    retries=retry_count,
)
```

---

## 6. Create `BENCHMARK_REPORT.md` skeleton at the repository root

The corrector checks for this file in the first 30 seconds and fails
immediately if it is missing or empty. Create it now with the required
structure — you can fill in the numbers after running the exam scripts.

```markdown
# Benchmark Report — Agent Smith

## 1. Setup

**Models tested (5+):**
| Model | Provider | Notes |
|-------|----------|-------|
| ...   | ...      | ...   |

**Tasks (3+ SWE-bench):**
| task_id | Repository | Description |
|---------|-----------|-------------|
| ...     | ...       | ...         |

**Selection rationale:** [Explain why you chose these models and tasks]

## 2. Results Table

| Model | Task | Pass | Iterations | Input Tokens | Output Tokens | Wall Time (s) |
|-------|------|------|-----------|--------------|---------------|---------------|

## 3. Provider Reliability

| Provider | Avg Response Time (ms) | Avg Retries | Availability |
|----------|----------------------|-------------|--------------|

## 4. Intermediary Metrics

<!-- At least 2 of the following 3 -->

### 4a. Step at which agent first reads/edits the target file
| Model | Task | First read/edit step |
|-------|------|---------------------|

### 4b. Step at which test failures first decrease vs. baseline
| Model | Task | Step |
|-------|------|------|

## 5. Ablation Study

**Change tested:** [Describe the agent change — e.g., adding a step-back prompt]

| Condition | Task | Pass | Avg Iterations | Avg Tokens |
|-----------|------|------|---------------|------------|
| Before    | ...  | ...  | ...           | ...        |
| After     | ...  | ...  | ...           | ...        |

**What changed and why:** [...]

## 6. Conclusions

[Model selection rationale based on the data above]
```

---

## 7. Fill `README.md`

The subject requires a README (Chapter VII). The corrector checks for it.
At minimum it must explain:
- How to install: `uv sync`
- How to run MBPP agent: `uv run python -m agent_mbpp --task-file <path> --output <path> --model-name <model> --provider-url <url>`
- How to run SWE-bench agent: `uv run python -m agent_swebench ...`
- How to launch the sandbox interactively: `uv run sandbox`
- Where API keys go (`.env` file, which variables)
- Brief description of the architecture

---

## Summary checklist

- [ ] `agent_mbpp.py` at root
- [ ] `agent_swebench.py` at root
- [ ] `pyproject.toml` merged deps + packages
- [ ] Docker SIGINT/SIGTERM cleanup
- [ ] `--max-iterations` and limits as CLI args in both agents
- [ ] `StepMetrics` fields populated with real values (api_url, model_name, tokens)
- [ ] `BENCHMARK_REPORT.md` skeleton at root
- [ ] `README.md` filled
