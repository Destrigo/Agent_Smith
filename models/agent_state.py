from pydantic import BaseModel, Field
from typing import Literal, Optional
from models.solution import StepMetrics
from models.llm import Message


class AgentState(BaseModel):
    task_id: str
    benchmark: Literal["mbpp", "swebench"]
    iteration: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_requests: int = 0
    start_time: Optional[float] = None
    messages: list[Message] = Field(default_factory=list)
    steps: list[StepMetrics] = Field(default_factory=list)
    current_model: str = ""
    current_provider: str = ""
    final_answer: Optional[str] = None
    failed: bool = False
    error: Optional[str] = None
    compressed_history: Optional[str] = None
    baseline_test_output: Optional[str] = None
    max_iterations: int = 10
    max_input_tokens: int = 6000
    max_output_tokens: int = 1500
    max_time_seconds: int = 120