"""
Tests for eval/report_builder.py.
"""

import json
import pytest
from pathlib import Path
from eval.report_builder import _md_table, build_report


# ---------------------------------------------------------------------------
# _md_table
# ---------------------------------------------------------------------------

class TestMdTable:
    def test_basic_structure(self):
        result = _md_table(["A", "B"], [["x", "y"], ["foo", "bar"]])
        lines = result.splitlines()
        assert len(lines) == 4          # header, separator, 2 rows
        assert lines[0].startswith("|")
        assert set(lines[1].replace("|", "").replace("-", "").replace(" ", "")) == set()

    def test_column_widths_match_longest_value(self):
        result = _md_table(["Col"], [["short"], ["a_very_long_value"]])
        # every data row must be the same width as the header row
        lines = result.splitlines()
        widths = {len(l) for l in lines}
        assert len(widths) == 1, f"row widths differ: {widths}"

    def test_single_row(self):
        result = _md_table(["H"], [["v"]])
        assert "H" in result
        assert "v" in result

    def test_empty_rows(self):
        result = _md_table(["X", "Y"], [])
        lines = result.splitlines()
        assert len(lines) == 2          # only header + separator, no data rows


# ---------------------------------------------------------------------------
# build_report
# ---------------------------------------------------------------------------

def _make_solution(tmp_path: Path, task_id: str, success: bool,
                   model: str = "qwen/qwen3-8b:free",
                   iterations: int = 3) -> Path:
    """Write a minimal *_solution.json file that build_report can parse."""
    data = {
        "task_id": task_id,
        "benchmark": "mbpp",
        "success": success,
        "solution": "def f(): pass",
        "iterations": iterations,
        "total_requests": iterations,
        "total_input_tokens": iterations * 100,
        "total_output_tokens": iterations * 50,
        "total_time_seconds": iterations * 1.5,
        "steps": [
            {
                "step": i + 1,
                "model_name": model,
                "request_time_ms": 300.0,
                "retries": 0,
                "sandbox_input": "run_tests()" if i == 1 else "",
                "sandbox_output": "passed" if (success and i == 1) else "FAIL",
            }
            for i in range(iterations)
        ],
    }
    path = tmp_path / f"{task_id}_solution.json"
    path.write_text(json.dumps(data))
    return path


class TestBuildReport:
    def test_creates_output_file(self, tmp_path):
        _make_solution(tmp_path, "task_1", success=True)
        out = tmp_path / "report.md"
        build_report(tmp_path, out)
        assert out.exists()

    def test_report_has_required_sections(self, tmp_path):
        _make_solution(tmp_path, "task_1", success=True)
        out = tmp_path / "report.md"
        build_report(tmp_path, out)
        content = out.read_text()
        for section in ("# Benchmark Report", "## 1. Setup",
                        "## 2. Results Table", "## 3. Provider Reliability",
                        "## 4. Intermediary Metrics", "## 5. Ablation Study",
                        "## 6. Conclusions"):
            assert section in content, f"Missing section: {section!r}"

    def test_pass_shown_as_checkmark(self, tmp_path):
        _make_solution(tmp_path, "task_pass", success=True)
        out = tmp_path / "report.md"
        build_report(tmp_path, out)
        assert "✅" in out.read_text()

    def test_fail_shown_as_cross(self, tmp_path):
        _make_solution(tmp_path, "task_fail", success=False)
        out = tmp_path / "report.md"
        build_report(tmp_path, out)
        assert "❌" in out.read_text()

    def test_multiple_solutions_all_appear(self, tmp_path):
        for i in range(3):
            _make_solution(tmp_path, f"task_{i}", success=(i % 2 == 0))
        out = tmp_path / "report.md"
        build_report(tmp_path, out)
        content = out.read_text()
        for i in range(3):
            assert f"task_{i}" in content

    def test_empty_solutions_dir_produces_empty_table(self, tmp_path):
        out = tmp_path / "report.md"
        build_report(tmp_path, out)
        content = out.read_text()
        # report should still be written without crashing
        assert "# Benchmark Report" in content

    def test_malformed_json_is_skipped_gracefully(self, tmp_path):
        bad = tmp_path / "bad_solution.json"
        bad.write_text("{ not valid json")
        out = tmp_path / "report.md"
        build_report(tmp_path, out)   # must not raise
        assert out.exists()

    def test_summary_by_model_in_report(self, tmp_path):
        _make_solution(tmp_path, "t1", success=True,  model="modelA")
        _make_solution(tmp_path, "t2", success=False, model="modelA")
        out = tmp_path / "report.md"
        build_report(tmp_path, out)
        content = out.read_text()
        assert "modelA" in content
