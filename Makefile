.PHONY: install sandbox sandbox-mbpp sandbox-swebench \
        mbpp swebench test lint clean help

# ── defaults ──────────────────────────────────────────────────────────────────
MODEL    ?= qwen/qwen3-235b-a22b:free
URL      ?= https://openrouter.ai/api/v1
PROVIDER ?= openrouter
TASK     ?= /tmp/task.json
OUT      ?= /tmp/solution.json

# ── setup ─────────────────────────────────────────────────────────────────────
install:
	uv pip install -e .

# ── sandbox ───────────────────────────────────────────────────────────────────
sandbox:
	uv run sandbox

sandbox-mbpp:
	uv run sandbox config/sandbox_template.json --mcp-stdio "python mcp_tools_mbpp.py"

sandbox-swebench:
	uv run sandbox config/sandbox_template.json --mcp-stdio "python mcp_tools_swebench.py"

# ── dump tasks ────────────────────────────────────────────────────────────────
dump-mbpp:
	cd moulinette && uv run python -m moulinette dump --benchmark mbpp --output $(TASK)

dump-swebench:
	cd moulinette && uv run python -m moulinette dump --benchmark swebench --output $(TASK)

# ── run agents ────────────────────────────────────────────────────────────────
mbpp:
	uv run agent-mbpp \
		--task-file $(TASK) \
		--output $(OUT) \
		--model-name "$(MODEL)" \
		--provider-url "$(URL)" \
		--provider $(PROVIDER)

swebench:
	uv run agent-swebench \
		--task-file $(TASK) \
		--output $(OUT) \
		--model-name "$(MODEL)" \
		--provider-url "$(URL)" \
		--provider $(PROVIDER)

# ── validate ──────────────────────────────────────────────────────────────────
validate:
	cd moulinette && uv run python -m moulinette validate --solution $(OUT)

# ── test / lint ───────────────────────────────────────────────────────────────
test:
	uv run pytest tests/ -v

lint:
	uv run python -m py_compile $$(find . -name "*.py" \
		! -path "./.venv/*" ! -path "./moulinette/*") \
		&& echo "All files OK"

# ── mcp servers (standalone) ──────────────────────────────────────────────────
mcp-mbpp:
	python mcp_tools_mbpp.py --transport http --port 8000

mcp-swebench:
	python mcp_tools_swebench.py --transport http --port 8001

# ── clean ─────────────────────────────────────────────────────────────────────
clean:
	find . -type d -name __pycache__ ! -path "./.venv/*" ! -path "./moulinette/*" \
		| xargs rm -rf
	find . -name "*.pyc" ! -path "./.venv/*" | xargs rm -f

# ── help ──────────────────────────────────────────────────────────────────────
help:
	@echo ""
	@echo "  install          install project with uv"
	@echo ""
	@echo "  sandbox          interactive sandbox REPL"
	@echo "  sandbox-mbpp     sandbox with MBPP MCP tools"
	@echo "  sandbox-swebench sandbox with SWE-bench MCP tools"
	@echo ""
	@echo "  dump-mbpp        dump an MBPP task  → TASK=$(TASK)"
	@echo "  dump-swebench    dump a SWE-bench task"
	@echo "  mbpp             run MBPP agent     (TASK= OUT= MODEL= URL=)"
	@echo "  swebench         run SWE-bench agent"
	@echo "  validate         validate solution with moulinette"
	@echo ""
	@echo "  test             run pytest"
	@echo "  lint             syntax-check all .py files"
	@echo "  mcp-mbpp         start MBPP MCP server on port 8000"
	@echo "  mcp-swebench     start SWE-bench MCP server on port 8001"
	@echo "  clean            remove __pycache__ and .pyc files"
	@echo ""
	@echo "  Override defaults:  make mbpp MODEL=deepseek/deepseek-r1:free TASK=/tmp/t.json"
	@echo ""
