import logging
import time
from typing import Any, Literal, Optional
from models.agent_state import AgentState
from models.llm import Message, LLMRequest, LLMResponse
from models.solution import SolutionOutput, StepMetrics
from models.sandbox import SandboxResult
from agent.parsing.code_extractor import CodeExtractor
from agent.llm.manager import LLMManager

logger = logging.getLogger(__name__)


class AgentLoop:
    def __init__(self, llm_manager: LLMManager, sandbox_client: Any,
                 system_prompt: str, max_iterations: int = 10,
                 max_input_tokens: int = 6000,
                 max_output_tokens: int = 1500,
                 max_time_seconds: int = 120) -> None:
        self.llm = llm_manager
        self.sandbox = sandbox_client
        self.system_prompt = system_prompt
        self.extractor = CodeExtractor()
        self.max_iterations = max_iterations
        self.max_input_tokens = max_input_tokens
        self.max_output_tokens = max_output_tokens
        self.max_time_seconds = max_time_seconds

    def _call_llm(self, state: AgentState
                  ) -> tuple[Optional[LLMResponse], int]:
        request = LLMRequest(
            model=self.llm.current_model,
            messages=state.messages,
            max_tokens=max(
                1, min(1024,
                       self.max_output_tokens - state.total_output_tokens)),
            stop_sequences=["<end_code>", "Observation:"])
        return self.llm.complete(request)

    def _execute(self, code: str) -> SandboxResult:
        try:
            raw = self.sandbox.execute(code)
        except Exception as exc:
            logger.error("Sandbox call failed: %s", exc)
            return SandboxResult(success=False, stdout="", stderr="",
                                 error=f"Sandbox communication error : {exc}",
                                 execution_time_ms=0.0, memory_usage_mb=0.0)
        if isinstance(raw, SandboxResult):
            return raw
        return SandboxResult(
            success=raw.get("success", False), stdout=raw.get("stdout", ""),
            stderr=raw.get("stderr", ""), error=raw.get("error"),
            execution_time_ms=raw.get("execution_time_ms", 0.0),
            memory_usage_mb=raw.get("memory_usage_mb", 0.0),
            final_answer=raw.get("final_answer"))

    def run(self, task_id: str, benchmark: Literal["mbpp", "swebench"],
            user_message: str) -> SolutionOutput:
        state = AgentState(task_id=task_id, benchmark=benchmark,
                           max_iterations=self.max_iterations,
                           max_input_tokens=self.max_input_tokens,
                           max_output_tokens=self.max_output_tokens,
                           max_time_seconds=self.max_time_seconds)
        state.start_time = time.time()
        state.messages.append(Message(role="system",
                                      content=self.system_prompt))
        state.messages.append(Message(role="user", content=user_message))
        logger.info("Starting agent loop | task=%s benchmark=%s", task_id,
                    benchmark)
        while not state.is_done():
            ok, reason = state.within_limits()
            if not ok:
                logger.warning("Limit reached: %s", reason)
                state.failed = True
                state.error = f"Stopped: {reason}"
                break
            state.iteration += 1
            logger.info("--- Iteration %d ---", state.iteration)

            t0 = time.perf_counter()
            llm_response, retries = self._call_llm(state)
            request_time_ms = (time.perf_counter() - t0) * 1000.0
            if llm_response is None:
                state.failed = True
                state.error = "LLM API failed after all retries"
                break
            state.total_input_tokens += llm_response.input_tokens
            state.total_output_tokens += llm_response.output_tokens
            state.total_requests += 1 + retries
            state.messages.append(Message(role="assistant",
                                          content=llm_response.content))

            code, extraction_note = self.extractor.extract(
                llm_response.content)
            if code is None:
                observation = (
                    "[SANDBOX] No executable code block was found "
                    "in responses.\n"
                    "Please respond with a Python code block delimited by:\n"
                    "```python\n"
                    "# your code here\n"
                    "```\n"
                    "<end_code>")
                sandbox_result = SandboxResult(
                    success=False, stdout="", stderr="",
                    error="No code block found", execution_time_ms=0.0,
                    memory_usage_mb=0.0)
            else:
                sandbox_result = self._execute(code)
                observation = sandbox_result.as_observation()
                if extraction_note:
                    observation = f"[PARSER] {extraction_note}\n{observation}"
                if sandbox_result.final_answer is not None:
                    state.final_answer = sandbox_result.final_answer
                    logger.info("final_answer() received -> task complete")

            step = StepMetrics(step=state.iteration,
                               input_tokens=llm_response.input_tokens,
                               output_tokens=llm_response.output_tokens,
                               request_time_ms=request_time_ms,
                               api_url=llm_response.api_url,
                               model_name=llm_response.model_name,
                               llm_output=llm_response.content,
                               sandbox_input=code or "",
                               sandbox_output=observation,
                               retries=retries)
            state.steps.append(step.model_dump())
            if state.is_done():
                break
            state.messages.append(Message(
                role="user", content=f"Observation:\n{observation}"))
        total_time = time.time() - state.start_time
        return SolutionOutput(task_id=task_id, benchmark=benchmark,
                              success=state.final_answer is not None,
                              solution=state.final_answer or "",
                              system_prompt=self.system_prompt,
                              iterations=state.iteration,
                              total_requests=state.total_requests,
                              total_input_tokens=state.total_input_tokens,
                              total_output_tokens=state.total_output_tokens,
                              total_time_seconds=total_time,
                              steps=[StepMetrics(**s) for s in state.steps],
                              error=state.error)
