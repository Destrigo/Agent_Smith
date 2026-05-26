from pydantic import BaseModel, Field, field_validator, model_validator


class MBPPTaskInput(BaseModel):
    """Input for MBPP task evaluation."""
    task_id: str

    @field_validator("task_id", mode="before")
    @classmethod
    def coerce_task_id(cls, v: object) -> str:
        """Accept int task_id from moulinette dump (e.g. 239 → '239')."""
        return str(v)

    @model_validator(mode="before")
    @classmethod
    def remap_public_fields(cls, data: object) -> object:
        """
        Moulinette dumps tasks with ``public_test_list`` / ``public_test_imports``
        field names.  Accept either spelling so the agent works with both the
        exam API format (``test_list``) and the moulinette dump format.
        """
        if not isinstance(data, dict):
            return data
        if "test_list" not in data and "public_test_list" in data:
            data["test_list"] = data["public_test_list"] or []
        if "test_imports" not in data and "public_test_imports" in data:
            data["test_imports"] = data["public_test_imports"] or []
        return data

    task_definition: str
    function_definition: str
    test_imports: list[str] = Field(default_factory=list)
    test_list: list[str] = Field(default_factory=list)


class SWEBenchTaskInput(BaseModel):
    """
    Input for a SWE-bench task, provided by the moulinette.
    Your agent receives this and must produce a git patch that fixes the issue.
    """
    instance_id: str = Field(
        ..., description="SWE-bench instance identifier,"
        " e.g. 'sympy__sympy-23534'")
    problem_statement: str = Field(
        ..., description="The GitHub issue description, "
        "what needs to be fixed")
    docker_image: str = Field(
        ..., description="Full Docker image name, e.g. "
        "'swebench/sweb.eval.x86_64.sympy_1776_sympy-23534:latest'")
    eval_script: str = Field(
        ..., description="Bash script to run inside the container "
        "to evaluate the patch")
    hints_text: str = Field(
        default="", description="Optional hints about "
        "the issue (may be empty)")
    repo: str = Field(
        default="", description="Repository name, e.g. 'sympy/sympy'")
