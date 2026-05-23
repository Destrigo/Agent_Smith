# Agent Smith — Developer Guide

> How to run, connect, and build on top of the existing components.

---

## Table of Contents

1. [Setup](#setup)
2. [Running the Sandbox](#running-the-sandbox)
3. [Running the MCP Servers](#running-the-mcp-servers)
4. [Sandbox + MCP: Full Flow](#sandbox--mcp-full-flow)
5. [Using the Sandbox Programmatically](#using-the-sandbox-programmatically)
6. [Using MCPClient Programmatically](#using-mcpclient-programmatically)
7. [Generating the LLM Manual](#generating-the-llm-manual)
8. [Config Files](#config-files)
9. [Data Models](#data-models)
10. [What You Need to Build](#what-you-need-to-build)

---

## Setup

```bash
# Install dependencies (requires Python ≥ 3.11)
uv sync

# Or with pip
pip install -e .
```

After installation, three CLI commands are available:

| Command | Entry point |
|---|---|
| `uv run sandbox` | `sandbox/cli.py:main` |
| `uv run mcp-mbpp` | `mcp_servers/mcp_tools_mbpp.py:main` |
| `uv run mcp-swebench` | `mcp_servers/mcp_tools_swebench.py:main` |

---

## Running the Sandbox

The sandbox is an interactive Python REPL that executes code in an isolated namespace with security restrictions.

### Interactive REPL (default config)

```bash
uv run sandbox
```

Starts a REPL with the default `SandboxConfig` (standard library allowlist, `/testbed` and `/tmp/agent` as allowed directories, 30s timeout).

### With a custom config file

```bash
uv run sandbox config/sandbox_template.json
uv run sandbox config/sandbox_template_swebench.json
```

The JSON file is loaded into `SandboxConfig`. See [Config Files](#config-files) for the schema.

### With an MCP server (stdio)

The sandbox launches the MCP server as a subprocess and connects via stdin/stdout:

```bash
uv run sandbox config/sandbox_template.json --mcp-stdio "python mcp_servers/mcp_tools_mbpp.py"
uv run sandbox config/sandbox_template_swebench.json --mcp-stdio "python mcp_servers/mcp_tools_swebench.py"
```

After connecting, all MCP tools are available as Python callables in the sandbox REPL:

```python
>>> result = run_tests()
>>> files = list_files("/testbed", "*.py")
>>> patch = get_patch()
>>> final_answer(patch)
```

### With an MCP server (HTTP)

Start the MCP server first (see below), then connect the sandbox to it:

```bash
uv run sandbox config/sandbox_template.json --mcp-server http://localhost:8000
```

### REPL usage

Once the sandbox is running, enter Python code. A blank line triggers execution:

```
[sandbox] Ready.  Enter Python code (blank line to execute, Ctrl-D to quit).

>>> x = 42
>>> print(x * 2)
...               ← blank line to execute
84

>>> final_answer("my solution")
...
[final_answer] my solution
```

Calling `final_answer()` terminates the REPL and prints the final answer.

---

## Running the MCP Servers

The MCP servers expose tools to the sandbox (or to any MCP client). They must be running before the sandbox connects via HTTP, or they are launched automatically when using `--mcp-stdio`.

### MBPP MCP server

```bash
# stdio mode (launched by the sandbox automatically)
uv run mcp-mbpp

# HTTP mode (start manually, then connect the sandbox via --mcp-server)
uv run mcp-mbpp --transport http --host 0.0.0.0 --port 8000
```

### SWE-bench MCP server

```bash
# stdio mode
uv run mcp-swebench

# HTTP mode
uv run mcp-swebench --transport http --host 0.0.0.0 --port 8001
```

### Tools available on both servers

| Tool | Signature | Description |
|---|---|---|
| `read_file` | `(filepath, start_line, end_line)` | Read lines N–M from a file, `cat -n` format |
| `edit_file` | `(filepath, old_str, new_str)` | Replace first occurrence of `old_str` in file |
| `list_files` | `(directory, pattern)` | List files matching a glob pattern recursively |
| `search_code` | `(pattern, file_pattern?)` | Grep-like search across `/testbed` |
| `search_function_or_class_definition_in_code` | `(name)` | Find `def`/`class` definitions by name |
| `find_references` | `(name, filepath?, line?)` | Find all usages of a symbol |
| `run_tests` | `()` | Run the test suite (reads env vars, see below) |
| `run_command` | `(command, workdir)` | Execute a shell command in a directory |
| `get_patch` | `()` | Return `git diff` of `/testbed` |

#### `run_tests()` environment variables

`run_tests` reads the task context from environment variables set by the orchestrator:

```bash
# MBPP mode: run Python test assertions
export SANDBOX_TEST_CODE="assert my_func(1) == 2; assert my_func(3) == 4"

# SWE-bench mode: run an eval script
export SANDBOX_EVAL_SCRIPT="/testbed/eval.sh"
```

Exactly one must be set before calling `run_tests()`.

---

## Sandbox + MCP: Full Flow

The recommended way to run a complete agent session:

**Terminal 1 — Start the MCP server (HTTP mode):**

```bash
export SANDBOX_TEST_CODE="assert solution(1) == 1"
uv run mcp-mbpp --transport http --port 8000
```

**Terminal 2 — Start the sandbox connected to it:**

```bash
uv run sandbox config/sandbox_template.json --mcp-server http://localhost:8000
```

**Or as a single command (stdio, no separate terminal needed):**

```bash
export SANDBOX_TEST_CODE="assert solution(1) == 1"
uv run sandbox config/sandbox_template.json --mcp-stdio "python mcp_servers/mcp_tools_mbpp.py"
```

---

## Using the Sandbox Programmatically

Import `Sandbox` and `SandboxConfig` directly in your Python code (e.g. inside the agent loop you are building):

```python
from models.sandbox_model import SandboxConfig
from sandbox.core.sandbox import Sandbox

# Load config from file
import json
with open("config/sandbox_template.json") as f:
    config = SandboxConfig(**json.load(f))

# Or use defaults
config = SandboxConfig()

sandbox = Sandbox(config)
```

### Execute code

```python
result = sandbox.execute("""
x = [1, 2, 3]
print(sum(x))
""")

print(result["stdout"])       # "6\n"
print(result["stderr"])       # ""
print(result["error"])        # None
print(result["success"])      # True
print(result["final_answer"]) # None
```

### Detect final_answer

```python
result = sandbox.execute('final_answer("def solution(n): return n")')
if result["final_answer"] is not None:
    # task complete — collect the solution
    solution_code = result["final_answer"]
```

### Detect timeout

```python
result = sandbox.execute("while True: pass")
if result["error"] and "ExecutionTimeout" in result["error"]:
    # the code ran over max_execution_time_seconds
    partial_output = result["stdout"]
```

### Inject MCP tools manually

```python
from mcp_servers.mcp_client import MCPClient

client = MCPClient()
client.connect_stdio("python", ["mcp_servers/mcp_tools_swebench.py"])

tools = client.make_tool_wrappers()  # dict of {name: callable}
sandbox.register_mcp_tools(tools)

# Now the sandbox code can call run_tests(), get_patch(), etc.
result = sandbox.execute("result = run_tests()\nprint(result)")
```

### Namespace persistence

The sandbox namespace persists across multiple `execute()` calls on the same instance:

```python
sandbox.execute("x = 10")
sandbox.execute("y = x * 2")
result = sandbox.execute("print(y)")
# result["stdout"] == "20\n"
```

---

## Using MCPClient Programmatically

```python
from mcp_servers.mcp_client import MCPClient

client = MCPClient()

# Option A: connect via stdio (launches a subprocess)
client.connect_stdio("python", ["mcp_servers/mcp_tools_swebench.py"])

# Option B: connect via HTTP (server must already be running)
client.connect_http("http://localhost:8001")

# Inspect available tools
schemas = client.discover_tools()
for name, schema in schemas.items():
    print(name, "—", schema["description"])

# Call a tool directly
files = client.call_tool("list_files", directory="/testbed", pattern="*.py")

# Get callable wrappers (for injection into the sandbox)
wrappers = client.make_tool_wrappers()
patch = wrappers["get_patch"]()

# Always close when done
client.close()
```

---

## Generating the LLM Manual

The manual generator builds a human-readable description of all available tools, ready to be embedded in the LLM system prompt.

```python
from mcp_servers.mcp_client import MCPClient
from sandbox.manual.generator import generate_manual_from_client, generate_manual_from_schemas

# From a live MCP client
client = MCPClient()
client.connect_stdio("python", ["mcp_servers/mcp_tools_mbpp.py"])
manual = generate_manual_from_client(client)
print(manual)

# From a hardcoded schema dict (useful for tests)
manual = generate_manual_from_schemas({
    "run_tests": {
        "description": "Execute the test suite.",
        "inputSchema": {}
    }
})
```

**Output format:**

```
=== SANDBOX MANUAL ===

The following tools are available as Python callables in the sandbox.
Call them like regular functions — they communicate with the MCP server.

Tool: run_tests
Signature: run_tests()
Description: Execute the test suite...

Tool: final_answer
Signature: final_answer(answer: str) -> None
Description: Signal task completion. ...

=== END OF MANUAL ===
```

Embed this string in the system prompt before your first LLM call so the model knows exactly which functions it can invoke.

---

## Config Files

### `config/sandbox_template.json` (MBPP)

```json
{
  "authorized_imports": ["math", "math.*", "collections", "collections.*", ...],
  "allowed_directories": ["/testbed", "/tmp/agent"],
  "max_execution_time_seconds": 30,
  "max_memory_mb": 512
}
```

### `config/sandbox_template_swebench.json` (SWE-bench)

Same as above but with `max_execution_time_seconds: 60` and `pathlib` added to `authorized_imports`.

### `SandboxConfig` fields

| Field | Type | Description |
|---|---|---|
| `authorized_imports` | `List[str]` | Allowlist of importable modules. Wildcards supported (`math.*`) |
| `allowed_directories` | `List[str]` | Directories accessible via `open()` inside sandbox code |
| `max_execution_time_seconds` | `int` | Code execution timeout (thread join timeout) |
| `max_memory_mb` | `int` | Memory limit (not yet enforced — implement via resource limits) |

### What the security layer blocks

- **Imports**: any module not in `authorized_imports` raises `ImportError`. Modules in `_BLOCKED_MODULES` (os, sys, socket, subprocess, threading, asyncio, pickle, …) are always blocked even if listed in the allowlist.
- **File access**: `open()` calls with paths outside `allowed_directories` raise `PermissionError`.
- **Builtins**: `eval`, `exec`, `compile`, `__import__`, `input`, `breakpoint` are removed from the namespace.
- **Timeout**: code running longer than `max_execution_time_seconds` is abandoned (thread left to die); the result is returned with `error="ExecutionTimeout"`.

---

## Data Models

All models are in [models/](models/) and use Pydantic v2.

### Task inputs

```python
from models.mbpp import MBPPTaskInput
from models.swebench import SWEBenchTaskInput

task = MBPPTaskInput(
    task_id=1,
    task_definition="Write a function that returns the sum of two numbers.",
    function_definition="def add(a, b):",
    test_imports=[],
    test_list=["assert add(1, 2) == 3", "assert add(0, 0) == 0"],
)

task = SWEBenchTaskInput(
    instance_id="django__django-12345",
    problem_statement="Fix the bug in...",
    docker_image="swebench/django:latest",
    eval_script="/testbed/run_eval.sh",
    repo="django/django",
)
```

### Recording step metrics

```python
from models.agent_state import StepMetrics

step = StepMetrics(
    step=1,
    input_tokens=512,
    output_tokens=128,
    request_time_ms=340.5,
    api_url="https://api.anthropic.com",
    model_name="claude-sonnet-4-6",
    llm_output="```python\ndef add(a, b): return a + b\n```",
    sandbox_input="def add(a, b): return a + b",
    sandbox_output="stdout: \nerror: None",
    retries=0,
)
```

### Building the final output

```python
from models.solution import SolutionOutput

output = SolutionOutput(
    task_id="mbpp_1",
    benchmark="mbpp",
    success=True,
    solution="def add(a, b): return a + b",
    system_prompt="You are a coding assistant...",
    iterations=3,
    total_requests=3,
    total_input_tokens=1536,
    total_output_tokens=384,
    total_time_seconds=5.2,
    steps=[step],
)

print(output.model_dump_json(indent=2))
```

---

## What You Need to Build

The following modules exist as empty stubs. This is where the agent lives.

### Agent loop (`agent/core/agent_loop.py`)

The core loop that drives the agent. It should:

1. Receive a task (`MBPPTaskInput` or `SWEBenchTaskInput`)
2. Build the system prompt (include the sandbox manual from `generate_manual_from_client`)
3. Call the LLM with the task + conversation history
4. Extract the Python code block from the LLM response
5. Execute it with `sandbox.execute(code)`
6. Append `(llm_output, sandbox_result)` to the conversation history
7. Repeat until `sandbox_result["final_answer"]` is set or max iterations reached
8. Return a `SolutionOutput`

### LLM client (`agent/llm/`)

Needs to wrap an LLM API (Anthropic SDK is already a dependency). The `agent/llm/` directory has stubs for:
- `base.py` — abstract base class for LLM providers
- `manager.py` — manages a pool of providers
- `dispatcher.py` — selects a provider per request
- `router.py` — routing logic
- `retry_policy.py` — retry on rate limits / errors
- `providers/` — one file per provider (Anthropic, Gemini, Groq, etc.)

### Eval runner (`eval/`)

- `task_loader.py` — loads MBPP / SWE-bench datasets
- `runner.py` — runs the agent on a set of tasks in parallel
- `score.py` — computes pass@k and other metrics
- `report_builder.py` — generates `BENCHMARK_REPORT.md`

### Docker manager (`docker/`)

Required for SWE-bench. The MCP server tools operate on `/testbed` inside a Docker container. `docker/manager.py` should start/stop containers and mount the right image per task.

### Prompts (`agent/prompts/`)

The system prompt and task-specific prompt templates are empty. The system prompt must include the sandbox manual. See `sandbox/manual/generator.py` for how to generate it.
