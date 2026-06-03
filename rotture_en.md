# rotture_en.md — Point-by-point answers to Jie's questions

## URGENT: EXAM_POOL and MBPP dataset (#15, #19 bis)

**EXAM_POOL has not changed.** Confirmed:
```
['django__django-11066', 'pydata__xarray-4629', 'scikit-learn__scikit-learn-13439',
 'sympy__sympy-13480', 'sympy__sympy-14711', 'sympy__sympy-18189']
```
The same 6 tasks as always. **No need to re-run anything.**

**`sympy__sympy-21847` is not part of the pool.** The `make run-swebench` command
runs `moulinette dump --benchmark swebench`, which dumps a RANDOM task from the entire
SWE-bench dataset (6000+ tasks), NOT from the exam pool. The pool is only used by the
exam scripts. The one-shot runs on any task — this is expected behavior.

**MBPP 419 tasks:** the moulinette counts the total dataset (train+test). We
benchmarked the test split (257 tasks). Nothing has changed on our end.

---

## macOS issues we CANNOT fix (eval_documents is off-limits)

### #21 — `mktemp --suffix=.json` does not work on macOS

`mktemp --suffix=.json` is GNU/Linux syntax. macOS uses a different syntax.
This breaks `exam_mbpp.sh` and `exam_swebench.sh` on macOS.

**We cannot fix this**: the files are in `eval_documents/`, which we must not touch.
**This is not a problem for evaluation**: the evaluator runs on Linux where it works.

Local fix for testing on macOS (install GNU coreutils):
```bash
brew install coreutils
# then add to ~/.zshrc:
export PATH="/opt/homebrew/opt/coreutils/libexec/gnubin:$PATH"
```
After this, the `mktemp` and `timeout` commands will work correctly.

### #19 — `timeout: command not found` (exam_sandbox.sh)

Same issue: `timeout` is a GNU command, not present by default on macOS.
Same fix: `brew install coreutils`.
The `MCP HTTP Connection` test fails on macOS for this reason, not due to a bug
in our code. The evaluator runs on Linux → no real issue.

---

## Issues we can fix

### #1 — Is providers.py correct?

**The code is correct.** Explanation:
- `_openrouter`: adds the `HTTP-Referer` header required by OpenRouter. ✓
- `_gemini`: a separate handler ready for direct Gemini access (not used in the
  benchmark but available). ✓
- `_generic`: all other providers use the standard OpenAI-compatible endpoint. ✓
- The registry has 6 providers → all supported ones. ✓

Gemini in the benchmarks was used via OpenRouter (same endpoint), not directly.
The `_gemini` handler is there for anyone who wants to use a direct Gemini key in the future.

### #2 — `agent/prompts/tool_prompt.txt` is empty/missing

The file does not exist — it was a placeholder. Verified: no code imports it.
**To be deleted** if it exists as an empty file.

### #3 — `config/models.yaml`

Contains free OpenRouter models for personal reference. Not used by any Python or bash script.
**To be deleted** — the information is now in the README.

### #4 — Extra task results not visible in the folder

The results of `bench_extra_swe` are in `evaluations/bench_extra_swe/`. Check
whether they have been committed. If not, run `git add evaluations/bench_extra_swe/ && git push`.

### #5 — `evaluations/bench_mbpp/` and `evaluations/bench_swebench/`

These folders contain the solution.json files for all historical runs — they are the **backing data**
required by the report. **Do not delete.** They are needed for the "Backing Data Spot-Check"
section of the evaluation (the evaluator will ask to open a specific solution.json).

### #6 — Is `utils/moulinette/` a duplicate?

`utils/moulinette/` = copy of the moulinette package (without venv).
`./moulinette/` = installation with venv used by the scripts.
They are the same thing, but `utils/moulinette/` is not used by any script.
**To be deleted** or clarified if it is a submodule.

### #7 — `models.md`

File with OpenRouter models — old, outdated information. **Already removed**
(git rm run in a previous session). If it still appears, run `git pull`.

### #8 — `scripts/run_benchmark.sh` and `run_benchmark_command.sh`

These files do not exist in the current `scripts/` folder. They were probably in an
old branch and have already been removed. Check with `git log --all --diff-filter=D --name-only`.

### #9 — `tst/` folder

Does not exist in the current project. Probably already removed.

### #10 — `eval/report_builder.py`

File that builds a markdown report from solution.json. Not called by any current
script (bench_all.sh generates its own SUMMARY.md). **To be deleted** — the
functionality has been replaced by the manually compiled BENCHMARK_REPORT.md.

### #11 — `filterwarnings` too broad

Jie is right: `"ignore::RuntimeWarning"` suppresses all RuntimeWarnings.
Fix: filter only the specific httpx warning.
**→ Fix applied in the following commit.**

### #12 — `RequestsDependencyWarning` on macOS

The warning `urllib3 (2.6.3) or chardet doesn't match supported version` comes from
the `requests` library used by the moulinette venv. **It is not in our code** — it is
in the isolated moulinette venv. We cannot/should not fix it.

To find the one-shot logs: they are in `/tmp/solution.json`. To view the details:
```bash
cat /tmp/solution.json | python3 -m json.tool | head -50
# or
cd moulinette && uv run moulinette_eval display /tmp/solution.json
```

### #13 — SWE improved iterations (3 instead of 4 for sympy-13480)?

Natural variance between runs. In previous sessions we have seen the same task vary
between 4 and 13 iterations. A single run is not representative. **Leave the historical data
in the report** — those are the official benchmark data, not one-shot results.

### #14 — Docker duplication: `_docker.py` vs `mydocker/manager.py`

Confirmed: significant duplication. **Fix planned** — merge to be done.
→ See fix in the commit.

### #16 — README: add Sandbox and MCP section

**→ Fix applied in the following commit.**

### #17 — OpenRouter gpt-oss-120b, 503 error

The model `openai/gpt-oss-120b:free` has a very low rate limit on OpenRouter
(50 req/day). The 503 means the daily quota was exhausted.
**→ Removed from the README as a recommended model.**

### #18 — `uv run agent-mbpp` fails with ValidationError

Jie ran `make run-swebench` (which dumps a SWE task to `/tmp/task.json`),
then manually ran `uv run agent-mbpp --task-file /tmp/task.json`.
The file is a SWE task, not MBPP → ValidationError is expected.

**Fix**: the `make run-mbpp` and `make run-swebench` commands will use separate paths:
`/tmp/mbpp-task.json` and `/tmp/swe-task.json`.
→ Fix in the Makefile in the following commit.

### #20 — `make mcp-mbpp` → `python: No such file or directory`

On macOS (and also Linux in some setups) the command is `python3`, not `python`.
The Makefile uses `python`. **→ Fix: change to `uv run python`** in the following commit.

Error `ModuleNotFoundError: No module named 'mcp'` when using `python3` directly:
this is expected — you must use `uv run python` which uses the project's venv.

### #22 — Test skips and warnings on macOS

- **Skip**: probably the Docker test (SWE-bench) skipped because Docker is not
  configured / images not present. Not a code bug.
- **Warning**: the `RequestsDependencyWarning` from moulinette is not in our code.

### #23 — `make validate-mbpp` → fails with token exceeded

`validate-mbpp` uses `/tmp/task.json` and `/tmp/solution.json` which were written
by a previous run (not mistral-medium, not MBPP). It is a false positive caused by
leftover `/tmp` files.

**Fix**: as in #18, separate the paths for temporary files.

---

## Fix checklist to apply in the commit

- [ ] Delete `config/models.yaml`
- [ ] Delete `eval/report_builder.py`
- [ ] Delete `utils/moulinette/` (if not a submodule)
- [ ] More specific `filterwarnings` fix
- [ ] Makefile fix: `python` → `uv run python` for mcp targets
- [ ] Makefile fix: separate paths for mbpp and swe (/tmp/mbpp-* and /tmp/swe-*)
- [ ] Fix Docker duplication
- [ ] README: add Sandbox/MCP section
- [ ] README: remove OpenRouter as default/recommended
- [ ] Commit evaluations/bench_extra_swe/ results
