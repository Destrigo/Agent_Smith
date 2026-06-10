*This project has been created as part of the 42 curriculum by mtaranti, jiezhang*

# Agent Smith — Autonomous Coding Agent

An autonomous coding agent that solves algorithmic challenges (MBPP) and fixes real-world software bugs (SWE-bench) using a secure Python sandbox, MCP-exposed tools, and a Thought→Code→Observation loop powered by an LLM.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Architecture](#2-architecture)
3. [Quick Start](#3-quick-start)
4. [Running the Agents](#4-running-the-agents)
5. [Exam Scripts (Evaluator)](#5-exam-scripts-evaluator)
6. [Benchmark Results](#6-benchmark-results)
7. [Project Structure](#7-project-structure)
8. [Configuration](#8-configuration)
9. [Running Tests](#9-running-tests)
10. [Providers Supported](#10-providers-supported)
11. [Design Decisions](#11-design-decisions)

---

## 1. Project Overview

Agent Smith is an agentic framework built for two coding benchmarks:

- **MBPP** (Mostly Basic Python Problems) — algorithmic Python tasks. The agent must produce a function that passes all test cases within a secure sandboxed environment.
- **SWE-bench** — real GitHub issues in pre-built Docker containers. The agent must navigate the repository, identify the bug, apply a patch, and produce a valid git diff.

**Default model:** `mistral-large-latest` via the Mistral free API. The model was selected after benchmarking 11 models; it achieves strong SWE-bench accuracy (7/8 tasks) with consistently low iteration counts.

All models run on **free-tier API quotas only** — no paid plans or credits are required.

---

## 2. Architecture

### System Overview

```
┌──────────────────────────────────────────────────────────────┐
│                         CLI Entry Points                     │
│           agent-mbpp               agent-swebench            │
│     (agent/cli/agent_mbpp.py)  (agent/cli/agent_swebench.py) │
└───────────────────────┬──────────────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────────────────────┐
│                       Agent Loop                             │
│  AgentLoop.run()  (agent/core/agent_loop.py)                 │
│                                                              │
│  ┌─────────────┐      ┌──────────────┐   ┌───────────────┐   │
│  │ LLMManager  │─────▶│   Sandbox    │──▶│ SolutionOutput│   │
│  │ (provider)  │      │  .execute()  │   │   (.json)     │   │
│  └─────────────┘      └──────┬───────┘   └───────────────┘   │
│                              │                               │
└──────────────────────────────┼───────────────────────────────┘
                               │  MCP (stdio or HTTP)
                               ▼
              ┌──────────────────────────────┐
              │        MCP Tool Server       │
              │  mcp_tools_mbpp.py       OR  │
              │  mcp_tools_swebench.py       │
              │                              │
              │  Shared tools:               │
              │  - read_file                 │
              │  - edit_file / write_file    │
              │  - list_files                │
              │  - search_code               │
              │  - search_function_or_class_ │
              │    definition_in_code        │
              │  - find_references           │
              │  - run_tests                 │
              │  - get_patch                 │
              │  - run_command               │
              └──────────────────────────────┘
                                │
          ┌─────────────────────┴──────────────────────┐
          │                                            │
          ▼ MBPP                                       ▼ SWE-bench
┌──────────────────────┐                 ┌─────────────────────────┐
│  Docker container    │                 │  Docker container       │
│  python:3.11-slim    │                 │  (per-task SWE image)   │
│  Isolated code exec  │                 │  /testbed = git repo    │
└──────────────────────┘                 └─────────────────────────┘
```

### Agent Loop (Thought → Code → Observation)

```
User Message (task description + tests / issue)
      │
      ▼
┌────────────────────────────────────────────────────────┐
│  while not done and within_limits():                   │
│                                                        │
│  1. LLM call ──▶  Thought + ```python ... ``` block    │
│     stop_sequences = ["<end_code>", "Observation:"]    │
│                                                        │
│  2. CodeExtractor.extract()                            │
│     → Python fence / XML invoke / JSON tool_call /     │
│       ReAct Action                                     │
│                                                        │
│  3. Sandbox.execute(code)                              │
│     → stdout / stderr / error / final_answer signal    │
│                                                        │
│  4. Observation appended to messages                   │
│                                                        │
│  5. If final_answer() called → SolutionOutput          │
└────────────────────────────────────────────────────────┘
```

Stop sequences prevent the LLM from hallucinating execution output: the model stops at `<end_code>` and waits for the real sandbox result before continuing.

**Resource limits per benchmark:**

| Limit | MBPP | SWE-bench |
|-------|------|-----------|
| Max iterations | 10 | 30 |
| Max input tokens | 6,000 | 300,000 |
| Max output tokens | 1,500 | 10,000 |
| Timeout | 120 s | 900 s |

---

## 3. Quick Start

### Prerequisites

- Python ≥ 3.10
- [uv](https://docs.astral.sh/uv/) package manager
- **Docker** — required for both MBPP (code execution) and SWE-bench (repo containers)

> **Docker must be running before any `make` command.**
>
> | Platform | How to start Docker |
> |----------|---------------------|
> | macOS / Windows | Launch **Docker Desktop** from the Applications menu |
> | Linux | `sudo systemctl start docker` or `systemctl --user start docker` |
>
> **Windows note:** the exam scripts require a bash shell. Use **WSL2** with Docker Desktop's WSL2 backend enabled.

### Installation

```bash
# 1. Clone and enter the project
cd agent_smith

# 2. Install the project
uv pip install -e .

# 3. Pull the base Docker image (once per machine)
make setup-docker

# 4. Configure API keys
cp .env.example .env
# Edit .env and fill in at least MISTRAL_API_KEY
```

### API Keys

Edit `.env` and provide the key for whichever provider you want to use. The default provider is Mistral:

```env
# Mistral — https://console.mistral.ai/api-keys  (default)
MISTRAL_API_KEY=your_key_here

# OpenRouter — https://openrouter.ai/settings/keys
OPENROUTER_API_KEY=sk-or-...

# Groq — https://console.groq.com/keys
GROQ_API_KEY=gsk_...

# Gemini — https://aistudio.google.com/apikey
GEMINI_API_KEY=AIza...

# DeepSeek — https://platform.deepseek.com/api_keys
DEEPSEEK_API_KEY=sk-...
```

---

## 4. Running the Agents

### One-shot: dump → run → validate

The easiest way to run a full cycle for either benchmark:

```bash
# MBPP (uses mistral-large-latest by default)
make run-mbpp

# SWE-bench
make run-swebench

# Override the model
make run-mbpp MODEL=mistral-medium-latest
make run-swebench MODEL=mistral-medium-latest
```

### MBPP Agent CLI

```bash
uv run agent-mbpp \
  --task-file /tmp/task.json \
  --output /tmp/solution.json \
  --model-name "mistral-large-latest" \
  --provider-url "https://api.mistral.ai/v1" \
  --provider mistral
```

**All CLI flags for `agent-mbpp`:**

| Flag | Default | Description |
|------|---------|-------------|
| `--task-file` | *(required)* | Path to task JSON file |
| `--output` | *(required)* | Path to write solution JSON |
| `--model-name` | `mistral-large-latest` | Model identifier (or `AGENT_MODEL` env var) |
| `--provider-url` | `https://api.mistral.ai/v1` | API base URL (or `AGENT_PROVIDER_URL` env var) |
| `--provider` | `mistral` | Provider name for key lookup (or `AGENT_PROVIDER` env var) |
| `--max-iterations` | `10` | Maximum agent loop iterations |
| `--max-input-tokens` | `6000` | Maximum cumulative input tokens |
| `--max-output-tokens` | `1500` | Maximum output tokens per request |
| `--timeout` | `120` | Maximum wall-clock seconds per task |
| `--log-level` | `INFO` | Logging verbosity (`DEBUG`, `INFO`, `WARNING`) |

### SWE-bench Agent CLI

```bash
uv run agent-swebench \
  --task-file /tmp/task.json \
  --output /tmp/solution.json \
  --model-name "mistral-large-latest" \
  --provider-url "https://api.mistral.ai/v1" \
  --provider mistral
```

**All CLI flags for `agent-swebench`:**

| Flag | Default | Description |
|------|---------|-------------|
| `--task-file` | *(required)* | Path to task JSON file |
| `--output` | *(required)* | Path to write solution JSON |
| `--model-name` | `mistral-large-latest` | Model identifier |
| `--provider-url` | `https://api.mistral.ai/v1` | API base URL |
| `--provider` | `mistral` | Provider name for key lookup |
| `--max-iterations` | `30` | Maximum agent loop iterations |
| `--max-input-tokens` | `300000` | Maximum cumulative input tokens |
| `--max-output-tokens` | `10000` | Maximum output tokens per request |
| `--timeout` | `900` | Maximum wall-clock seconds per task (15 min) |
| `--log-level` | `INFO` | Logging verbosity |

### Sandbox (Interactive REPL)

The sandbox is a standalone secure Python execution environment with optional MCP tool servers:

```bash
# Default config, no MCP tools (interactive REPL)
uv run sandbox

# With a config file
uv run sandbox config/sandbox_template.json

# With MBPP MCP tools via stdio
uv run sandbox config/sandbox_template.json --mcp-stdio "python mcp_tools_mbpp.py"

# With SWE-bench MCP tools via stdio
uv run sandbox config/sandbox_template.json --mcp-stdio "python mcp_tools_swebench.py"

# With HTTP MCP server (requires the MCP server to be running first)
# Terminal 1:
make mcp-mbpp
# Terminal 2:
uv run sandbox config/sandbox_template.json --mcp-server http://localhost:8000/mcp
```

### MCP Servers (Standalone)

The MCP tool servers can also be started independently for external connections:

```bash
# MBPP MCP server on HTTP port 8000
make mcp-mbpp
# equivalent: uv run python mcp_tools_mbpp.py --transport http --port 8000

# SWE-bench MCP server on HTTP port 8001
make mcp-swebench
# equivalent: uv run python mcp_tools_swebench.py --transport http --port 8001

# stdio transport (default — used by the agents internally)
uv run python mcp_tools_mbpp.py
```

---

## 5. Exam Scripts (Evaluator)

The evaluator uses exam scripts located in `eval_documents/`. The Makefile wraps them for convenience:

```bash
# Run MBPP exam (requires Docker)
make exam-mbpp

# Run SWE-bench exam (requires Docker)
make exam-swebench

# Run sandbox exam
make exam-sandbox

# Run anti-cheat checks
make exam-anticheat
```

Each `make exam-*` target calls the corresponding shell script:

```bash
# Direct invocation (what the Makefile does internally)
./eval_documents/exam_mbpp.sh \
    --student-path . \
    --moulinette-path ./moulinette \
    --env-file .env

./eval_documents/exam_swebench.sh \
    --student-path . \
    --moulinette-path ./moulinette \
    --env-file .env

./eval_documents/exam_sandbox.sh \
    --student-path . \
    --moulinette-path ./moulinette \
    --env-file .env
```

The exam scripts internally:
1. Use `moulinette_eval dump` to fetch a task from the benchmark dataset
2. Call `uv run agent-mbpp` / `uv run agent-swebench` with the default model
3. Pass the solution to `moulinette_eval validate` for scoring

### Anti-cheat: Known False-Positive Warnings

`make exam-anticheat` runs 6 checks and exits with status `REVIEW` (4 warnings, 2 passes). The 4 warnings are all false positives — none represent cheating. They are explained here for the evaluator's reference.

**1. GitHub URLs**
```
eval_documents/sandbox_tests/test_network_blocked.py — api.github.com
```
`test_network_blocked.py` tries to open an HTTPS connection to `api.github.com` to verify that the sandbox **blocks** outbound HTTPS. The connection is expected to fail; the test asserts failure. The URL is a test target, not a solution source.

**2. PR/Issue references in prompts**
```
agent/cli/agent_swebench.py — prompt_path (variable name)
agent/cli/agent_mbpp.py     — prompt_path (variable name)
tests/test_agent.py         — system_prompt= (test assertion)
moulinette/...              — system_prompt (provided evaluator code)
```
The regex catches the word `prompt` near file paths or the word `system`. These are variable names (`prompt_path`) and test assertions (`system_prompt="MY CUSTOM PROMPT"`), not references to external issues. The moulinette matches are in the provided evaluator code, which we did not write.

**3. External HTTP requests**
```
sandbox/core/sandbox.py              — "urllib" inside the blocklist string
eval_documents/sandbox_tests/test_network_blocked.py — urllib.request.urlopen (tests the block)
```
`sandbox.py` contains the string `"urllib"` as an entry in `_BLOCKED_MODULES` — the deny-list that prevents the sandbox from importing it. `test_network_blocked.py` attempts `urllib.request.urlopen` to verify the block fires. Both occurrences demonstrate the security feature working, not a bypass.

**4. SWE-bench dataset access**
```
agent/cli/agent_swebench.py    — benchmark="swebench" (task field value)
tests/test_agent.py            — benchmark="swebench" (test fixture)
tests/test_sandbox_scripts.py  — swebench_mcp_client (fixture name)
moulinette/...                 — throughout (provided evaluator code)
```
The word `swebench` is the name of the benchmark itself. It appears as a string literal for the `benchmark` field in `SolutionOutput` (the output schema), as fixture names in tests, and pervasively throughout the provided `moulinette` package. None of these access the SWE-bench dataset directly; the dataset is accessed only through `moulinette`'s `InteractSweBench` class, which is the intended interface.

---

## 6. Benchmark Results

Full results including per-model, per-task, and ablation analysis are in [BENCHMARK_REPORT.md](BENCHMARK_REPORT.md). Summary below.

### MBPP (257 tasks, full test split)

| Model | Passed | Score |
|-------|--------|-------|
| `openai/gpt-oss-120b:free` | 238/257 | **93%** |
| **`mistral-large-latest`** | **233/257** | **91%** |
| `mistral-small-latest` | 232/257 | 90% |
| `mistral-medium-latest` | 232/257 | 90% |
| `devstral-latest` | 232/257 | 90% |
| `codestral-latest` | 225/257 | 88% |
| `devstral-medium-latest` | 221/257 | 86% |
| `ministral-8b-latest` | 217/257 | 84% |
| `ministral-3b-latest` | 109/257 | 42% |
| `open-mistral-nemo` | 15/257 | 6% |
| `mistral-tiny-latest` | 11/257 | 4% |

### SWE-bench (6 exam-pool tasks + 2 extra)

| Model | Pool (6) | Extra-1 | Extra-2 | Total | Avg Iter | Avg Time (s) |
|-------|----------|---------|---------|-------|----------|--------------|
| `mistral-medium-latest` | 6/6 | 1/1 | 1/1 | 8/8 | 5.5 | 19.1 |
| **`mistral-large-latest`** | **6/6** | **0/1** | **1/1** | **7/8** | **5.8** | **64.1** |
| `ministral-8b-latest` | 4/6 | 0/1 | 1/1 | 5/8 | 12.3 | 42.8 |
| `codestral-latest` | 3/6 | 0/1 | 0/1 | 3/8 | 7.8 | 19.4 |
| `mistral-small-latest` | 3/6 | 0/1 | 0/1 | 3/8 | 14.2 | 437.6 |
| `devstral-medium-latest` | 3/6 | 0/1 | 0/1 | 3/8 | 22.5 | 184.1 |
| `openai/gpt-oss-120b:free` | 2/6 | 0/1 | 1/1 | 3/8 | 18.5 | 154.4 |
| `devstral-latest` | 2/6 | 0/1 | 0/1 | 2/8 | 21.2 | 34.0 |
| `ministral-3b-latest` | 1/6 | 0/1 | 0/1 | 1/8 | 11.2 | 28.3 |
| `mistral-tiny-latest` | 0/6 | — | — | 0/7 | — | — |
| `open-mistral-nemo` | 0/6 | — | — | 0/7 | — | — |

**`mistral-large-latest` passes 7/8 SWE-bench tasks** with a low average iteration count (5.8) and consistent performance, at $0 cost on the Mistral free tier.

### Key Findings

- Scale is the dominant factor for SWE-bench: models below ~70B parameters fail to achieve 100%.
- Code-specialised models (`codestral`, `devstral`) do not outperform general-purpose models of similar scale — SWE-bench rewards multi-step reasoning over raw code generation.
- `mistral-large-latest` edits the correct file at iteration 1 on every pool task — zero wasted exploration.
- All 11 models were evaluated at $0 cost using free-tier APIs only.

---

## 7. Project Structure

```
agent_smith/
│
├── agent/                          # Core agent logic
│   ├── cli/
│   │   ├── agent_mbpp.py           # Entry point: uv run agent-mbpp
│   │   └── agent_swebench.py       # Entry point: uv run agent-swebench
│   ├── core/
│   │   └── agent_loop.py           # Main Thought→Code→Observation loop
│   ├── llm/
│   │   ├── manager.py              # LLMManager: wraps provider calls + retry
│   │   └── providers.py            # Provider registry (Mistral, OpenRouter, …)
│   ├── parsing/
│   │   └── code_extractor.py       # Extracts code blocks from LLM responses
│   └── prompts/
│       ├── mbpp_prompt.txt         # System prompt for MBPP agent
│       └── swebench_prompt.txt     # System prompt for SWE-bench agent
│
├── sandbox/                        # Secure Python execution sandbox
│   ├── core/
│   │   └── sandbox.py              # Sandbox: exec with import hooks, file guards
│   ├── manual/
│   │   └── generator.py            # Builds tool-usage manual from MCP schemas
│   └── cli.py                      # Entry point: uv run sandbox
│
├── mcp_servers/                    # MCP tool implementations
│   ├── mcp_client.py               # Client: connects stdio/HTTP MCP servers
│   ├── mcp_server.py               # Server base: registers tools with MCP
│   └── shared_tools/
│       ├── filesystem/
│       │   ├── read_file.py        # read_file(filepath, start_line?, end_line?)
│       │   ├── edit_file.py        # edit_file(filepath, old_str, new_str)
│       │   ├── write_file.py       # write_file(filepath, content)
│       │   └── list_files.py       # list_files(directory, pattern?)
│       ├── search/
│       │   ├── search_code.py      # search_code(pattern, file_pattern?)
│       │   ├── find_definition.py  # search_function_or_class_definition_in_code(name)
│       │   ├── find_references.py  # find_references(name, filepath?, line?)
│       │   └── grep_context.py     # Internal grep with context lines
│       └── execution/
│           ├── run_tests.py        # run_tests() — MBPP or SWE-bench eval
│           ├── get_patch.py        # get_patch() — git diff HEAD from /testbed
│           └── run_command.py      # run_command(command, workdir)
│
├── mcp_tools_mbpp.py               # Root MCP server for MBPP (stdio + HTTP)
├── mcp_tools_swebench.py           # Root MCP server for SWE-bench (stdio + HTTP)
│
├── models/                         # Pydantic data models
│   ├── task.py                     # MBPPTaskInput, SWEBenchTaskInput
│   ├── solution.py                 # SolutionOutput, StepMetrics
│   ├── sandbox_model.py            # SandboxConfig
│   ├── llm.py                      # Message, LLMRequest, LLMResponse
│   └── agent_state.py              # AgentState (conversation history)
│
├── mydocker/
│   └── manager.py                  # DockerManager: start/stop SWE-bench containers
│
├── config/
│   ├── sandbox_template.json       # Default sandbox configuration
│   └── sandbox_template_swebench.json
│
├── eval_documents/                 # Exam scripts (used by the evaluator)
│   ├── exam_mbpp.sh
│   ├── exam_swebench.sh
│   ├── exam_sandbox.sh
│   └── exam_anticheat.sh
│
├── scripts/                        # Benchmark sweep scripts
│   ├── bench_mbpp.sh               # Run MBPP across N tasks
│   ├── bench_swebench.sh           # Run SWE-bench across exam pool tasks
│   ├── bench_all.sh                # All 11 models × both benchmarks
│   └── bench_extra_swe.sh          # Extra SWE tasks across all models
│
├── moulinette/                     # Official evaluator (submodule / separate venv)
│
├── tests/                          # Test suite
│   ├── test_agent.py
│   ├── test_sandbox.py
│   ├── test_tools.py
│   └── test_sandbox_scripts.py
│
├── evaluations/                    # Committed benchmark output (solution.json files)
│   ├── bench_all/                  # Full multi-model sweep results
│   ├── bench_extra_swe/            # Extra SWE-bench tasks results
│   ├── bench_mbpp/                 # MBPP benchmark results
│   └── bench_swebench/             # SWE-bench benchmark results
│
├── BENCHMARK_REPORT.md             # Full results for 11 models × 8 SWE tasks
├── Makefile                        # All top-level commands
├── pyproject.toml                  # Package manifest + entry points
└── .env.example                    # API key template
```

---

## 8. Configuration

### `.env` Variables

Copy `.env.example` to `.env` and fill in your API keys:

```env
# Provider API keys (fill in the one(s) you use)
MISTRAL_API_KEY=...          # https://console.mistral.ai/api-keys
OPENROUTER_API_KEY=sk-or-... # https://openrouter.ai/settings/keys
GROQ_API_KEY=gsk_...         # https://console.groq.com/keys
GEMINI_API_KEY=AIza...       # https://aistudio.google.com/apikey
DEEPSEEK_API_KEY=sk-...      # https://platform.deepseek.com/api_keys
```

### Agent Defaults via Environment Variables

You can set defaults for the agent CLI flags via environment variables in `.env`:

| Variable | Corresponding Flag | Default |
|----------|--------------------|---------|
| `AGENT_MODEL` | `--model-name` | `mistral-large-latest` |
| `AGENT_PROVIDER_URL` | `--provider-url` | `https://api.mistral.ai/v1` |
| `AGENT_PROVIDER` | `--provider` | `mistral` |

### Makefile Defaults

The Makefile also exposes overridable variables:

```bash
make mbpp MODEL=mistral-medium-latest
make swebench MODEL=mistral-medium-latest \
              SWE_TASK=/tmp/my_task.json \
              SWE_OUT=/tmp/my_solution.json
```

| Variable | Default | Description |
|----------|---------|-------------|
| `MODEL` | `mistral-large-latest` | Model name |
| `URL` | `https://api.mistral.ai/v1` | Provider base URL |
| `PROVIDER` | `mistral` | Provider name for key lookup |
| `MBPP_TASK` | `/tmp/mbpp-task.json` | MBPP input task file path |
| `MBPP_OUT` | `/tmp/mbpp-solution.json` | MBPP output solution file path |
| `SWE_TASK` | `/tmp/swe-task.json` | SWE-bench input task file path |
| `SWE_OUT` | `/tmp/swe-solution.json` | SWE-bench output solution file path |

### Sandbox Configuration (`config/sandbox_template.json`)

The sandbox config controls isolation parameters:

```json
{
  "allowed_directories": ["/tmp"],
  "max_execution_time_seconds": 30,
  "max_memory_mb": 256
}
```

For SWE-bench, the allowed directories are set to `["/testbed", "/tmp/agent"]` and limits are increased to 120 s / 1024 MB.

---

## 9. Running Tests

```bash
# Pull required Docker images first (once per machine)
make setup-docker

# Main project tests (sandbox, agent, tools, eval_documents scripts)
make test
# equivalent: uv run pytest tests/ -v

# eval_documents sandbox scripts only
make test-eval
# equivalent: uv run pytest tests/test_sandbox_scripts.py -v

# Moulinette tests (uses moulinette's own venv)
make test-moulinette
# equivalent: cd moulinette && uv run pytest tests/ -v

# Both suites in sequence
make test-all

# Lint: flake8 + mypy (excludes moulinette and eval_documents)
make lint

# Strict lint: flake8 + mypy --strict
make lint-strict
```

### Rootless Docker Fix (Linux only)

If SWE-bench tests fail with a `lchown` / `500 Server Error`, run once:

```bash
make fix-docker-userns   # requires sudo
```

This patches `/etc/subuid` and `/etc/subgid` to include your own UID/GID in the sub-UID mapping range (required by the rootless Docker daemon when extracting SWE-bench tar archives).

---

## 10. Providers Supported

The `LLMManager` dispatches to any OpenAI-compatible API. Set `--provider-url` to the base URL of your provider and `--provider` to the name used for key lookup in `.env`.

| Provider | `--provider` | `--provider-url` | Key env var |
|----------|-------------|-----------------|-------------|
| Mistral (default) | `mistral` | `https://api.mistral.ai/v1` | `MISTRAL_API_KEY` |
| OpenRouter | `openrouter` | `https://openrouter.ai/api/v1` | `OPENROUTER_API_KEY` |
| Groq | `groq` | `https://api.groq.com/openai/v1` | `GROQ_API_KEY` |
| Gemini | `gemini` | `https://generativelanguage.googleapis.com/v1beta/openai` | `GEMINI_API_KEY` |
| DeepSeek | `deepseek` | `https://api.deepseek.com/v1` | `DEEPSEEK_API_KEY` |

Multi-key rotation is supported for OpenRouter (useful to work around free-tier rate limits):

```env
OPENROUTER_API_KEY_1=key1
OPENROUTER_API_KEY_2=key2
# ... up to 20 keys; the manager rotates automatically on 429 errors
```

---

## 11. Design Decisions

### Sandbox Security Model

The sandbox executes LLM-generated code in an isolated in-process Python namespace running inside a daemon thread. Security is enforced at multiple layers:

| Threat | Defence |
|--------|---------|
| Arbitrary imports | Custom `__import__` hook: explicit allowlist + deny-list (`os`, `sys`, `subprocess`, `socket`, …) |
| Filesystem escapes | `open()` override: checks `os.path.realpath()` against `allowed_directories` |
| Network access | `socket`, `urllib`, `http`, `ssl`, `requests` blocked at import level |
| Infinite loops / CPU | Daemon thread + `thread.join(timeout=N)` |
| Memory exhaustion | `resource.setrlimit(RLIMIT_AS, …)` (Linux) |
| Dangerous builtins | `eval`, `exec`, `compile`, `__import__`, `input`, `breakpoint` removed from namespace |
| Direct builtins access | `__builtins__` replaced with a filtered dict |

### `final_answer()` Mechanism

`final_answer(answer: str)` is injected directly into the sandbox namespace as a Python function (not an MCP tool). It raises `FinalAnswerSignal(BaseException)` which propagates out of `exec()`, is caught by the sandbox, and the answer is stored. This signal works regardless of which MCP server is connected.

### Sandbox Feedback to the LLM

The sandbox always returns an `observation` string describing execution outcome:

| Prefix | Meaning |
|--------|---------|
| `[SANDBOX ERROR]` | No code block found / syntax error / blocked import |
| `[SANDBOX TIMEOUT]` | Time limit exceeded (partial stdout included) |
| `[SANDBOX MEMORY LIMIT]` | Memory limit exceeded |
| `[SANDBOX TRUNCATED]` | stdout > 8,192 bytes (first portion shown) |
| *(normal)* | stdout + stderr concatenated |

### MCP Transport Choice

Both `mcp_tools_mbpp.py` and `mcp_tools_swebench.py` support two transports:

- **stdio** (default): zero-configuration; launched as a subprocess by the sandbox/agent. Used in all exam and benchmark runs.
- **streamable HTTP** (`--transport http --port PORT`): for external connections, multi-client setups, or interactive debugging with the sandbox REPL.

### Tool Design

All 9 shared tools live in `mcp_servers/shared_tools/` and are exposed through both MCP server entry points. Key design choices:

- `read_file` returns output in `N: line` format (like `cat -n`) so the agent can refer to exact line numbers in follow-up `edit_file` calls.
- `edit_file` performs exact-string replacement and fails clearly if `old_str` is not found — preventing silent misapplications.
- `run_tests` is benchmark-aware: for MBPP it executes `$SANDBOX_TEST_CODE`; for SWE-bench it runs `$SANDBOX_EVAL_SCRIPT` inside the Docker container.
- `get_patch` runs `git -c core.fileMode=false diff HEAD` from `/testbed` — the `-c core.fileMode=false` flag avoids spurious diffs from file permission changes.

### Dynamic System Prompt

`sandbox/manual/generator.py` builds the tool-usage section of the system prompt at runtime by introspecting the connected MCP server's schemas. This ensures the prompt always accurately reflects the available tools, regardless of which server variant is launched. `final_answer` documentation is always appended at the end.

### Why `mistral-large-latest` is the Default

After benchmarking 11 models at $0 cost:
- It passes 7/8 SWE-bench tasks (6/6 exam pool + 1 extra) with an average iteration count of 5.8.
- It achieves 91% on MBPP (233/257 tasks), outperforming most other models.
- It edits the correct file at step 1 on every pool task — no wasted exploration iterations.
- It is available on the Mistral free tier at $0 cost.

### Rate Limits and Fallback Models

All evaluations run on the Mistral **free tier** (no paid plan required). Rate limits vary per model:

| Model | Free-tier rate limit | Notes |
|-------|---------------------|-------|
| `mistral-large-latest` | ~0.08 RPS | Default; may be slow for bulk runs |
| `mistral-medium-latest` | ~0.83 RPS | Higher throughput but rate limit can tighten |
| `mistral-medium-2505` | ~0.83 RPS | Pinned snapshot of medium; use if `medium-latest` hits 429s |
| `codestral-2508` | ~2.08 RPS | Fastest free-tier option; best for high-volume bench runs |

If `mistral-large-latest` is too slow for a full MBPP run, `mistral-medium-2505` is the recommended fallback: it matches `medium-latest` accuracy and has a stable rate limit. `codestral-2508` offers the highest throughput for bulk benchmarking but lower SWE-bench accuracy.

Override the model at runtime:

```bash
# Stable medium alternative
make bench-mbpp AGENT_MODEL=mistral-medium-2505

# Fast bulk runs
make bench-mbpp AGENT_MODEL=codestral-2508
```

---

## AI Usage Disclosure

This project used AI assistance (Claude Sonnet) for:
- Drafting boilerplate code and docstrings
- Reviewing the integration contract between the sandbox and the agent loop
- Debugging import path issues during the merge of two parallel branches

All AI-generated code was reviewed, adapted, and tested by the developers before inclusion.

---

## References

- [MBPP dataset](https://huggingface.co/datasets/google-research-datasets/mbpp)
- [SWE-bench](https://www.swebench.com/)
- [Model Context Protocol (MCP)](https://modelcontextprotocol.io/)
- [Mistral AI API](https://docs.mistral.ai/)
- [OpenRouter](https://openrouter.ai/)
- [uv — Python package manager](https://docs.astral.sh/uv/)
