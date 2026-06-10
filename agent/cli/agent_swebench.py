import argparse
import logging
import signal
import sys
import os
from pathlib import Path
from typing import Any
from dotenv import load_dotenv
from models.task import SWEBenchTaskInput
from models.solution import SolutionOutput
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


def _build_system_prompt(sandbox: Any) -> str:
    manual = ""
    if hasattr(sandbox, "get_manual"):
        try:
            manual = sandbox.get_manual()
        except Exception:
            pass
    prompt_path = PROJECT_ROOT / "agent" / "prompts" / "swebench_prompt.txt"
    static_prompt = prompt_path.read_text(encoding="utf-8")
    if manual:
        return static_prompt + "\n\n" + manual
    return static_prompt


def _make_sandbox_client(container_id: str, task: SWEBenchTaskInput,
                         docker_mgr: DockerManager, eval_script_path: str
                         ) -> Any:
    """Connect the real sandbox with SWE-bench MCP tools bridging into Docker."""
    os.environ["SANDBOX_EVAL_SCRIPT"] = eval_script_path
    os.environ["DOCKER_CONTAINER_ID"] = container_id
    from sandbox.core.sandbox import Sandbox
    from models.sandbox_model import SandboxConfig
    from mcp_servers.mcp_client import MCPClient
    config = SandboxConfig(
        allowed_directories=["/testbed", "/tmp/agent"],
        max_execution_time_seconds=120, max_memory_mb=1024)
    sandbox = Sandbox(config)
    mcp_script = str(PROJECT_ROOT / "mcp_tools_swebench.py")
    mcp_client = MCPClient()
    mcp_client.connect_stdio("python", [mcp_script])
    sandbox.register_mcp_tools(mcp_client.make_tool_wrappers())
    setattr(sandbox, "_mcp_client", mcp_client)  # keep subprocess alive
    return sandbox


def main() -> None:
    parser = argparse.ArgumentParser(description="SWE-bench Agent")
    parser.add_argument("--task-file", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--model-name",
                        default=os.getenv("AGENT_MODEL", "mistral-large-latest"))
    parser.add_argument("--provider-url",
                        default=os.getenv("AGENT_PROVIDER_URL",
                                          "https://api.mistral.ai/v1"))
    parser.add_argument("--provider",
                        default=os.getenv("AGENT_PROVIDER", "mistral"))
    parser.add_argument("--max-iterations", type=int, default=30)
    parser.add_argument("--max-input-tokens", type=int, default=300000)
    parser.add_argument("--max-output-tokens", type=int, default=10000)
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()
    setup_logging(args.log_level)
    logger = logging.getLogger(__name__)
    task_path = Path(args.task_file)
    task = SWEBenchTaskInput.model_validate_json(task_path.read_text())
    logger.info("Loaded SWE-bench task: %s", task.instance_id)
    docker_mgr = DockerManager()

    def _cleanup(sig: Any = None, frame: Any = None) -> None:
        logger.info("Signal %s - cleaning up Docker container...", sig)
        docker_mgr.cleanup()
        sys.exit(0)

    signal.signal(signal.SIGINT, _cleanup)
    signal.signal(signal.SIGTERM, _cleanup)
    result: SolutionOutput
    try:
        logger.info("Starting Docker container: %s", task.docker_image)
        container_id = docker_mgr.start(image=task.docker_image,
                                        eval_script=task.eval_script)
        logger.info("Container ready: %s", container_id[:12])

        eval_script_path = "/tmp/eval_script.sh"
        sandbox = _make_sandbox_client(container_id, task, docker_mgr,
                                       eval_script_path)

        system_prompt = _build_system_prompt(sandbox)
        llm = LLMManager.from_env(
            provider=args.provider, model=args.model_name,
            provider_url=args.provider_url)
        loop = AgentLoop(
            llm_manager=llm, sandbox_client=sandbox,
            system_prompt=system_prompt, max_iterations=args.max_iterations,
            max_input_tokens=args.max_input_tokens,
            max_output_tokens=args.max_output_tokens,
            max_time_seconds=args.timeout)
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
