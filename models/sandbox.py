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

    def as_observation(self) -> str:
        parts: list[str] = []
        if not self.success and self.error:
            if "timeout" in self.error.lower():
                parts.append("[SANDBOX] Execution timed out after limit. "
                             "Partial output preserved below.")
            elif "MemoryError" in self.error:
                parts.append("[SANDBOX] Execution exceeded memory limit and "
                             "was terminated.")
            elif "ImportError" in self.error:
                parts.append("[SANDBOX] Import blocked by security policy.\n"
                             "Only authorized imports are allowed. Error: "
                             f"{self.error}")
            elif "PermissionError" in self.error or "path" in self.error.lower(
            ):
                parts.append("[SANDBOX] Filesystem access denied.\n"
                             "Only allowed directories are accessible. Error: "
                             f"{self.error}")
            else:
                parts.append(f"[SANDBOX] Execution error:\n{self.error}")
        if self.stdout:
            output = self.stdout
            if len(output) > 8000:
                output = output[:8000]
                parts.append(
                    "[SANDBOX] Tool output was truncated to 8000 chars.\n"
                    f"Consider reading smaller ranges.\n\nOutput:\n{output}")
            else:
                parts.append(f"Output:\n{output}")
        if self.stderr and self.stderr.strip():
            parts.append(f"Stderr:\n{self.stderr.strip()}")
        if not parts:
            parts.append("[SANDBOX] Code executed successfully with no output")
        return "\n\n".join(parts)
