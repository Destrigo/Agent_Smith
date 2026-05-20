import argparse
import json
import logging
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def run_mbpp_task(task_file: Path, output_file: Path, model: str,
                  provider: str, provider_url: str, max_iterations: int = 10
                  ) -> bool:
    cmd = [sys.executable, "-m", "agent.cli.agent_mbpp", "--task-file",
           str(task_file), "--output", str(output_file), "--model-name", model,
           "--provider", provider, "--provider-url", provider_url,
           "--max-iterations", str(max_iterations)]
    result = subprocess.run(cmd, capture_output=False)
    return result.returncode == 0


def run_swebench_task(task_file: Path, output_file: Path, model: str,
                      provider: str, provider_url: str,
                      max_iterations: int = 30) -> bool:
    cmd = [sys.executable, "-m", "agent.cli.agent_swebench", "--task-file",
           str(task_file), "--output", str(output_file), "--model-name", model,
           "--provider", provider, "--provider-url", provider_url,
           "--max-iterations", str(max_iterations)]
    result = subprocess.run(cmd, capture_output=False)
    return result.returncode == 0


def main() -> None:
    p = argparse.ArgumentParser(description="Evaluation runner")
    p.add_argument("--benchmark", choices=["mbpp", "swebench"], required=True)
    p.add_argument("--tasks", required=True,
                   help="Directory with task JSON files")
    p.add_argument("--model", required=True)
    p.add_argument("--provider", default="openrouter")
    p.add_argument("--provider-url", required=True)
    p.add_argument("--output-dir", required=True)
    p.add_argument("--max-iterations", type=int, default=None)
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    tasks_dir = Path(args.tasks)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    task_files = sorted(tasks_dir.glob("*.json"))
    if not task_files:
        logger.error("No task JSON files found in %s", tasks_dir)
        sys.exit(1)
    results = []
    for task_file in task_files:
        out_file = output_dir / f"{task_file.stem}_solution.json"
        logger.info("Running %s on %s ...", args.model, task_file.name)
        max_iter = args.max_iterations or (10 if args.benchmark == "mbpp"
                                           else 30)
        if args.benchmark == "mbpp":
            ok = run_mbpp_task(task_file, out_file, args.model, args.provider,
                               args.provider_url, max_iter)
        results.append({"task": task_file.name, "success": ok,
                        "output": str(out_file)})
        logger.info("   -> %s", "PASS" if ok else "FAIL")
    summary_path = output_dir / "run_summary.json"
    summary_path.write_text(json.dumps(results, indent=2))
    passed = sum(1 for r in results if r["success"])
    logger.info("Results: %d/%d passed. Summary: %s", passed, len(results),
                summary_path)


if __name__ == "__main__":
    main()
