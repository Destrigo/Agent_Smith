from pydantic import BaseModel, Field


class MBPPTaskInput(BaseModel):
    task_id: str
    task_definition: str
    function_definition: str
    test_imports: list[str] = Field(default_factory=list)
    test_list: list[str] = Field(default_factory=list)


class SWEBenchTaskInput(BaseModel):
    instance_id: str = Field(..., description="SWE-bench instance identifier")
    problem_statement: str = Field(..., description="GitHub issue description")
    docker_image: str = Field(
        ..., description="Docker image used for evalution")
    eval_script: str = Field(
        ..., description="Evaluation script executed inside the container")
    hints_text: str = Field(default="", description="Optional dataset hints")
    repo: str = Field(default="", description="Repository name")
