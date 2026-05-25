# Commands

## Setup

```bash
uv pip install -e .
```

Create `.env` at project root:

```
OPENROUTER_API_KEY=sk-or-...
```

---

## Sandbox

```bash
# bare REPL
make sandbox

# with MBPP tools
make sandbox-mbpp

# with SWE-bench tools
make sandbox-swebench
```

---

## MBPP

```bash
# 1. get a task
make dump-mbpp               # writes to /tmp/task.json

# 2. run the agent
make mbpp                    # reads /tmp/task.json, writes /tmp/solution.json

# 3. validate
make validate
```

Custom task/output/model:

```bash
make mbpp TASK=/tmp/my_task.json OUT=/tmp/my_out.json MODEL=deepseek/deepseek-r1:free
```

---

## SWE-bench

```bash
# 1. get a task (Docker must be running)
make dump-swebench

# 2. run the agent
make swebench

# 3. validate
make validate
```

---

## MCP servers (standalone)

```bash
make mcp-mbpp        # HTTP on port 8000
make mcp-swebench    # HTTP on port 8001
```

---

## Tests

```bash
# run all tests
make test

# single file
uv run pytest tests/test_sandbox.py -v

# single test
uv run pytest tests/test_sandbox.py::test_import_blocked -v

# syntax check every .py file
make lint
```

---

## Clean

```bash
make clean    # removes __pycache__ and .pyc files
```

---

## Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MODEL` | `qwen/qwen3-235b-a22b:free` | model identifier |
| `URL` | `https://openrouter.ai/api/v1` | provider API base URL |
| `PROVIDER` | `openrouter` | used for API key lookup (`OPENROUTER_API_KEY`) |
| `TASK` | `/tmp/task.json` | input task file |
| `OUT` | `/tmp/solution.json` | output solution file |
