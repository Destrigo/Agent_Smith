from pydantic import BaseModel
from typing import Optional


class SWEBenchTaskInput(BaseModel):
    """Input for a SWE-bench task evaluation."""
    instance_id: str
    problem_statement: str
    docker_image: str
    eval_script: str
    hints_text: Optional[str] = None
    repo: str
