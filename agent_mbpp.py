import argparse
import logging
import sys
from pathlib import Path
import io
import os
import contextlib
from dotenv import load_dotenv
from models.sandbox import SandboxResult
from models.task import MBPPTaskInput
from agent.llm.manager import LLMManager
from agent.core.agent_loop import AgentLoop
from utils.logger import setup_logging


PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv()


def build_task_message(task: MBPPTaskInput) -> str:
    tests_block = "\n".join(task.test_list)
    imports_block = "\n".join(task.test_imports) if task.test_imports else ""
    return (
        f"Task #{task.task_id}: {task.task_definition}\n\n"
        f"Function signature to implement:\n{task.function_definition}\n\n"
        f"Tests that must pass:\n{tests_block}\n"
        + (f"\nRequired imports for tests:\n{imports_block}\n"
           if imports_block else "")
        + "\nSolve this step by step. Call run_tests() to verify, "
        "then final_answer() to submit.")


def _build_system_prompt(sandbox) -> str:
    manual = ""
    if hasattr(sandbox, "get_manual"):
        try:
            manual = sandbox.get_manual()
        except Exception:
            pass
    prompt_path = PROJECT_ROOT / "agent" / "prompt" / "mbpp_prompt.txt"
    static_prompt = prompt_path.read_text(encode="utf-8")
    if manual:
        return static_prompt + "\n\n" + manual
    return static_prompt


class _StubSandboxClient:
    """
    Development stub that runs code locally (no security restrictions).
    Replace with Agent A's real sandbox before final integration.
    """
    def __init__(self, task: MBPPTaskInput) -> None:
        self._task = task

    def execute(self, code: str):
        def run_tests(solution_code: str) -> str:
            try:
                namespace: dict = {}
                exec(solution_code, namespace)
                for test_import in self._task.test_imports:
                    exec(test_import, namespace)
                for test in self._task.test_list:
                    exec(test, namespace)
                return "ALL TESTS PASSED"
            except AssertionError as e:
                return f"ASSERTION FAILED: {e}"
            except Exception as e:
                return f"ERROR: {type(e).__name__}: {e}"

        _final_answers: list = []

        def final_answer(sol):
            _final_answers.append(sol)

        namespace = {"run_tests": run_tests, "final_answer": final_answer}
        stdout_buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(stdout_buf):
                exec(code, namespace)
            return SandboxResult(
                success=True, stdout=stdout_buf.getvalue(), stderr="",
                error=None, execution_time_ms=0.0, memory_usage_mb=0.0,
                final_answer=_final_answers[0] if _final_answers else None)
        except Exception as exc:
            return SandboxResult(
                success=False, stdout=stdout_buf.getvalue(), stderr="",
                error=f"{type(exc).__name__}: {exc}", execution_time_ms=0.0,
                memory_usage_mb=0.0)


def make_sandbox_client(task: MBPPTaskInput):
    test_lines = list(task.test_imports) + list(task.test_list)
    os.environ["SANDBOX_TEST_CODE"] = "\n".join(test_lines)
    try:
        from sandbox.core.sandbox import Sandbox
        from sandbox.config import SandboxConfig
        config = SandboxConfig()
        mcp_cmd = f"python {PROJECT_ROOT}/mcp_servers/mcp_tools_mbpp.py"
        return Sandbox(config, mcp_stdio=mcp_cmd,
                       task_context=task.model_dump())
    except ImportError:
        logging.warning("Sandbox module not found - using StubSanboxClient")
        return _StubSandboxClient(task)


def main() -> None:
    parser = argparse.ArgumentParser(description="MBPP Agent")
    parser.add_argument("--task-file", required=True,
                        help="Path to task JSON file")
    parser.add_argument("--output", required=True,
                        help="Path to write solution JSON")
    parser.add_argument("--model-name", required=True,
                        help="Model identifiler, eg. qwen/qwen3-b:free")
    parser.add_argument("--provider-url", required=True, help="API base URL")
    parser.add_argument("--provider", default="openrouter",
                        help="Provider name for key lookup")
    parser.add_argument("--max-iterations", type=int, default=10)
    parser.add_argument("--max-input-tokens", type=int, default=6000)
    parser.add_argument("--max-output-tokens", type=int, default=1500)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()
    setup_logging(args.log_level)
    logger = logging.getLogger(__name__)

    task_path = Path(args.task_file)
    if not task_path.exists():
        logger.error("Task file not found: %s", task_path)
        sys.exit(1)
    task = MBPPTaskInput.model_validate_json(task_path.read_text())
    logger.info("Loaded MBPP task #%s: %s", task.task_id,
                task.task_definition[:60])

    prompt_path = PROJECT_ROOT / "agent" / "prompts" / "mbpp_prompt.txt"
    system_prompt = prompt_path.read_text(encoding="utf-8")

    llm = LLMManager.from_env(provider=args.provider, model=args.model_name,
                              provider_url=args.provider_url)

    sandbox = make_sandbox_client(task)

    loop = AgentLoop(
        llm_manager=llm, sandbox_client=sandbox, system_prompt=system_prompt,
        max_iterations=args.max_iterations, max_input_tokens=6000,
        max_output_tokens=1500)
    user_message = build_task_message(task)
    result = loop.run(task_id=str(task.task_id), benchmark="mbpp",
                      user_message=user_message)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(result.model_dump_json(indent=2))

    logger.info("Done | success=%s iterations=%d input_tokens=%d "
                "output_tokens=%d time=%.1fs", result.success,
                result.iterations, result.total_input_tokens,
                result.total_output_tokens, result.total_time_seconds)
    sys.exit(0 if result.success else 1)


if __name__ == "__main__":
    main()
