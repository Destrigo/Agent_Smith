import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class RunStats:
    task_id: str
    model_name: str
    provider: str
    success: bool
    iterations: int
    total_input_tokens: int
    total_output_tokens: int
    total_time_seconds: float
    total_requests: int
    avg_request_time_ms: float
    total_retries: int
    first_edit_step: Optional[int] = None
    first_pass_step: Optional[int] = None
    steps_after_pass: int = 0


def compute_stats(solution_path: Path, model_name: str, provider: str
                  ) -> RunStats:
    data = json.loads(solution_path.read_text())
    steps = data.get("steps", [])
    total_retries = sum(s.get("retries", 0) for s in steps)
    avg_time = (sum(s.get("request_time_ms", 0) for s in steps) / len(steps)
                if steps else 0.0)
    first_edit = None
    for s in steps:
        si = s.get("sandbox_input", "")
        if "edit_file(" in si:
            first_edit = s["step"]
            break
    first_pass = None
    for s in steps:
        so = s.get("sandbox_output", "")
        if "passed" in so.lower():
            first_pass = s["step"]
            break
    steps_after = 0
    if first_pass is not None:
        steps_after = data.get("iterations", 0) - first_pass
    return RunStats(
        task_id=data["task_id"], model_name=model_name, provider=provider,
        success=data["success"], iterations=data.get("iterations", 0),
        total_input_tokens=data.get("total_input_tokens", 0),
        total_output_tokens=data.get("total_output_tokens", 0),
        total_time_seconds=data.get("total_time_seconds", 0),
        total_requests=data.get("total_requests", 0),
        avg_request_time_ms=avg_time, total_retries=total_retries,
        first_edit_step=first_edit, first_pass_step=first_pass,
        steps_after_pass=steps_after)


@dataclass
class BenchmarkAccumulator:
    runs: list[RunStats] = field(default_factory=list)

    def add(self, stats: RunStats) -> None:
        self.runs.append(stats)

    def summary_by_model(self) -> dict[str, dict]:
        by_model: dict[str, list[RunStats]] = {}
        for r in self.runs:
            by_model.setdefault(r.model_name, []).append(r)
        summary = {}
        for model, runs in by_model.items():
            passed = sum(1 for r in runs if r.success)
            summary[model] = {
                "pass_rate": f"{passed}/{len(runs)}",
                "avg_iterations": round(sum(r.iterations
                                            for r in runs) / len(runs), 1),
                "avg_input_tokens": round(sum(r.total_input_tokens
                                              for r in runs) / len(runs)),
                "avg_output_tokens": round(sum(r.total_output_tokens
                                               for r in runs) / len(runs)),
                "avg_time_s": round(sum(r.total_time_seconds
                                        for r in runs) / len(runs), 1),
                "avg_request_ms": round(sum(r.avg_request_time_ms
                                            for r in runs) / len(runs), 1),
                "total_retries": sum(r.total_retries for r in runs)
            }
        return summary
