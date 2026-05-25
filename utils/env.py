"""
Environment variable utilities.

Loads API keys and configuration from a .env file so that
no credentials are hardcoded in the source code.
"""

import os
from pathlib import Path


def load_env(env_file: str = ".env") -> None:
    """
    Load environment variables from *env_file* (default: .env in cwd).

    Lines starting with '#' are treated as comments.
    Already-set variables in the environment are NOT overwritten.
    """
    env_path = Path(env_file)
    if not env_path.exists():
        return
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


def get_api_key(key_name: str) -> str:
    """
    Return the value of environment variable *key_name*.

    Raises EnvironmentError with a clear message if the variable is not set,
    so students get an actionable error instead of a silent None.
    """
    value = os.environ.get(key_name, "").strip()
    if not value:
        raise EnvironmentError(
            f"Required environment variable '{key_name}' is not set. "
            f"Add it to your .env file or export it before running."
        )
    return value
