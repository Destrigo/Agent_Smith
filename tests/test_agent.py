import json
import pytest
from unittest.mock import MagicMock, patch
from models.llm import LLMRequest, LLMResponse, Message
from models.sandbox import SandboxResult
from models.solution import SolutionOutput, StepMetrics
from models.agent_state import AgentState
from models.task import MBPPTaskInput, SWEBenchTaskInput
from agent.parsing.code_extractor import CodeExtractor
from agent.core.agent_loop import AgentLoop
from agent.llm.manager import LLMManager
from agent.llm.providers import (RateLimitError, TransientError,
                                 PROVIDER_REGISTRY, openai_compatible_call)


@pytest.fixture
def simple_mbpp_task() -> MBPPTaskInput:
    return MBPPTaskInput(
        task_id="1", task_definition="Write a function that returns the square"
        " of a numbers.", function_definition="def square(n):",
        test_imports=[],
        test_list=["assert square(3) == 9", "assert square(0) == 0"])


def _make_loop(llm, sandbox, max_iterations=5) -> AgentLoop:
    return AgentLoop(llm_manager=llm, sandbox_client=sandbox,
                     system_prompt="You are a coding assistant.",
                     max_iterations=max_iterations, max_input_tokens=10000,
                     max_output_tokens=2000)


def _make_llm_mock(responses: list[str]) -> MagicMock:
    llm = MagicMock()
    llm.current_model = "test-model"
    call_count = [0]

    def complete(request):
        idx = min(call_count[0], len(responses) - 1)
        call_count[0] += 1
        resp = LLMResponse(content=responses[idx], input_tokens=50,
                           output_tokens=30, request_time_ms=100.0,
                           model_name="test-model", api_url="http://test")
        return resp, 0
    llm.complete.side_effect = complete
    return llm


def _make_request(model: str = "test-model") -> LLMRequest:
    return LLMRequest(
        model=model, messages=[Message(role="user", content="Hello")],
        provider_url="https://openrouter.ai/api/v1", api_key="test-key",
        stop_sequences=["<end_code>"])


class TestCodeExtractor:
    def setup_method(self):
        self.ex = CodeExtractor()

    def test_python_fence(self):
        text = ("Thought: let me solve this\n```python\nprint('hello')\n```\n"
                "<end_code>")
        code, note = self.ex.extract(text)
        assert code == "print('hello')"
        assert note == ""

    def test_python_fence_without_end_code(self):
        text = "```python\nx = 1 + 1\nprint(x)\n```"
        code, note = self.ex.extract(text)
        assert code is not None
        assert "x = 1 + 1" in code

    def test_generic_fence_python_like(self):
        text = "```\ndef foo(x):\n.  return x\n```"
        code, note = self.ex.extract(text)
        assert code is not None
        assert "interpreted as Python" in note

    def test_xml_invoke(self):
        text = (
            "<invoke name=\"read_file\">"
            "<parameter name=\"filepath\">/testbed/foo.py</parameter>"
            "<parameter name=\"start_line\">1</parameter>"
            "</invoke>"
        )
        code, note = self.ex.extract(text)
        assert code is not None
        assert "read_file(" in code
        assert "XML" in note

    def test_json_tool_call(self):
        text = ('<tool_call>{"name": "search_code", "arguments": {"pattern": '
                '"def foo"}}</tool_call>')
        code, note = self.ex.extract(text)
        assert code is not None
        assert "search_code(" in code
        assert "JSON" in note

    def test_react_format(self):
        text = 'Action: run_tests\nAction Input: {"code": "def f(): pass"}'
        code, note = self.ex.extract(text)
        assert code is not None
        assert "run_tests(" in code
        assert "ReAct" in note

    def test_no_code_returns_none(self):
        text = "I need to think about this problem more carefully."
        code, note = self.ex.extract(text)
        assert code is None
        assert note == ""

    def test_priority_python_over_xml(self):
        text = ("```python\nresult = 42\n```\n<invoke name=\"foo\">"
                "<parameter name=\"x\">1</parameter></invoke>")
        code, _ = self.ex.extract(text)
        assert "result = 42" in code


class TestAgentState:
    def test_within_limits_initially(self):
        state = AgentState(task_id="1", benchmark="mbpp", max_iterations=10,
                           max_input_tokens=6000, max_output_tokens=1500)
        ok, reason = state.within_limits()
        assert ok
        assert reason == ""

    def test_iteration_limit(self):
        state = AgentState(task_id="1", benchmark="mbpp", max_iterations=3)
        state.iteration = 3
        ok, reason = state.within_limits()
        assert not ok
        assert "max_iterations" in reason

    def test_input_token_limit(self):
        state = AgentState(task_id="1", benchmark="mbpp", max_input_tokens=100)
        state.total_input_tokens = 100
        ok, reason = state.within_limits()
        assert not ok
        assert "max_input_tokens" in reason

    def test_is_done_with_final_answer(self):
        state = AgentState(task_id="1", benchmark="mbpp")
        assert not state.is_done()
        state.final_answer = "def foo(): pass"
        assert state.is_done()

    def test_is_done_when_failed(self):
        state = AgentState(task_id="1", benchmark="mbpp")
        state.failed = True
        assert state.is_done()


class TestSandboxResult:
    def test_success_with_output(self):
        r = SandboxResult(success=True, stdout="hello world")
        obs = r.as_observation()
        assert "hello world" in obs

    def test_timeout_error(self):
        r = SandboxResult(success=False,
                          error="TimeoutError: execution timeout")
        obs = r.as_observation()
        assert "[SANDBOX]" in obs
        assert "timed out" in obs.lower()

    def test_import_error(self):
        r = SandboxResult(success=False,
                          error="ImportError: No module named 'os'")
        obs = r.as_observation()
        assert "Import blocked" in obs

    def test_truncation(self):
        r = SandboxResult(success=True, stdout="x" * 9000)
        obs = r.as_observation()
        assert "truncated" in obs.lower()

    def test_no_output(self):
        r = SandboxResult(success=True, stdout="")
        obs = r.as_observation()
        assert "no output" in obs.lower()

    def test_stderr_included(self):
        r = SandboxResult(success=True, stdout="ok",
                          stderr="warning: something")
        obs = r.as_observation()
        assert "warning: something" in obs


class TestAgentLoop:
    def test_successful_run_one_iteration(self):
        llm = _make_llm_mock(["Thought: solve it.\n```python\n"
                              "final_answer('def foo(): return 1')\n```"
                              "<end_code>"])
        sandbox = MagicMock()
        sandbox.execute.return_value = SandboxResult(
            success=True, stdout="submitted",
            final_answer="def foo(): return 1")
        result = _make_loop(llm, sandbox).run("test_1", "mbpp", "Write foo()")
        assert result.success
        assert result.solution == "def foo(): return 1"
        assert result.iterations == 1
        assert len(result.steps) == 1
        assert result.steps[0].sandbox_input != ""

    def test_no_code_block_feedback(self):
        llm = _make_llm_mock(["I think the answer is 42.",
                              "```python\nfinal_answer('def foo(): return 42')"
                              "\n```\n<end_code>"])
        sandbox = MagicMock()
        sandbox.execute.return_value = SandboxResult(
            success=True, stdout="", final_answer="def foo(): return 42")
        result = _make_loop(llm, sandbox).run("test_2", "mbpp", "Write foo()")
        assert result.success
        assert result.iterations == 2
        assert result.steps[0].sandbox_input == ""
        assert "[SANDBOX]" in result.steps[0].sandbox_output

    def test_limit_enforcement(self):
        llm = _make_llm_mock(["Just thinking..." for _ in range(10)])
        sandbox = MagicMock()
        loop = AgentLoop(llm_manager=llm, sandbox_client=sandbox,
                         system_prompt="test", max_iterations=3,
                         max_input_tokens=10000, max_output_tokens=2000)
        result = loop.run("test_3", "mbpp", "task")
        assert not result.success
        assert result.iterations == 3
        assert "max_iterations" in (result.error or "")

    def test_step_metrics_populated(self):
        llm = _make_llm_mock(["```python\nfinal_answer('solution')\n```\n"
                              "<end_code>"])
        sandbox = MagicMock()
        sandbox.execute.return_value = SandboxResult(
            success=True, stdout="ok", final_answer="solution")
        result = _make_loop(llm, sandbox).run("t4", "mbpp", "task")
        step = result.steps[0]
        assert step.step == 1
        assert step.input_tokens == 50
        assert step.output_tokens == 30
        assert isinstance(step.request_time_ms, float)
        assert step.request_time_ms >= 0.0
        assert step.model_name == "test-model"
        assert step.api_url == "http://test"
        assert step.llm_output != ""
        assert step.sandbox_input != ""
        assert step.sandbox_output != ""
        assert step.retries == 0

    def test_llm_failure_stops_loop(self):
        llm = MagicMock()
        llm.current_model = "test-model"
        llm.complete.return_value = (None, 4)
        sandbox = MagicMock()
        result = _make_loop(llm, sandbox).run("t5", "mbpp", "task")
        assert not result.success
        assert "LLM API failed" in (result.error or "")

    def test_token_accumulation(self):
        llm = _make_llm_mock([
            "```python\nprint('step1')\n```\n<end_code>"
            "```python\nfinal_answer('sol')\n```\n<end_code>"])
        sandbox = MagicMock()
        sandbox.execute.side_effect = [
            SandboxResult(success=True, stdout="step1 output"),
            SandboxResult(success=True, stdout="", final_answer="sol")]
        result = _make_loop(llm, sandbox).run("t6", "mbpp", "task")
        assert result.total_input_tokens == 100
        assert result.total_output_tokens == 60
        assert result.total_requests == 2

    def test_system_prompt_in_output(self):
        llm = _make_llm_mock(["```python\nfinal_answer('x')\n```<end_code>"])
        sandbox = MagicMock()
        sandbox.execute.return_value = SandboxResult(
            success=True, stdout="", final_answer="x")
        loop = AgentLoop(llm_manager=llm, sandbox_client=sandbox,
                         system_prompt="MY CUSTOM PROMPT", max_iterations=5,
                         max_input_tokens=10000, max_output_tokens=2000)
        result = loop.run("t7", "mbpp", "task")
        assert result.system_prompt == "MY CUSTOM PROMPT"


class TestLLMManager:
    def test_key_rotation_on_rate_limit(self):
        mgr = LLMManager("openrouter", "test-model", "heep://test",
                         ["key1", "key2"])
        call_count = [0]

        def mock_fn(req):
            call_count[0] += 1
            if call_count[0] == 1:
                raise RateLimitError("429")
            return LLMResponse(content="ok", input_tokens=5, output_tokens=5,
                               request_time_ms=10, model_name="test",
                               api_url="http://test")
        mgr._call_fn = mock_fn
        req = LLMRequest(model="test", messages=[Message(role="user",
                                                         content="hi")])
        resp, retries = mgr.complete(req)
        assert resp is not None
        assert retries == 1
        assert mgr._key_index == 1

    def test_from_env_loads_multiple_keys(self, monkeypatch):
        monkeypatch.setenv("TESTPROVIDER_API_KEY", "base-key")
        monkeypatch.setenv("TESTPROVIDER_API_KEY_1", "key-one")
        monkeypatch.setenv("TESTPROVIDER_API_KEY_2", "key-two")
        mgr = LLMManager.from_env("testprovider", "model", "http://test")
        assert len(mgr._keys) == 3
        assert "base-key" in mgr._keys

    def test_no_keys_raises(self, monkeypatch):
        monkeypatch.delenv("EMPTYP_API_KEY", raising=False)
        with pytest.raises(ValueError, match="No API keys"):
            LLMManager.from_env("emptyp", "model", "http://test")

    def test_request_not_mutated(self):
        mgr = LLMManager("openrouter", "m", "http://test", ["mykey"])
        captured = {}

        def mock_fn(req):
            captured["key"] = req.api_key
            return LLMResponse(content="ok", input_tokens=1, output_tokens=1,
                               request_time_ms=1, model_name="m",
                               api_url="http://test")
        mgr._call_fn = mock_fn
        original_req = LLMRequest(
            model="m", messages=[Message(role="user", content="hi")],
            api_key="")
        mgr.complete(original_req)
        assert captured["key"] == "mykey"
        assert original_req.api_key == ""


class TestSolutionOutput:
    def test_round_trip_json(self):
        sol = SolutionOutput(task_id="123", benchmark="mbpp", success=True,
                             solution="def foo(): return 1", iterations=2,
                             total_requests=2, total_input_tokens=100,
                             total_output_tokens=50, total_time_seconds=5.3)
        raw = sol.model_dump_json()
        restored = SolutionOutput.model_validate_json(raw)
        assert restored.task_id == "123"
        assert restored.success is True
        assert restored.benchmark == "mbpp"

    def test_steps_populated(self):
        step = StepMetrics(step=1, input_tokens=10, output_tokens=5,
                           request_time_ms=200.0,
                           llm_output="```python\nfinal_answer('x')\n```",
                           sandbox_input="final_answer('x')",
                           sandbox_output="submitted")
        sol = SolutionOutput(task_id="1", benchmark="mbpp", success=True,
                             solution="x", iterations=1, total_requests=1,
                             total_input_tokens=10, total_output_tokens=5,
                             total_time_seconds=1.0, steps=[step])
        raw = json.loads(sol.model_dump_json())
        assert len(raw["steps"]) == 1
        assert raw["steps"][0]["step"] == 1
        assert raw["steps"][0]["llm_output"] != ""

    def test_error_field_optional(self):
        sol = SolutionOutput(task_id="1", benchmark="swebench", success=False,
                             solution="", iterations=0, total_requests=0,
                             total_input_tokens=0, total_output_tokens=0,
                             total_time_seconds=0.0)
        assert sol.error is None
        data = json.loads(sol.model_dump_json())
        assert data["error"] is None


class TestMBPPTaskInput:
    def test_parse_from_json(self):
        raw = json.dumps({
            "task_id": "42", "task_definition": "Write a function that adds "
            "two numbers.", "function_definition": "def add(a, b):",
            "test_imports": [], "test_list": ["assert add(1, 2) == 3"]})
        task = MBPPTaskInput.model_validate_json(raw)
        assert task.task_id == "42"
        assert len(task.test_list) == 1

    def test_default(self):
        task = MBPPTaskInput(task_id="1", task_definition="desc",
                             function_definition="def f():")
        assert task.test_imports == []
        assert task.test_list == []


class TestSWEBenchTaskInput:
    def test_parse(self):
        raw = json.dumps({
            "instance_id": "sympy__sympy-12345",
            "problem_statement": "Fix the bug in...",
            "docker_image": "swebench/sweb.eval.x86_64.sympy:latest",
            "eval_script": "#!/bin/bash\npython -m pytest"
        })
        task = SWEBenchTaskInput.model_validate_json(raw)
        assert task.instance_id == "sympy__sympy-12345"
        assert task.hints_text == ""


class TestProviders:
    def test_successful_call(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "Hello back!"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            "model": "test-model"
        }
        with patch("agent.llm.providers.requests.post",
                   return_value=mock_resp):
            result = openai_compatible_call(_make_request())
        assert result.content == "Hello back!"
        assert result.input_tokens == 10
        assert result.output_tokens == 5

    def test_rate_limit_raises(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.text = "Rate limit exceeded"
        with patch("agent.llm.providers.requests.post",
                   return_value=mock_resp):
            with pytest.raises(RateLimitError):
                openai_compatible_call(_make_request())

    def test_server_error_raises_transient(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 503
        mock_resp.text = "Service unavailable"
        with patch("agent.llm.providers.requests.post",
                   return_value=mock_resp):
            with pytest.raises(TransientError):
                openai_compatible_call(_make_request())

    def test_stop_sequences_in_payload(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "ok"}}],
            "usage": {"prompt_tokens": 1, "completion_token": 1},
            "model": "m"}
        captured = {}

        def fake_post(url, json, headers, timeout):
            captured["payload"] = json
            return mock_resp
        with patch("agent.llm.providers.requests.post", side_effect=fake_post):
            openai_compatible_call(_make_request())
        assert "stop" in captured["payload"]
        assert "<end_code>" in captured["payload"]["stop"]

    def test_all_providers_in_registry(self):
        expected = {"openrouter", "groq", "gemini", "mistral", "together"}
        assert expected.issubset(set(PROVIDER_REGISTRY.keys()))
