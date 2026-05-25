"""
Shared helper: resolve paths that refer to /testbed.

In real SWE-bench runs the repo is mounted at /testbed inside Docker.
During local exam testing the exam script sets TESTBED_PATH to a local
directory. All tools that operate on the testbed use _resolve() so they
work in both environments without changes.
"""
import os

_TESTBED_ROOT = "/testbed"


def _resolve(path: str) -> str:
    """Replace a /testbed prefix with TESTBED_PATH if that env var is set."""
    testbed = os.environ.get("TESTBED_PATH", _TESTBED_ROOT)
    if path == _TESTBED_ROOT:
        return testbed
    if path.startswith(_TESTBED_ROOT + "/") or path.startswith(_TESTBED_ROOT + os.sep):
        return testbed + path[len(_TESTBED_ROOT):]
    return path


def testbed() -> str:
    """Return the resolved /testbed root."""
    return os.environ.get("TESTBED_PATH", _TESTBED_ROOT)
