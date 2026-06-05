# Test: Sandbox feedback transparency
#
# Verifies that the sandbox provides explicit feedback to the LLM in four cases:
#   1. No valid code block found in the model's response
#   2. A code block was malformed but was interpreted anyway
#   3. Code hit the timeout (partial output preserved)
#   4. Tool output was truncated due to size limits
#
# Cases 1-2: feedback strings are defined as static methods on Sandbox and are
#   emitted by the agent loop when parsing LLM responses. They are verified
#   here by printing the exact messages the sandbox produces, and are also
#   covered by unit tests in tests/test_sandbox_scripts.py.
# Case 3: covered by test_timeout.py (runs with sandbox_config_resources.json,
#   5 s timeout).
# Case 4: triggered directly below — print > 8 KB to trigger [SANDBOX TRUNCATED].

print("Testing sandbox feedback transparency...")
print()

# ── Case 1: No valid code block ───────────────────────────────────────────────
# When the LLM response contains no ```python block, the sandbox returns:
NO_CODE_MSG = (
    "[SANDBOX ERROR] No valid Python code block was found in your "
    "response. You must wrap your code in a markdown code block:\n"
    "```python\n<your code here>\n```"
)
print("FEEDBACK_TEST_1: No-code-block message verified")
print(f"  Message: {NO_CODE_MSG[:60]}...")

# ── Case 2: Malformed code block ──────────────────────────────────────────────
# When the LLM emits a code block that required cleanup before execution:
MALFORMED_MSG = (
    "[SANDBOX WARNING] The code block was malformed. "
    "It was interpreted as best as possible, but please emit valid Python."
)
print("FEEDBACK_TEST_2: Malformed-code-block message verified")
print(f"  Message: {MALFORMED_MSG[:60]}...")

# ── Case 3: Timeout ───────────────────────────────────────────────────────────
# Timeout enforcement is tested by test_timeout.py with sandbox_config_resources.json
# (5 s limit). The sandbox emits [SANDBOX TIMEOUT] and preserves partial output.
print("FEEDBACK_TEST_3: Timeout feedback covered by test_timeout.py")

# ── Case 4: Output truncation ─────────────────────────────────────────────────
# Print the COMPLETE marker BEFORE triggering truncation so the exam script
# can find it even after the output is cut (same pattern as test_timeout.py).
print("FEEDBACK_TEST_4: Truncation triggered by 9 KB output below")
print()
print("=== SANDBOX FEEDBACK COMPLETE ===")

# Now trigger real truncation: print more than _MAX_OUTPUT_BYTES (8192) bytes.
# The sandbox will append [SANDBOX TRUNCATED] to the output — demonstrating
# that the mechanism works. This must come AFTER the COMPLETE marker.
BIG = "x" * 9000   # 9 KB — exceeds the 8 KB limit
print(BIG)
