# Suppress uv's "VIRTUAL_ENV does not match project environment" warning
unexport VIRTUAL_ENV

.PHONY: install check-docker sandbox sandbox-mbpp sandbox-swebench \
        dump-mbpp dump-swebench \
        mbpp swebench run-mbpp run-swebench \
        exam-mbpp exam-swebench exam-sandbox exam-anticheat \
        bench-mbpp bench-swebench bench-all bench-extra \
        validate-mbpp validate-swebench \
        test test-eval test-moulinette test-all \
        setup-docker fix-docker-userns \
        lint lint-strict mcp-mbpp mcp-swebench clean help

# ── defaults ──────────────────────────────────────────────────────────────────
# Rate limits (free tier, requests/s):
#   mistral-large-latest  : 0.08 RPS  — default; strong reasoning, 7/8 SWE
#   mistral-medium-latest : ~0.83 RPS — higher throughput; rate limit may tighten
#   mistral-medium-2505   : ~0.83 RPS — pinned snapshot; use if medium-latest hits 429s
MODEL    ?= mistral-large-latest
# MODEL  ?= mistral-medium-latest
# MODEL  ?= mistral-medium-2505
URL      ?= https://api.mistral.ai/v1
PROVIDER ?= mistral
# Separate temp paths so run-mbpp and run-swebench don't overwrite each other
MBPP_TASK ?= /tmp/mbpp-task.json
MBPP_OUT  ?= /tmp/mbpp-solution.json
SWE_TASK  ?= /tmp/swe-task.json
SWE_OUT   ?= /tmp/swe-solution.json

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

install-uv:
	uv venv
# ── sandbox ───────────────────────────────────────────────────────────────────
sandbox:
	uv run sandbox

sandbox-mbpp:
	uv run sandbox config/sandbox_template.json --mcp-stdio "python mcp_tools_mbpp.py"

sandbox-swebench:
	uv run sandbox config/sandbox_template.json --mcp-stdio "python mcp_tools_swebench.py"

# ── dump tasks ────────────────────────────────────────────────────────────────
dump-mbpp:
	cd moulinette && uv run python -m moulinette dump --benchmark mbpp --output $(MBPP_TASK)

dump-swebench:
	cd moulinette && uv run python -m moulinette dump --benchmark swebench --output $(SWE_TASK)

# ── run agents ────────────────────────────────────────────────────────────────
mbpp: check-docker
	uv run agent-mbpp \
		--task-file $(MBPP_TASK) \
		--output $(MBPP_OUT) \
		--model-name "$(MODEL)" \
		--provider-url "$(URL)" \
		--provider $(PROVIDER)

swebench: check-docker
	uv run agent-swebench \
		--task-file $(SWE_TASK) \
		--output $(SWE_OUT) \
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

exam-anticheat:
	./eval_documents/exam_anticheat.sh \
		--student-path .

# ── full benchmark sweep ─────────────────────────────────────────────────────
# N=0 → all 257 tasks   N=20 → first 20   N=20 SHUFFLE=1 → 20 random
bench-mbpp: check-docker
	./scripts/bench_mbpp.sh $(if $(N),--n $(N),) $(if $(SHUFFLE),--shuffle,)

# N=0 → all 6 exam pool tasks   N=3 → first 3   N=3 SHUFFLE=1 → 3 random
bench-swebench: check-docker
	./scripts/bench_swebench.sh $(if $(N),--n $(N),) $(if $(SHUFFLE),--shuffle,)

# Run all 11 models sequentially: MBPP (257 tasks) + SWE-bench (6 tasks)
# Options: make bench-all MBPP_ONLY=1 / SWE_ONLY=1 / N=20 (quick test)
bench-all: check-docker
	./scripts/bench_all.sh \
		$(if $(MBPP_ONLY),--mbpp-only,) \
		$(if $(SWE_ONLY),--swe-only,) \
		$(if $(N),--n $(N),)

# Run extra SWE-bench tasks (beyond EXAM_POOL) across all models for the report.
# Options: make bench-extra JOBS=4  (parallel model runs, default 1)
bench-extra: check-docker
	./scripts/bench_extra_swe.sh $(if $(JOBS),--jobs $(JOBS),)

# ── one-shot: dump → run → validate ──────────────────────────────────────────
# Usage: make run-mbpp
#        make run-mbpp MODEL=deepseek/deepseek-r1:free
#        make run-swebench
run-mbpp: check-docker
	@[ -f .env ] || { echo "Copying .env.example → .env"; cp .env.example .env; }
	cd moulinette && uv run python -m moulinette dump --benchmark mbpp --output $(MBPP_TASK)
	uv run agent-mbpp \
		--task-file $(MBPP_TASK) \
		--output $(MBPP_OUT) \
		--model-name "$(MODEL)" \
		--provider-url "$(URL)" \
		--provider $(PROVIDER)
	cd moulinette && uv run python -m moulinette validate mbpp $(MBPP_TASK) $(MBPP_OUT)

run-swebench: check-docker
	@[ -f .env ] || { echo "Copying .env.example → .env"; cp .env.example .env; }
	cd moulinette && uv run python -m moulinette dump --benchmark swebench --output $(SWE_TASK)
	uv run agent-swebench \
		--task-file $(SWE_TASK) \
		--output $(SWE_OUT) \
		--model-name "$(MODEL)" \
		--provider-url "$(URL)" \
		--provider $(PROVIDER)
	cd moulinette && uv run python -m moulinette validate swebench $(SWE_TASK) $(SWE_OUT)

# ── validate ──────────────────────────────────────────────────────────────────
# Usage: make validate-mbpp / make validate-swebench
validate-mbpp:
	cd moulinette && uv run python -m moulinette validate mbpp $(MBPP_TASK) $(MBPP_OUT)

validate-swebench:
	cd moulinette && uv run python -m moulinette validate swebench $(SWE_TASK) $(SWE_OUT)

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
test-all: test test-moulinette

# Pull Docker images required by moulinette tests
# (python:3.11-slim for MBPP; SWE-bench images are fetched on demand)
setup-docker: check-docker
	docker pull python:3.11-slim

# Fix rootless-Docker lchown issue for SWE-bench tests (Linux VM only).
#
# Root cause: swebench's copy_to_container() creates a tar that embeds the
# host user's UID/GID.  The Docker rootless daemon then tries to lchown the
# extracted file to that UID, which is outside the sub-UID mapping range
# (see /etc/subuid) → EINVAL / 500 Server Error.
#
# Fix: extend the sub-UID/GID map to include the user's own UID/GID, then
# restart the rootless daemon so the new mapping is active.
# Requires sudo — run once per Linux VM.  No-op on macOS (Docker Desktop
# handles namespacing internally).
fix-docker-userns:
	@if [ "$$(uname)" = "Darwin" ]; then \
		echo "macOS detected — Docker Desktop handles namespacing internally, nothing to do."; \
		exit 0; \
	fi; \
	USER=$$(id -un); UID_=$$(id -u); GID_=$$(id -g); \
	echo "Patching /etc/subuid and /etc/subgid for $$USER ($$UID_:$$GID_)..."; \
	sudo sh -c "grep -qF '$$USER:$$UID_:1' /etc/subuid || echo '$$USER:$$UID_:1' >> /etc/subuid"; \
	sudo sh -c "grep -qF '$$USER:$$GID_:1' /etc/subgid || echo '$$USER:$$GID_:1' >> /etc/subgid"; \
	echo "Restarting Docker daemon..."; \
	if systemctl --user is-active --quiet docker 2>/dev/null; then \
		systemctl --user restart docker && echo "Rootless Docker restarted."; \
	else \
		sudo systemctl restart docker && echo "System Docker restarted."; \
	fi; \
	echo "Done. SWE-bench eval tests should now pass."

lint:
	uv run flake8 .
	uv run mypy . \
		--warn-return-any \
		--warn-unused-ignores \
		--ignore-missing-imports \
		--disallow-untyped-defs \
		--check-untyped-defs \
		--explicit-package-bases \
		--exclude moulinette \
		--exclude eval_documents \
		--exclude tests \
		--exclude conftest

lint-strict:
	uv run flake8 .
	uv run mypy . --strict \
		--explicit-package-bases \
		--ignore-missing-imports \
		--disable-error-code=untyped-decorator \
		--exclude moulinette \
		--exclude eval_documents \
		--exclude tests \
		--exclude conftest

# ── mcp servers (standalone) ──────────────────────────────────────────────────
mcp-mbpp:
	uv run python mcp_tools_mbpp.py --transport http --port 8000

mcp-swebench:
	uv run python mcp_tools_swebench.py --transport http --port 8001

# ── clean ─────────────────────────────────────────────────────────────────────
clean:
	find . -type d \( -name __pycache__ -o -name .pytest_cache -o -name .mypy_cache \) \
		! -path "./.venv/*" ! -path "./moulinette/.venv/*" \
		| xargs -r rm -rf
	find . \( -name "*.pyc" -o -name "*.pyo" \) \
		! -path "./.venv/*" ! -path "./moulinette/.venv/*" \
		-delete
	find . -name ".DS_Store" -delete
	rm -rf .venv moulinette/.venv moulinette/__pycache__

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
	@echo "  dump-mbpp        dump an MBPP task  → MBPP_TASK=$(MBPP_TASK)"
	@echo "  dump-swebench    dump a SWE-bench task → SWE_TASK=$(SWE_TASK)"
	@echo "  mbpp             run MBPP agent     (MBPP_TASK= MBPP_OUT= MODEL= URL=)"
	@echo "  swebench         run SWE-bench agent (SWE_TASK= SWE_OUT= MODEL= URL=)"
	@echo "  validate-mbpp    validate MBPP solution with moulinette"
	@echo "  validate-swebench validate SWE-bench solution with moulinette"
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
	@echo "  exam-anticheat   run anti-cheat checks on student code"
	@echo "  lint             flake8 + mypy (excludes moulinette, eval_documents)"
	@echo "  lint-strict      flake8 + mypy --strict"
	@echo "  mcp-mbpp         start MBPP MCP server on port 8000"
	@echo "  mcp-swebench     start SWE-bench MCP server on port 8001"
	@echo "  clean            remove __pycache__, .pytest_cache, .mypy_cache, .pyc/.pyo"
	@echo ""
	@echo "  Override defaults:  make mbpp MODEL=deepseek/deepseek-r1:free MBPP_TASK=/tmp/t.json"
	@echo ""
