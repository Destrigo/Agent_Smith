*This project has been created as part of the 42 curriculum by marcotarantino, jiezhang*

# Agent Smith — Autonomous Coding Agent

An autonomous coding agent that solves algorithmic challenges (MBPP) and fixes real-world software bugs (SWE-bench) using a secure Python sandbox, MCP-exposed tools, and a Thought→Code→Observation loop powered by an LLM.

---

## Description

Agent Smith connects an LLM to a secure, isolated Python execution environment. In each iteration the agent:
1. **Thinks** — reasons about the problem
2. **Writes code** — produces a Python snippet calling available tools
3. **Observes** — sees the sandbox output (stdout/stderr, tool results, errors)
4. Repeats until `final_answer()` is called or resource limits are hit

Two benchmarks are supported:
- **MBPP** — algorithmic Python tasks; agent must produce a function that passes all test cases
- **SWE-bench** — real GitHub issues in Docker containers; agent must produce a git patch

---

## Instructions

### Requirements

- Python ≥ 3.10
- [uv](https://docs.astral.sh/uv/) package manager
- **Docker** — required for **both MBPP and SWE-bench** (MBPP runs submitted code in an isolated container; SWE-bench manages full repo containers)

> **Docker must be running before any `make` command.**  
> Without it every evaluation target will fail immediately with a clear error message.
>
> | Platform | How to start Docker |
> |----------|-------------------|
> | macOS / Windows | Launch **Docker Desktop** from the Applications menu |
> | Linux | `sudo systemctl start docker` &nbsp;or&nbsp; `systemctl --user start docker` |
>
> After starting Docker, pull the base image once:
> ```bash
> make setup-docker   # docker pull python:3.11-slim
> ```
>
> **Windows note:** the exam scripts (`exam_mbpp.sh`, `exam_swebench.sh`) require a bash shell. Use **WSL2** with Docker Desktop's WSL2 backend enabled — they will not run in PowerShell or CMD.

### Installation

```bash
cd agent_smith
uv pip install -e .
```

### Running the Sandbox (interactive REPL)

```bash
# Default config, no MCP tools
uv run sandbox

# With a config file
uv run sandbox config/sandbox_template.json

# With stdio MCP server
uv run sandbox config/sandbox_template.json --mcp-stdio "python mcp_tools_mbpp.py"

# With HTTP MCP server
uv run sandbox config/sandbox_template.json --mcp-server http://localhost:8000
```

### Running the MBPP Agent

```bash
uv run agent-mbpp \
  --task-file path/to/task.json \
  --output path/to/solution.json \
  --model-name "qwen/qwen3-235b-a22b" \
  --provider-url "https://openrouter.ai/api/v1" \
  --provider openrouter
```

### Running the SWE-bench Agent

```bash
uv run agent-swebench \
  --task-file path/to/task.json \
  --output path/to/solution.json \
  --model-name "qwen/qwen3-235b-a22b" \
  --provider-url "https://openrouter.ai/api/v1" \
  --provider openrouter
```

### Environment Variables

Create a `.env` file at the project root:

```env
OPENROUTER_API_KEY=your_key_here
# For multi-key rotation (up to 20 keys):
OPENROUTER_API_KEY_1=key1
OPENROUTER_API_KEY_2=key2
```

### Running MCP Servers Standalone

```bash
# MBPP MCP server (stdio — default)
python mcp_tools_mbpp.py

# SWE-bench MCP server (HTTP transport)
python mcp_tools_swebench.py --transport http --port 8001
```

---

## Resources

### AI Usage Disclosure

This project used AI assistance (Claude Sonnet) for:
- Drafting boilerplate code and docstrings
- Reviewing integration contract between sandbox and agent loop
- Debugging import path issues during the merge of two parallel branches

All AI-generated code was reviewed, adapted, and tested by the developers before inclusion.

### References

- [MBPP dataset](https://huggingface.co/datasets/google-research-datasets/mbpp)
- [SWE-bench](https://www.swebench.com/)
- [Model Context Protocol (MCP)](https://modelcontextprotocol.io/)
- [Anthropic Claude API](https://docs.anthropic.com/)
- [OpenRouter](https://openrouter.ai/)
- [uv — Python package manager](https://docs.astral.sh/uv/)

---

## System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                      Agent Loop                          │
│  AgentLoop.run()                                         │
│  ┌────────────┐    ┌─────────────┐    ┌──────────────┐  │
│  │ LLMManager │───▶│  Sandbox    │───▶│ SolutionOut  │  │
│  │ (provider) │    │ .execute()  │    │ (.json)      │  │
│  └────────────┘    └──────┬──────┘    └──────────────┘  │
│                           │                              │
└───────────────────────────┼──────────────────────────────┘
                            │ MCP (stdio or HTTP)
                            ▼
              ┌─────────────────────────┐
              │   MCP Tool Server       │
              │  mcp_tools_mbpp.py  OR  │
              │  mcp_tools_swebench.py  │
              │                         │
              │  Shared tools:          │
              │  - read_file            │
              │  - edit_file            │
              │  - list_files           │
              │  - search_code          │
              │  - search_function_...  │
              │  - find_references      │
              │  - run_tests            │
              │  - get_patch            │
              │  - run_command          │
              └─────────────────────────┘
```

**Key design decisions:**

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Sandbox isolation | In-process threading | Persistent namespace across steps; sufficient for single-task runs |
| Import control | Allowlist + `__import__` hook | No third-party library required; standard Python |
| Timeout | `thread.join(timeout=N)` | Simple; daemon thread is abandoned but not killed (Python limitation) |
| Memory limit | `RLIMIT_AS` (Linux) | OS-level enforcement; no polling needed |
| MCP transport | stdio (primary) + HTTP | stdio is zero-config; HTTP allows multi-client setups |

---

## Agent Loop Explanation

```
User Message (task)
      │
      ▼
┌─────────────────────────────────────────────────────┐
│  while not done and within_limits():                 │
│                                                      │
│  1. LLM call  ─▶  Thought + ```python ... ``` block │
│     stop_sequences=["<end_code>", "Observation:"]   │
│                                                      │
│  2. CodeExtractor.extract()                          │
│     → Python fence / XML invoke / JSON tool_call /  │
│       ReAct Action                                   │
│                                                      │
│  3. Sandbox.execute(code)                            │
│     → stdout/stderr/error/final_answer              │
│                                                      │
│  4. Observation appended to messages                 │
│                                                      │
│  5. If final_answer received → SolutionOutput        │
└─────────────────────────────────────────────────────┘
```

**Stop sequences** prevent the LLM from hallucinating execution output: the model stops at `<end_code>` and waits for the real sandbox observation.

**Token limits** per benchmark:
- MBPP: max 10 iterations, 6 000 input tokens, 1 500 output tokens, 120 s
- SWE-bench: max 30 iterations, 300 000 input tokens, 10 000 output tokens, 900 s

---

## Sandbox Design

The sandbox runs LLM-generated code in an **isolated in-process Python namespace** using a daemon thread with a configurable timeout.

### Security Layers

| Threat | Defence |
|--------|---------|
| Arbitrary imports | Custom `__import__` hook: allowlist + explicit deny-list (`os`, `sys`, `subprocess`, `socket`, …) |
| File-system escapes | `open()` override: checks `os.path.realpath()` against `allowed_directories` |
| Network access | `socket`, `urllib`, `http`, `ssl`, `requests` blocked at import level |
| Infinite loops / CPU | Daemon thread + `thread.join(timeout=N)` |
| Memory exhaustion | `resource.setrlimit(RLIMIT_AS, ...)` (Linux) |
| Dangerous builtins | `eval`, `exec`, `compile`, `__import__`, `input`, `breakpoint` removed from namespace |
| Direct builtins access | `__builtins__` replaced with filtered dict |

### `final_answer()` Mechanism

`final_answer(answer: str)` is injected directly into the sandbox namespace (not an MCP tool).  
It raises `FinalAnswerSignal(BaseException)` which propagates out of `exec()`, is caught by the sandbox, and the answer is stored.  
This signal works regardless of which MCP server is connected.

### Feedback to the LLM

The sandbox always returns an `observation` string:
- `[SANDBOX ERROR]` — no code block / syntax error / blocked import
- `[SANDBOX TIMEOUT]` — time limit exceeded (partial output included)
- `[SANDBOX MEMORY LIMIT]` — memory limit exceeded
- `[SANDBOX TRUNCATED]` — stdout > 8 000 bytes (first portion shown)
- Normal output — stdout + stderr concatenated

---

## Tool Implementation Details

### Shared Tools (9 mandatory)

All 9 tools are implemented in `mcp_servers/shared_tools/` and exposed through both `mcp_tools_mbpp.py` and `mcp_tools_swebench.py` at the repository root.

**Filesystem tools** (`shared_tools/filesystem/`):

| Tool | Signature | Description |
|------|-----------|-------------|
| `read_file` | `(filepath, start_line?, end_line?)` | Returns content with `N: line` format (like `cat -n`) |
| `edit_file` | `(filepath, old_str, new_str)` | Exact-string replacement; fails clearly if `old_str` not found |
| `list_files` | `(directory, pattern?)` | `find` with glob pattern, sorted, max 100 results |

**Search tools** (`shared_tools/search/`):

| Tool | Signature | Description |
|------|-----------|-------------|
| `search_code` | `(pattern, file_pattern?)` | grep with regex auto-detection |
| `search_function_or_class_definition_in_code` | `(name)` | Finds `def name(` and `class name` |
| `find_references` | `(name, filepath?, line?)` | All usages of a symbol |

**Execution tools** (`shared_tools/execution/`):

| Tool | Signature | Description |
|------|-----------|-------------|
| `run_tests` | `()` | Runs `SANDBOX_TEST_CODE` (MBPP) or `SANDBOX_EVAL_SCRIPT` (SWE-bench) |
| `get_patch` | `()` | `git -c core.fileMode=false diff HEAD` from `/testbed` |
| `run_command` | `(command, workdir)` | Shell command with stdout/stderr/exit_code |

### MCP Transports

Both root-level server files support:
- **stdio** (default): launched as a subprocess by the sandbox/agent
- **streamable HTTP**: `--transport http --port PORT` for external connections

### Dynamic Manual Generation

`sandbox/manual/generator.py` builds the LLM system prompt's tool section from discovered MCP schemas. It always appends `final_answer` documentation regardless of which server is connected.

---

## Benchmark Results

See [BENCHMARK_REPORT.md](BENCHMARK_REPORT.md) for full results.
