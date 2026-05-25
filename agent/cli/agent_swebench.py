"""
Entry point for the SWE-bench agent, invoked via `uv run agent-swebench`.

All logic lives in the root-level agent_swebench.py so it can also be run
directly with `python agent_swebench.py`. This thin wrapper makes the entry
point importable as `agent.cli.agent_swebench:main` for pyproject.toml scripts.
"""
import sys
from pathlib import Path

# Ensure project root is on the path so root-level agent_swebench.py is importable.
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from agent_swebench import main  # noqa: F401

__all__ = ["main"]
