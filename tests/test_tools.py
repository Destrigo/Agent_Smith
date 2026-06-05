"""
Tests for mcp_servers/shared_tools/**

Covers: filesystem tools (read_file, edit_file, list_files),
execution tools (run_command, run_tests, get_patch),
and search tools (search_code, find_definition, find_references).

All tools that operate on /testbed are exercised against a real temporary
directory by setting the TESTBED_PATH env var (supported by _testbed.py).
No os.walk or subprocess mocking — if something breaks, you see a real failure.
"""

import os
import subprocess
from pathlib import Path

# conftest.py adds mcp_servers/ to sys.path so these imports resolve.
from shared_tools.execution.get_patch import get_patch
from shared_tools.execution.run_command import run_command
from shared_tools.execution.run_tests import run_tests
from shared_tools.filesystem.edit_file import edit_file
from shared_tools.filesystem.list_files import list_files
from shared_tools.filesystem.read_file import read_file
from shared_tools.search.find_definition import (
    search_function_or_class_definition_in_code,
)
from shared_tools.search.find_references import find_references
from shared_tools.search.search_code import search_code


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write(path: Path, content: str) -> Path:
    """Write *content* to *path* and return *path*."""
    path.write_text(content, encoding="utf-8")
    return path


def _git_init(repo: Path) -> None:
    """Initialise a git repo in *repo* with a throwaway identity."""
    env = {**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "HOME": str(repo)}
    for cmd in [
        ["git", "init"],
        ["git", "config", "user.email", "test@example.com"],
        ["git", "config", "user.name", "Test"],
    ]:
        subprocess.run(cmd, cwd=repo, env=env, check=True,
                       capture_output=True)


def _git_commit_all(repo: Path, msg: str = "init") -> None:
    """Stage every file and create a commit."""
    env = {**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "HOME": str(repo)}
    subprocess.run(["git", "add", "."], cwd=repo, env=env, check=True,
                   capture_output=True)
    subprocess.run(["git", "commit", "-m", msg], cwd=repo, env=env,
                   check=True, capture_output=True)


# ---------------------------------------------------------------------------
# read_file
# ---------------------------------------------------------------------------

class TestReadFile:
    def test_reads_all_lines(self, tmp_path):
        f = _write(tmp_path / "a.txt", "line1\nline2\nline3\n")
        result = read_file(str(f), start_line=1, end_line=3)
        assert "1: line1" in result
        assert "2: line2" in result
        assert "3: line3" in result

    def test_reads_partial_range(self, tmp_path):
        f = _write(tmp_path / "a.txt", "alpha\nbeta\ngamma\n")
        result = read_file(str(f), start_line=2, end_line=2)
        assert "2: beta" in result
        assert "alpha" not in result
        assert "gamma" not in result

    def test_start_line_clamped_to_1(self, tmp_path):
        f = _write(tmp_path / "a.txt", "only\n")
        result = read_file(str(f), start_line=0, end_line=1)
        assert "1: only" in result

    def test_end_line_clamped_to_file_length(self, tmp_path):
        f = _write(tmp_path / "a.txt", "a\nb\n")
        result = read_file(str(f), start_line=1, end_line=999)
        assert "1: a" in result
        assert "2: b" in result

    def test_start_beyond_eof_returns_error(self, tmp_path):
        f = _write(tmp_path / "a.txt", "one line\n")
        result = read_file(str(f), start_line=10, end_line=20)
        assert "ERROR" in result
        assert "start_line" in result

    def test_file_not_found(self, tmp_path):
        result = read_file(str(tmp_path / "missing.txt"), start_line=1, end_line=5)
        assert "ERROR" in result
        assert "not found" in result

    def test_line_numbers_are_prefixed(self, tmp_path):
        f = _write(tmp_path / "a.txt", "x\ny\n")
        result = read_file(str(f), start_line=1, end_line=2)
        lines = result.splitlines()
        assert lines[0].startswith("1: ")
        assert lines[1].startswith("2: ")


# ---------------------------------------------------------------------------
# edit_file
# ---------------------------------------------------------------------------

class TestEditFile:
    def test_replaces_first_occurrence(self, tmp_path):
        f = _write(tmp_path / "code.py", "foo = 1\nfoo = 2\n")
        result = edit_file(str(f), old_str="foo = 1", new_str="bar = 1")
        assert result.startswith("OK")
        content = f.read_text()
        assert "bar = 1" in content
        assert "foo = 2" in content  # second occurrence untouched

    def test_only_first_occurrence_replaced(self, tmp_path):
        f = _write(tmp_path / "dup.txt", "abc\nabc\nabc\n")
        edit_file(str(f), old_str="abc", new_str="xyz")
        lines = f.read_text().splitlines()
        assert lines[0] == "xyz"
        assert lines[1] == "abc"
        assert lines[2] == "abc"

    def test_string_not_found_returns_error(self, tmp_path):
        f = _write(tmp_path / "f.txt", "hello world\n")
        result = edit_file(str(f), old_str="nonexistent", new_str="x")
        assert "ERROR" in result
        assert "not found" in result

    def test_empty_replacement(self, tmp_path):
        f = _write(tmp_path / "f.txt", "remove_me = True\n")
        result = edit_file(str(f), old_str="remove_me = True\n", new_str="")
        assert result.startswith("OK")
        assert f.read_text() == ""

    def test_multiline_replacement(self, tmp_path):
        f = _write(tmp_path / "f.py", "def old():\n    pass\n")
        result = edit_file(
            str(f),
            old_str="def old():\n    pass\n",
            new_str="def new():\n    return 42\n",
        )
        assert result.startswith("OK")
        assert "def new" in f.read_text()


# ---------------------------------------------------------------------------
# list_files
# ---------------------------------------------------------------------------

class TestListFiles:
    def test_lists_all_files(self, tmp_path):
        (tmp_path / "a.py").write_text("")
        (tmp_path / "b.py").write_text("")
        result = list_files(str(tmp_path), pattern="*")
        assert any("a.py" in p for p in result)
        assert any("b.py" in p for p in result)

    def test_glob_pattern_filters(self, tmp_path):
        (tmp_path / "main.py").write_text("")
        (tmp_path / "readme.md").write_text("")
        result = list_files(str(tmp_path), pattern="*.py")
        assert any("main.py" in p for p in result)
        assert all(not p.endswith(".md") for p in result)

    def test_nonexistent_directory_returns_empty(self, tmp_path):
        result = list_files(str(tmp_path / "ghost"), pattern="*")
        assert result == []

    def test_recurses_into_subdirectories(self, tmp_path):
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "deep.txt").write_text("")
        result = list_files(str(tmp_path), pattern="*.txt")
        assert any("deep.txt" in p for p in result)

    def test_empty_directory_returns_empty(self, tmp_path):
        result = list_files(str(tmp_path), pattern="*")
        assert result == []


# ---------------------------------------------------------------------------
# run_command
# ---------------------------------------------------------------------------

class TestRunCommand:
    def test_successful_command(self, tmp_path):
        result = run_command("echo hello", workdir=str(tmp_path))
        assert result["exit_code"] == 0
        assert "hello" in result["stdout"]

    def test_nonzero_exit_code(self, tmp_path):
        result = run_command("exit 42", workdir=str(tmp_path))
        assert result["exit_code"] == 42

    def test_stderr_captured(self, tmp_path):
        result = run_command("echo err >&2", workdir=str(tmp_path))
        assert "err" in result["stderr"] or "err" in result["stdout"]

    def test_command_error_returns_dict(self, tmp_path):
        result = run_command("false", workdir=str(tmp_path))
        assert "stdout" in result
        assert "stderr" in result
        assert "exit_code" in result

    def test_invalid_workdir_captured(self):
        result = run_command("echo hi", workdir="/nonexistent_path_xyz")
        assert "exit_code" in result


# ---------------------------------------------------------------------------
# run_tests
# ---------------------------------------------------------------------------

class TestRunTests:
    """Tests for run_tests().

    Three modes:
      • Inline (code= + test_list=): no subprocess, pure Python exec.
      • Env SANDBOX_TEST_CODE: runs `python -c <code>` for real.
      • Env SANDBOX_EVAL_SCRIPT: runs `bash <script>` for real.
    """

    # -- inline mode ----------------------------------------------------------

    def test_inline_mode_passing(self):
        result = run_tests(
            code="def add(a, b): return a + b",
            test_list=["assert add(1, 2) == 3", "assert add(0, 0) == 0"],
        )
        assert result["success"] is True
        assert result["exit_code"] == 0

    def test_inline_mode_failing_assertion(self):
        result = run_tests(
            code="def add(a, b): return 0",          # wrong impl
            test_list=["assert add(1, 2) == 3"],
        )
        assert result["success"] is False
        assert result["exit_code"] == 1
        assert "ASSERTION" in result["output"].upper()

    def test_inline_mode_syntax_error(self):
        result = run_tests(
            code="def bad(: pass",                    # invalid syntax
            test_list=["assert bad()"],
        )
        assert result["success"] is False
        assert result["exit_code"] == 1

    # -- SANDBOX_TEST_CODE mode (real subprocess) ----------------------------

    def test_sandbox_test_code_passes(self, monkeypatch, tmp_path):
        monkeypatch.setenv("SANDBOX_TEST_CODE", "assert 1 + 1 == 2")
        monkeypatch.delenv("SANDBOX_EVAL_SCRIPT", raising=False)
        monkeypatch.setenv("TESTBED_PATH", str(tmp_path))

        result = run_tests()
        assert result["exit_code"] == 0

    def test_sandbox_test_code_failing(self, monkeypatch, tmp_path):
        monkeypatch.setenv("SANDBOX_TEST_CODE", "assert False")
        monkeypatch.delenv("SANDBOX_EVAL_SCRIPT", raising=False)
        monkeypatch.setenv("TESTBED_PATH", str(tmp_path))

        result = run_tests()
        assert result["exit_code"] == 1
        assert "AssertionError" in result["stderr"]

    # -- SANDBOX_EVAL_SCRIPT mode (real bash script) -------------------------

    def test_eval_script_passing(self, monkeypatch, tmp_path):
        script = tmp_path / "eval.sh"
        script.write_text("#!/bin/bash\necho PASSED\nexit 0\n")
        script.chmod(0o755)
        monkeypatch.setenv("SANDBOX_EVAL_SCRIPT", str(script))
        monkeypatch.delenv("SANDBOX_TEST_CODE", raising=False)
        monkeypatch.setenv("TESTBED_PATH", str(tmp_path))

        result = run_tests()
        assert result["exit_code"] == 0
        assert "PASSED" in result["stdout"]

    def test_eval_script_failing(self, monkeypatch, tmp_path):
        script = tmp_path / "eval.sh"
        script.write_text("#!/bin/bash\necho FAILED\nexit 1\n")
        script.chmod(0o755)
        monkeypatch.setenv("SANDBOX_EVAL_SCRIPT", str(script))
        monkeypatch.delenv("SANDBOX_TEST_CODE", raising=False)
        monkeypatch.setenv("TESTBED_PATH", str(tmp_path))

        result = run_tests()
        assert result["exit_code"] == 1
        assert "FAILED" in result["stdout"]

    # -- error cases ----------------------------------------------------------

    def test_neither_env_set_returns_error(self, monkeypatch):
        monkeypatch.delenv("SANDBOX_TEST_CODE", raising=False)
        monkeypatch.delenv("SANDBOX_EVAL_SCRIPT", raising=False)

        result = run_tests()
        assert result["exit_code"] == -1
        assert "ERROR" in result["stderr"]
        assert "SANDBOX_TEST_CODE" in result["stderr"]

    def test_result_keys_always_present(self, monkeypatch):
        monkeypatch.delenv("SANDBOX_TEST_CODE", raising=False)
        monkeypatch.delenv("SANDBOX_EVAL_SCRIPT", raising=False)

        result = run_tests()
        assert {"stdout", "stderr", "exit_code"} <= result.keys()


# ---------------------------------------------------------------------------
# get_patch
# ---------------------------------------------------------------------------

class TestGetPatch:
    """Tests for get_patch() against a real git repository.

    A temporary git repo is initialised in tmp_path; TESTBED_PATH is set so
    the tool operates on that directory instead of /testbed.
    """

    def test_returns_diff_when_file_modified(self, tmp_path, monkeypatch):
        monkeypatch.setenv("TESTBED_PATH", str(tmp_path))
        _git_init(tmp_path)
        _write(tmp_path / "file.py", "original\n")
        _git_commit_all(tmp_path)

        _write(tmp_path / "file.py", "modified\n")
        result = get_patch()

        assert "diff --git" in result
        assert "file.py" in result

    def test_returns_empty_when_no_changes(self, tmp_path, monkeypatch):
        monkeypatch.setenv("TESTBED_PATH", str(tmp_path))
        _git_init(tmp_path)
        _write(tmp_path / "file.py", "stable\n")
        _git_commit_all(tmp_path)

        result = get_patch()
        assert result == ""

    def test_respects_testbed_path(self, tmp_path, monkeypatch):
        """TESTBED_PATH controls which repo get_patch() reads from."""
        monkeypatch.setenv("TESTBED_PATH", str(tmp_path))
        _git_init(tmp_path)
        _write(tmp_path / "hello.py", "print('hello')\n")
        _git_commit_all(tmp_path)

        _write(tmp_path / "hello.py", "print('world')\n")
        result = get_patch()
        # The diff must mention the file in our tmp repo, not /testbed.
        assert "hello.py" in result


# ---------------------------------------------------------------------------
# search_code
# ---------------------------------------------------------------------------

class TestSearchCode:
    """search_code walks TESTBED_PATH — no os.walk mock needed."""

    def test_finds_matching_lines(self, tmp_path, monkeypatch):
        monkeypatch.setenv("TESTBED_PATH", str(tmp_path))
        _write(tmp_path / "module.py", "x = 1\nresult = x + 1\n")
        _write(tmp_path / "other.py", "nothing_here = True\n")

        results = search_code("result", file_pattern="*.py")
        assert any("result" in r for r in results)

    def test_no_results_for_missing_pattern(self, tmp_path, monkeypatch):
        monkeypatch.setenv("TESTBED_PATH", str(tmp_path))
        _write(tmp_path / "empty.py", "nothing\n")

        results = search_code("COMPLETELY_ABSENT_XYZ123")
        assert results == []

    def test_file_pattern_filters_extensions(self, tmp_path, monkeypatch):
        monkeypatch.setenv("TESTBED_PATH", str(tmp_path))
        _write(tmp_path / "code.py", "target_string\n")
        _write(tmp_path / "notes.txt", "target_string\n")

        results = search_code("target_string", file_pattern="*.py")
        assert results  # at least one hit
        assert all(".py" in r for r in results)

    def test_returns_file_and_line_number(self, tmp_path, monkeypatch):
        monkeypatch.setenv("TESTBED_PATH", str(tmp_path))
        _write(tmp_path / "f.py", "# comment\nfind_me = 1\n")

        results = search_code("find_me")
        assert len(results) == 1
        assert ":2 " in results[0]


# ---------------------------------------------------------------------------
# search_function_or_class_definition_in_code (find_definition)
# ---------------------------------------------------------------------------

class TestFindDefinition:
    """find_definition walks TESTBED_PATH — no os.walk mock needed."""

    def test_finds_function_definition(self, tmp_path, monkeypatch):
        monkeypatch.setenv("TESTBED_PATH", str(tmp_path))
        _write(tmp_path / "funcs.py",
               "def my_func(x):\n    return x\n\nclass MyClass:\n    pass\n")

        results = search_function_or_class_definition_in_code("my_func")
        assert any("my_func" in r for r in results)

    def test_finds_class_definition(self, tmp_path, monkeypatch):
        monkeypatch.setenv("TESTBED_PATH", str(tmp_path))
        _write(tmp_path / "cls.py", "class Foo:\n    pass\n")

        results = search_function_or_class_definition_in_code("Foo")
        assert any("Foo" in r for r in results)

    def test_no_match_returns_empty(self, tmp_path, monkeypatch):
        monkeypatch.setenv("TESTBED_PATH", str(tmp_path))
        _write(tmp_path / "a.py", "x = 1\n")

        results = search_function_or_class_definition_in_code("ghost_fn")
        assert results == []

    def test_does_not_match_call_site(self, tmp_path, monkeypatch):
        """A call like `my_func(x)` must not be returned, only defs."""
        monkeypatch.setenv("TESTBED_PATH", str(tmp_path))
        _write(tmp_path / "caller.py", "my_func(1)\n")

        results = search_function_or_class_definition_in_code("my_func")
        assert results == []

    def test_only_searches_python_files(self, tmp_path, monkeypatch):
        monkeypatch.setenv("TESTBED_PATH", str(tmp_path))
        _write(tmp_path / "defs.txt", "def not_python():\n    pass\n")

        results = search_function_or_class_definition_in_code("not_python")
        assert results == []


# ---------------------------------------------------------------------------
# find_references
# ---------------------------------------------------------------------------

class TestFindReferences:
    """find_references walks TESTBED_PATH — no os.walk mock needed."""

    def test_finds_variable_usage(self, tmp_path, monkeypatch):
        monkeypatch.setenv("TESTBED_PATH", str(tmp_path))
        _write(tmp_path / "usage.py", "x = my_var + 1\ny = my_var * 2\n")

        results = find_references("my_var")
        assert len(results) == 2

    def test_word_boundary_no_partial_match(self, tmp_path, monkeypatch):
        monkeypatch.setenv("TESTBED_PATH", str(tmp_path))
        _write(tmp_path / "b.py", "my_variable = 1\nmy_var_extended = 2\n")

        results = find_references("my_variable")
        assert len(results) == 1
        assert "my_variable" in results[0]

    def test_no_references_returns_empty(self, tmp_path, monkeypatch):
        monkeypatch.setenv("TESTBED_PATH", str(tmp_path))
        _write(tmp_path / "c.py", "x = 1\n")

        results = find_references("nonexistent_symbol_xyz")
        assert results == []

    def test_result_format_includes_path_and_line(self, tmp_path, monkeypatch):
        monkeypatch.setenv("TESTBED_PATH", str(tmp_path))
        _write(tmp_path / "ref.py", "token = 1\n")

        results = find_references("token")
        assert len(results) == 1
        assert ":1 " in results[0]
