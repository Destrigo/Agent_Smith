import io
from contextlib import redirect_stdout
from sandbox_model import SandboxConfig

class Sandbox(SandboxConfig):
    def __init__(self):
        super().__init__()
        self.tools = {
            "hello": 0
        }

    def execute(self, code: str):
        stdout_buffer = io.StringIO()

        sandbox_globals = {
            "__builtins__": __builtins__,
            **self.tools
        }

        try:
            with redirect_stdout(stdout_buffer):
                exec(code, sandbox_globals)

            return {
                "success": True,
                "stdout": stdout_buffer.getvalue(),
                "error": None
            }

        except Exception as e:
            return {
                "success": False,
                "stdout": stdout_buffer.getvalue(),
                "error": str(e)
            }