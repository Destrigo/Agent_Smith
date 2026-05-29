# Suppress uv's "VIRTUAL_ENV does not match project environment" warning
unexport VIRTUAL_ENV

.PHONY: install check-docker sandbox sandbox-mbpp sandbox-swebench \
        mbpp swebench run-mbpp run-swebench \
        exam-mbpp exam-swebench exam-sandbox \
        bench-mbpp bench-swebench \
        test test-eval test-moulinette test-all \
        setup-docker fix-docker-userns \
        lint clean help

# ── defaults ──────────────────────────────────────────────────────────────────
MODEL    ?= mistral-small-latest
URL      ?= https://api.mistral.ai/v1
PROVIDER ?= mistral
TASK     ?= /tmp/task.json
OUT      ?= /tmp/solution.json

# ── docker check ──────────────────────────────────────────────────────────────
# Verifies the Docker daemon is reachable before any target that needs it.
# Docker is required for BOTH MBPP (code execution) and SWE-bench (containers).
check-docker:
	@docker info > /dev/null 2>&1 || { \
		echo ""; \
		echo "ERROR: Docker daemon is not running."; \
		echo "  macOS / Windows : start Docker Desktop, then retry."; \
		echo "  Linux           : sudo systemctl start docker"; \
		echo "                    (or: systemctl --user start docker)"; \
		echo ""; \
		echo "After Docker is running, pull the base image once:"; \
		echo "  make setup-docker"; \
		echo ""; \
		exit 1; \
	}

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
mbpp: check-docker
	uv run agent-mbpp \
		--task-file $(TASK) \
		--output $(OUT) \
		--model-name "$(MODEL)" \
		--provider-url "$(URL)" \
		--provider $(PROVIDER)

swebench: check-docker
	uv run agent-swebench \
		--task-file $(TASK) \
		--output $(OUT) \
		--model-name "$(MODEL)" \
		--provider-url "$(URL)" \
		--provider $(PROVIDER)

# ── exam scripts (as used by the evaluator) ──────────────────────────────────
exam-mbpp: check-docker
	./eval_documents/exam_mbpp.sh \
		--student-path . \
		--moulinette-path ./moulinette \
		--env-file .env

exam-swebench: check-docker
	./eval_documents/exam_swebench.sh \
		--student-path . \
		--moulinette-path ./moulinette \
		--env-file .env

exam-sandbox: check-docker
	./eval_documents/exam_sandbox.sh \
		--student-path . \
		--moulinette-path ./moulinette \
		--env-file .env

# ── full benchmark sweep ─────────────────────────────────────────────────────
# N=0 → all 257 tasks   N=20 → first 20   N=20 SHUFFLE=1 → 20 random
bench-mbpp: check-docker
	./scripts/bench_mbpp.sh $(if $(N),--n $(N),) $(if $(SHUFFLE),--shuffle,)

# N=0 → all 6 exam pool tasks   N=3 → first 3   N=3 SHUFFLE=1 → 3 random
bench-swebench: check-docker
	./scripts/bench_swebench.sh $(if $(N),--n $(N),) $(if $(SHUFFLE),--shuffle,)

# ── one-shot: dump → run → validate ──────────────────────────────────────────
# Usage: make run-mbpp
#        make run-mbpp MODEL=deepseek/deepseek-r1:free
#        make run-swebench
run-mbpp: check-docker
	@[ -f .env ] || { echo "Copying .env.example → .env"; cp .env.example .env; }
	cd moulinette && uv run python -m moulinette dump --benchmark mbpp --output $(TASK)
	uv run agent-mbpp \
		--task-file $(TASK) \
		--output $(OUT) \
		--model-name "$(MODEL)" \
		--provider-url "$(URL)" \
		--provider $(PROVIDER)
	cd moulinette && uv run python -m moulinette validate mbpp $(TASK) $(OUT)

run-swebench: check-docker
	@[ -f .env ] || { echo "Copying .env.example → .env"; cp .env.example .env; }
	cd moulinette && uv run python -m moulinette dump --benchmark swebench --output $(TASK)
	uv run agent-swebench \
		--task-file $(TASK) \
		--output $(OUT) \
		--model-name "$(MODEL)" \
		--provider-url "$(URL)" \
		--provider $(PROVIDER)
	cd moulinette && uv run python -m moulinette validate swebench $(TASK) $(OUT)

# ── validate ──────────────────────────────────────────────────────────────────
# Usage: make validate-mbpp / make validate-swebench
validate-mbpp:
	cd moulinette && uv run python -m moulinette validate mbpp $(TASK) $(OUT)

validate-swebench:
	cd moulinette && uv run python -m moulinette validate swebench $(TASK) $(OUT)

# ── test / lint ───────────────────────────────────────────────────────────────

# Main project tests (includes eval_documents sandbox scripts)
test: install setup-docker
	uv run pytest tests/ -v

# eval_documents sandbox scripts only
test-eval: install setup-docker
	uv run pytest tests/test_sandbox_scripts.py -v

# Moulinette tests (uses moulinette's own venv)
test-moulinette: install setup-docker
	cd moulinette && uv run pytest tests/ -v

# Both suites in sequence
test-all: install setup-docker test test-moulinette

# Pull Docker images required by moulinette tests
# (python:3.11-slim for MBPP; SWE-bench images are fetched on demand)
setup-docker: check-docker
	docker pull python:3.11-slim

# Fix rootless-Docker lchown issue for SWE-bench tests.
#
# Root cause: swebench's copy_to_container() creates a tar that embeds the
# host user's UID/GID.  The Docker rootless daemon then tries to lchown the
# extracted file to that UID, which is outside the sub-UID mapping range
# (see /etc/subuid) → EINVAL / 500 Server Error.
#
# Fix: extend the sub-UID/GID map to include the user's own UID/GID, then
# restart the rootless daemon so the new mapping is active.
# Requires sudo — run once per machine.
fix-docker-userns:
	@USER=$$(id -un); UID_=$$(id -u); GID_=$$(id -g); \
	echo "Patching /etc/subuid and /etc/subgid for $$USER ($$UID_:$$GID_)..."; \
	sudo sh -c "grep -qF '$$USER:$$UID_:1' /etc/subuid || echo '$$USER:$$UID_:1' >> /etc/subuid"; \
	sudo sh -c "grep -qF '$$USER:$$GID_:1' /etc/subgid || echo '$$USER:$$GID_:1' >> /etc/subgid"; \
	systemctl --user restart docker; \
	echo "Done. SWE-bench eval tests should now pass."

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
	@echo "  run-mbpp         one-shot: dump → run MBPP agent → validate"
	@echo "  run-swebench     one-shot: dump → run SWE-bench agent → validate"
	@echo ""
	@echo "  dump-mbpp        dump an MBPP task  → TASK=$(TASK)"
	@echo "  dump-swebench    dump a SWE-bench task"
	@echo "  mbpp             run MBPP agent     (TASK= OUT= MODEL= URL=)"
	@echo "  swebench         run SWE-bench agent"
	@echo "  validate         validate solution with moulinette"
	@echo ""
	@echo "  bench-mbpp       run MBPP agent on all (or N) tasks and report score"
	@echo "  bench-swebench   run SWE-bench agent on all 6 exam pool tasks"
	@echo "                   (N=3 → first 3, SHUFFLE=1 → random order)"
	@echo ""
	@echo "  test             run main project tests (incl. eval_documents)"
	@echo "  test-eval        run eval_documents sandbox tests only"
	@echo "  test-moulinette  run moulinette tests (uses moulinette venv)"
	@echo "  test-all         run both test suites in sequence"
	@echo ""
	@echo "  setup-docker     pull Docker images needed by moulinette tests"
	@echo "                   (run once per machine: docker pull python:3.11-slim)"
	@echo "  fix-docker-userns fix rootless-Docker lchown error for SWE-bench tests"
	@echo "                   (requires sudo, run once per machine)"
	@echo ""
	@echo "  lint             syntax-check all .py files"
	@echo "  mcp-mbpp         start MBPP MCP server on port 8000"
	@echo "  mcp-swebench     start SWE-bench MCP server on port 8001"
	@echo "  clean            remove __pycache__ and .pyc files"
	@echo ""
	@echo "  Override defaults:  make mbpp MODEL=deepseek/deepseek-r1:free TASK=/tmp/t.json"
	@echo ""
