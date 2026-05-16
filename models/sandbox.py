from typing import Optional
from pydantic import BaseModel, Field


class SandboxResult(BaseModel):
    """
    Returned by sandbox.execute(code: str) after running one code block.

    Agent B reads:
        - stdout + stderr  → forms the "Observation" sent back to the LLM
        - final_answer     → if set, the agent loop terminates with this value
        - success=False    → pass error info to the LLM so it can self-correct
    """
    success: bool = Field(
        ..., description="True if the code ran without unhandled exceptions")
    stdout: str = Field(
        default="",
        description="Captured standard output from the executed code")
    stderr: str = Field(
        default="",
        description="Captured standard error from the executed code")
    error: Optional[str] = Field(
        default=None,
        description="Exception message if execution failed (None on success)")
    execution_time_ms: float = Field(
        default=0.0, description="Wall-clock time for code execution in ms")
    memory_usage_mb: float = Field(
        default=0.0, description="Peak memory usage during execution in MB")
    final_answer: Optional[str] = Field(
        default=None,
        description="Set when the code called final_answer(). "
        "Signals the agent loop to stop.")