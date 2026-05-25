"""
Entry point for the MBPP agent, invoked via `uv run agent-mbpp`.

All logic lives in the root-level agent_mbpp.py so it can also be run
directly with `python agent_mbpp.py`. This thin wrapper makes the entry
point importable as `agent.cli.agent_mbpp:main` for pyproject.toml scripts.
"""
import sys
from pathlib import Path

# Ensure project root is on the path so root-level agent_mbpp.py is importable.
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from agent_mbpp import main  # noqa: F401

__all__ = ["main"]
