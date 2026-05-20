import argparse
import json
from pathlib import Path
from agent.metrics.tracker import compute_stats, BenchmarkAccumulator


def _md_table(headers: list[str], rows: list[list[str]]) -> str:
    col_w = [max(len(h), max((len(str(r[i])) for r in rows), default=0))
             for i, h in enumerate(headers)]

    def row_str(cells):
        return "| " + " | ".join(str(c).ljust(col_w[i])
                                 for i, c in enumerate(cells)) + " |"
    sep = "| " + " | ".join("-" * w for w in col_w) + " |"
    return "\n".join([row_str(headers), sep] + [row_str(r) for r in rows])


def build_report(solutions_dir: Path, output_path: Path) -> None:
    acc = BenchmarkAccumulator()
    all_rows = []
    for sol_file in sorted(solutions_dir.rglob("*_solution.json")):
        try:
            data = json.loads(sol_file.read_text())
        except Exception:
            continue
        model = data.get("steps", [{}])[0].get("model_name", "unknown") \
            if data.get("steps") else "unknown"
        provider = "openrouter"
        stats = compute_stats(sol_file, model, provider)
        acc.add(stats)
        all_rows.append([
            stats.task_id, stats.model_name[:30],
            "✅" if stats.success else "❌", str(stats.iterations),
            str(stats.total_input_tokens), str(stats.total_output_tokens),
            f"{stats.total_time_seconds:.1f}s",
            f"{stats.avg_request_time_ms:.0f}ms", str(stats.total_retries),
            str(stats.first_edit_step or "-"),
            str(stats.first_pass_step or "-"), str(stats.steps_after_pass)])
        lines = [
            "# Benchmark Report", "", "## 1. Setup", "", "Tasks and models "
            "compared in this report. All providers use free-tier APIs only.",
            "", "## 2. Results Table", "", _md_table([
                "Task", "Model", "Pass", "Iter", "In Tok", "Out Tok", "Time",
                "Avg Req", "Retries", "First Edit", "First Pass",
                "Steps After Pass"], all_rows), "",
            "## 3. Provider Reliability", ""]
        by_model = acc.summary_by_model()
        if by_model:
            rel_rows = [
                [m, str(s["pass_rate"]), str(s["avg_request_ms"]) + "ms",
                 str(s["total_retries"]), str(s["avg_time_s"]) + "s"]
                for m, s in by_model.items()]
            lines += [_md_table(["Model", "Pass Rate", "Avg Req Time",
                                 "Total Retries", "Avg Task Time"],
                                rel_rows), ""]
        lines += [
            "## 4. Intermediary Metrics",
            "",
            "- **First Edit Step**: iteration at which agent first called "
            "`edit_file()` on the patched file.",
            "- **First Pass Step**: iteration at which tests first reported "
            "passing.",
            "- **Steps After Pass**: iterations between first pass and "
            "`final_answer()` call (lower is better).",
            "",
            "## 5. Ablation Study",
            "",
            "*(Fill in manually: one before/after comparison of a prompt or "
            "tool change.)*",
            "",
            "| Change | Model | Task | Pass Before | Pass After | Iter Before "
            "| Iter After |",
            "| ------ | ----- | ---- | ----------- | ---------- | ----------- "
            "| ---------- |",
            "| Example: added step-by-step example to prompt | qwen3-8b | "
            "sympy-14711 | ❌ | ✅ | - | 8 |",
            "",
            "## 6. Conclusions",
            "",
            "*(Fill in: which models to use, which to discard, "
            "based on data above.)*"]

        output_path.write_text("\n".join(lines))
        print(f"Report written to {output_path}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--solutions-dir", required=True)
    p.add_argument("--output", default="BENCHMARK_REPORT.md")
    args = p.parse_args()
    build_report(Path(args.solutions_dir), Path(args.output))


if __name__ == "__main__":
    main()
