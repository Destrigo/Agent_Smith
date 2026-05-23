import argparse
import logging
import signal
import sys
import io
import os
import tarfile
import contextlib
from pathlib import Path
from dotenv import load_dotenv
from models.task import SWEBenchTaskInput
from models.solution import SolutionOutput
from models.sandbox import SandboxResult
from agent.llm.manager import LLMManager
from agent.core.agent_loop import AgentLoop
from mydocker.manager import DockerManager
from utils.logger import setup_logging


PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv()


def build_task_message(task: SWEBenchTaskInput) -> str:
    msg = (
        f"Repository: {task.repo}\n"
        f"Instance: {task.instance_id}\n\n"
        f"Issue to fix:\n{task.problem_statement}\n"
    )
    if task.hints_text:
        msg += f"\nHints:\n{task.hints_text}\n"
    msg += (
        "\nThe repository is mounted at /testbed inside the container.\n"
        "Follow the debugging methodology in your instructions.\n"
        "When done, call final_answer(get_patch())."
    )
    return msg


class _DockerStubClient:
    """
    Development stub: runs MCP tool calls directly in the Docker container.
    Replace with Agent A's real sandbox before submission.
    """
    def __init__(self, docker_mgr: DockerManager, task: SWEBenchTaskInput
                 ) -> None:
        self._mgr = docker_mgr
        self._task = task

    def execute(self, code: str) -> SandboxResult:
        mgr = self._mgr
        answers: list[str] = []

        def run_in_container(cmd: str, workdir: str = "/testbed") -> str:
            return mgr.exec_run(cmd, workdir)

        def read_file(filepath: str, start_line: int = None,
                      end_line: int = None) -> str:
            if start_line is not None and end_line is not None:
                cmd = (f"sed -n '{start_line},{end_line}p' "
                       f"{filepath} | nl -ba -nrz -v{start_line}")
            else:
                cmd = f"cat -n {filepath}"
            return run_in_container(cmd)

        def edit_file(filepath: str, old_str: str, new_str: str) -> str:
            result = mgr._container.exec_run(["cat", filepath])
            content = result.output.decode("utf-8", errors="replace") \
                if result.output else ""
            if old_str not in content:
                return (f"ERROR: old_str not found in {filepath}."
                        f"Check exact whitespace/content")
            new_content = content.replace(old_str, new_str, 1)
            tar_stream = io.BytesIO()
            parent_dir = os.path.dirname(filepath) or "/"
            filename = os.path.basename(filepath)
            file_data = new_content.encode("utf-8")
            with tarfile.open(fileobj=tar_stream, mode="w") as tar:
                tar_info = tarfile.TarInfo(name=filename)
                tar_info.size = len(file_data)
                tar.addfile(tar_info, io.BytesIO(file_data))
            tar_stream.seek(0)
            success = mgr._container.put_archive(parent_dir, tar_stream)
            if not success:
                return f"Error: failed to write updated file to {filepath}."
            return "File edited successfully."

        def list_files(directory: str, pattern: str = "*") -> str:
            return run_in_container(f"find '{directory}' -name '{pattern}' "
                                    "-type f 2>/dev/null | sort | head -100")

        def search_code(pattern: str, file_pattern: str = "*.py") -> str:
            flag = "-rEn" if any(c in pattern for c in r".*+?[](){}^$|\\") \
                  else "-rFn"
            return run_in_container(
                f"grep {flag} --include='{file_pattern}' "
                f"'{pattern}' /testbed 2>/dev/null | head -50")

        def search_function_or_class_definition_in_code(name: str) -> str:
            result = run_in_container(
                f"grep -rEn --include='*.py' "
                f"'(^|\\s)(async\\s+)?def\\s+{name}\\s*\\(|^class\\s+{name}"
                "[\\s:(]' /testbed 2>/dev/null | head -20")
            if not result.strip():
                result = run_in_container(
                    f"grep -rn --include='*.py' '{name}' /testbed 2>/dev/null "
                    "| head -20")
                if result.strip():
                    result = "[No definition found. Broad matches:]\n{result}"
            return result

        def find_references(name: str, filepath: str = "", line: int = 0
                            ) -> str:
            scope = f"'{filepath}'" if filepath else "/testbed"
            return run_in_container(
                f"grep -rEn --include='*.py' '\\b{name}\\b' {scope} "
                "2>/dev/null | head -30")

        def run_tests() -> str:
            return run_in_container("bash /tmp/eval_script.sh 2>&1 | tail -50")

        def run_command(command: str, workdir: str = "/testbed") -> str:
            return run_in_container(command, workdir)

        def get_patch() -> str:
            return run_in_container("git -c core.fileMode=false diff HEAD",
                                    workdir="/testbed")

        def final_answer(patch: str):
            answers.append(patch)

        namespace = {
            "read_file": read_file, "edit_file": edit_file,
            "list_files": list_files, "search_code": search_code,
            "search_function_or_class_definition_in_code":
            search_function_or_class_definition_in_code,
            "find_references": find_references, "run_tests": run_tests,
            "run_command": run_command, "get_patch": get_patch,
            "final_answer": final_answer}

        stdout_buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(stdout_buf):
                exec(code, namespace)
            return SandboxResult(
                success=True, stdout=stdout_buf.getvalue(), stderr="",
                error=None, execution_time_ms=0.0, memory_usage_mb=0.0,
                final_answer=answers[0] if answers else None)
        except Exception as exc:
            return SandboxResult(
                success=False, stdout=stdout_buf.getvalue(), stderr="",
                error=f"{type(exc).__name__}: {exc}", execution_time_ms=0.0,
                memory_usage_mb=0.0)


def _make_sandbox_client(container_id: str, task: SWEBenchTaskInput,
                         docker_mgr: DockerManager):
    """
    Connect to Agent A's sandbox, configured with SWE-bench MCP tools
    that bridge into the Docker container.
    """
    try:
        from sandbox.core.sandbox import Sandbox
        from sandbox.config import SandboxConfig
        config = SandboxConfig(
            allowed_directories=["/testbed", "/tmp/agent"],
            max_execution_time_seconds=120, max_memory_mb=1024)
        mcp_cmd = (f"python {PROJECT_ROOT}/mcp_servers/mcp_tools_swebench.py "
                   f"--container-id {container_id}")
        return Sandbox(config, mcp_stdio=mcp_cmd)
    except ImportError:
        logging.warning("Sandbox module not found - using DockerStubClient")
        return _DockerStubClient(docker_mgr, task)


def main() -> None:
    parser = argparse.ArgumentParser(description="SWE-bench Agent")
    parser.add_argument("--task-file", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--model-name", required=True)
    parser.add_argument("--provider-url", required=True)
    parser.add_argument("--provider", default="openrouter")
    parser.add_argument("--max-iterations", type=int, default=30)
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()
    setup_logging(args.log_level)
    logger = logging.getLogger(__name__)
    task_path = Path(args.task_file)
    task = SWEBenchTaskInput.model_validate_json(task_path.read_text())
    logger.info("Loaded SWE-bench task: %s", task.instance_id)
    docker_mgr = DockerManager()

    def _cleanup(sig=None, frame=None):
        logger.info("Signal received - cleaning up Docker container...")
        docker_mgr.cleanup()
        sys.exit(1)

    signal.signal(signal.SIGINT, _cleanup)
    signal.signal(signal.SIGTERM, _cleanup)

    try:
        logger.info("Starting Docker container: %s", task.docker_image)
        container_id = docker_mgr.start(image=task.docker_image,
                                        eval_script=task.eval_script)
        logger.info("Container ready: %s", container_id[:12])

        prompt_path = (PROJECT_ROOT / "agent" / "prompts"
                       / "swebench_prompt.txt")
        system_prompt = prompt_path.read_text(encoding="utf-8")

        llm = LLMManager.from_env(
            provider=args.provider, model=args.model_name,
            provider_url=args.provider_url)
        sandbox = _make_sandbox_client(container_id, task, docker_mgr)
        loop = AgentLoop(
            llm_manager=llm, sandbox_client=sandbox,
            system_prompt=system_prompt, max_iterations=args.max_iterations,
            max_input_tokens=300000, max_output_tokens=10000)
        result = loop.run(task_id=task.instance_id, benchmark="swebench",
                          user_message=build_task_message(task))
    except Exception as exc:
        logger.error("Agent crashed: %s", exc, exc_info=True)
        result = SolutionOutput(
            task_id=task.instance_id, benchmark="swebench", success=False,
            solution="", iterations=0, total_requests=0, total_input_tokens=0,
            total_output_tokens=0, total_time_seconds=0.0, error=str(exc))
    finally:
        logger.info("Stopping and removing Docker container...")
        docker_mgr.cleanup()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(result.model_dump_json(indent=2))
    logger.info("Done | success=%s iterations=%d time=%.1fs", result.success,
                result.iterations, result.total_time_seconds)
    sys.exit(0 if result.success else 1)


if __name__ == "__main__":
    main()
