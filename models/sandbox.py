from typing import Optional
from pydantic import BaseModel, Field


class SandboxResult(BaseModel):
    success: bool = Field(..., description="True if execution completed "
                          "without unhandled exceptions")
    stdout: str = Field(
        default="", description="Captured stdout from executed code")
    stderr: str = Field(
        default="", description="Captured stderr from executed code")
    error: Optional[str] = Field(
        default=None, 
        description="Execution error message if execution failed")
    execution_time_ms: float = Field(
        default=0.0, description="Wall-clock execution time in milliseconds")
    memory_usage_mb: float = Field(
        default=0.0, description="Peak memory usage during execution")
    final_answer: Optional[str] = Field(
        default=None, 
        description="Value passed to final_answer() inside sandbox")