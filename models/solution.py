from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class StepMetrics(BaseModel):
    """Metrics for a single agent step."""

    step: int
    input_tokens: int
    output_tokens: int
    request_time_ms: float
    api_url: str
    model_name: str
    llm_output: str
    sandbox_input: str
    sandbox_output: str
    retries: int
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class SolutionOutput(BaseModel):
    """Output from student solution — this is what students must produce."""

    task_id: str
    benchmark: Literal["mbpp", "swebench"]
    success: bool
    solution: str  # Python function code for MBPP, git patch for SWE-bench
    system_prompt: str
    iterations: int
    total_requests: int
    total_input_tokens: int
    total_output_tokens: int
    total_time_seconds: float
    steps: List[StepMetrics] = Field(default_factory=list)
    error: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
