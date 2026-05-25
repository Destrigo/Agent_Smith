from pydantic import BaseModel, Field
from typing import Literal, Optional, Any
from models.llm import Message


class AgentState(BaseModel):
    """
    Mutable state carried across iterations of the agent loop.
    Serializable so it can be logged / inspected at any point.
    """
    task_id: str
    benchmark: Literal["mbpp", "swebench"]
    iteration: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_requests: int = 0
    start_time: Optional[float] = None
    messages: list[Message] = Field(default_factory=list)
    steps: list[dict[str, Any]] = Field(default_factory=list)
    final_answer: Optional[str] = None
    failed: bool = False
    error: Optional[str] = None
    compressed_history: Optional[str] = None
    baseline_test_output: Optional[str] = None
    max_iterations: int = 10
    max_input_tokens: int = 6000
    max_output_tokens: int = 1500
    max_time_seconds: int = 120

    def is_done(self) -> bool:
        return self.final_answer is not None or self.failed

    def within_limits(self) -> tuple[bool, str]:
        if self.iteration >= self.max_iterations:
            return False, f"max_iterations={self.max_iterations} reached"
        if self.total_input_tokens >= self.max_input_tokens:
            return False, f"max_input_tokens={self.max_input_tokens} exceeded"
        if self.total_output_tokens >= self.max_output_tokens:
            return (False, f"max_output_tokens={self.max_output_tokens} "
                    "exceeded")
        if self.start_time is not None:
            import time
            elapsed = time.time() - self.start_time
            if elapsed >= self.max_time_seconds:
                return (False,
                        f"max_time_seconds={self.max_time_seconds} exceeded "
                        f"(elapsed={elapsed:.1f}s)")
        return True, ""
