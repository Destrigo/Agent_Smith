from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class SolutionOutput(BaseModel):
    """Output from student solution - this is what students must
    produce."""
    task_id: str
    benchmark: str # "mbpp" or "swebench"
    success: bool
    solution: str # Code for MBPP, patch for SWE-bench
    system_prompt: str
    iterations: int
    total_requests: int
    total_input_tokens: int
    total_output_tokens: int
    total_time_seconds: float
    steps: List["StepMetrics"] = Field(default_factory=list)
    error: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())