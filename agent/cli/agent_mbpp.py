import argparse
import logging
import sys
from pathlib import Path
from typing import Any
import os
from dotenv import load_dotenv
from models.task import MBPPTaskInput
from agent.llm.manager import LLMManager
from agent.core.agent_loop import AgentLoop
from utils.logger import setup_logging


PROJECT_ROOT = Path(__file__).resolve().parents[2]
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


def _build_system_prompt(sandbox: Any) -> str:
    manual = ""
    if hasattr(sandbox, "get_manual"):
        try:
            manual = sandbox.get_manual()
        except Exception:
            pass
    prompt_path = PROJECT_ROOT / "agent" / "prompts" / "mbpp_prompt.txt"
    static_prompt = prompt_path.read_text(encoding="utf-8")
    if manual:
        return static_prompt + "\n\n" + manual
    return static_prompt


def make_sandbox_client(task: MBPPTaskInput) -> Any:
    test_lines = list(task.test_imports) + list(task.test_list)
    os.environ["SANDBOX_TEST_CODE"] = "\n".join(test_lines)
    from sandbox.core.sandbox import Sandbox
    from models.sandbox_model import SandboxConfig
    from mcp_servers.mcp_client import MCPClient
    config = SandboxConfig()
    sandbox = Sandbox(config)
    mcp_script = str(PROJECT_ROOT / "mcp_tools_mbpp.py")
    mcp_client = MCPClient()
    mcp_client.connect_stdio("python", [mcp_script])
    sandbox.register_mcp_tools(mcp_client.make_tool_wrappers())
    setattr(sandbox, "_mcp_client", mcp_client)  # keep subprocess alive
    return sandbox


def main() -> None:
    parser = argparse.ArgumentParser(description="MBPP Agent")
    parser.add_argument("--task-file", required=True,
                        help="Path to task JSON file")
    parser.add_argument("--output", required=True,
                        help="Path to write solution JSON")
    parser.add_argument("--model-name",
                        default=os.getenv("AGENT_MODEL", "mistral-large-latest"),
                        help="Model identifier (or set AGENT_MODEL in .env)")
    parser.add_argument("--provider-url",
                        default=os.getenv("AGENT_PROVIDER_URL",
                                          "https://api.mistral.ai/v1"),
                        help="API base URL (or set AGENT_PROVIDER_URL in .env)")
    parser.add_argument("--provider",
                        default=os.getenv("AGENT_PROVIDER", "mistral"),
                        help="Provider name for key lookup (or set AGENT_PROVIDER in .env)")
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

    llm = LLMManager.from_env(provider=args.provider, model=args.model_name,
                              provider_url=args.provider_url)

    sandbox = make_sandbox_client(task)
    system_prompt = _build_system_prompt(sandbox)

    loop = AgentLoop(
        llm_manager=llm, sandbox_client=sandbox, system_prompt=system_prompt,
        max_iterations=args.max_iterations,
        max_input_tokens=args.max_input_tokens,
        max_output_tokens=args.max_output_tokens,
        max_time_seconds=args.timeout)
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
