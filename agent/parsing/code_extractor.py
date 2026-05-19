import json
import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)


class CodeExtractor:
    _PY_FENCE = re.compile(r"```python\s*\n(.*?)```(?:\s*<end_code>)?",
                           re.DOTALL | re.IGNORECASE)
    _GENERIC_FENCE = re.compile(r"```\s*\n(.*?)```", re.DOTALL)
    # anthropic XML tool call
    _XML_INVOKE = re.compile(r"<invoke\s+name=[\"'](?P<name>[^\"']+)[\"']>"
                             r"(?P<body>.*?)</invoke>", re.DOTALL)
    _XML_PARAM = re.compile(
        r"<parameter\s+name=[\"'](?P<pname>[^\"']+)[\"']>"
        r"(?P<pval>.*?)</parameter>", re.DOTALL)
    _JSON_TOOL = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>",
                            re.DOTALL)
    _REACT_ACTION = re.compile(
        r"Action:\s*(?P<tool>\w+)\s*\nAction\s+Input:\s*(?P<args>\{.*?\})",
        re.DOTALL)

    def _try_python_fence(self, text: str) -> Optional[str]:
        match = self._PY_FENCE.search(text)
        if match:
            return match.group(1)
        return None

    def _try_generic_fence(self, text: str) -> tuple[Optional[str], str]:
        match = self._GENERIC_FENCE.search(text)
        if not match:
            return None, ""
        content = match.group(1)
        if any(kw in content for kw in ("def", "import", "print(", "result =",
                                        "=")):
            return content, ("Found a code block without a language tag - "
                             "interpreted as Python")
        return None, ""

    def _try_xml_invoke(self, text: str) -> Optional[str]:
        """
        Convert:
          <invoke name="read_file">
            <parameter name="filepath">/testbed/foo.py</parameter>
          </invoke>
        Into:
          result = read_file(filepath="/testbed/foo.py")
          print(result)
        """
        invoke_match = self._XML_INVOKE.search(text)
        if not invoke_match:
            return None
        tool_name = invoke_match.group("name")
        body = invoke_match.group("body")
        kwargs = {}
        for param in self._XML_PARAM.finditer(body):
            kwargs[param.group("pname")] = param.group("pval").strip()
        args_str = ", ".join(f'{k}={json.dumps(v)}' for k, v in kwargs.items())
        return f"result = {tool_name}({args_str})\nprint(result)"

    def _try_json_tool(self, text: str) -> Optional[str]:
        """
        Convert:
          <tool_call>{"name": "read_file", "arguments":
          {"filepath": "/testbed/foo.py"}}</tool_call>
        Into:
          result = read_file(filepath="/testbed/foo.py")
          print(result)
        """
        match = self._JSON_TOOL.search(text)
        if not match:
            return None
        try:
            data = json.loads(match.group(1))
        except json.JSONDecodeError as exc:
            logger.debug("JSON tool call parse failed: %s", exc)
            return None
        tool_name = data.get("name") or data.get("tool")
        arguments = data.get("arguments") or data.get("parameters") or {}
        if not tool_name:
            return None
        args_str = ", ".join(f'{k}={json.dumps(v)}'
                             for k, v in arguments.items())
        return f"result = {tool_name}({args_str})\nprint(result)"

    def _try_react(self, text: str) -> Optional[str]:
        """
        Convert:
          Action: read_file
          Action Input: {"filepath": "/testbed/foo.py"}
        Into:
          result = read_file(filepath="/testbed/foo.py")
          print(result)
        """
        match = self._REACT_ACTION.search(text)
        if not match:
            return None
        tool_name = match.group("tool")
        args_str_raw = match.group("args")
        try:
            args = json.loads(args_str_raw)
        except json.JSONDecodeError:
            return (f"result = {tool_name}({json.dumps(args_str_raw)})\n"
                    "print(result)")
        kwargs_str = ", ".join(f'{k}={json.dumps(v)}' for k, v in args.items())
        return f"result = {tool_name}({kwargs_str})\nprint(result)"

    def extract(self, text: str) -> tuple[Optional[str], str]:
        code = self._try_python_fence(text)
        if code:
            return code.strip(), ""
        code, note = self._try_generic_fence(text)
        if code:
            return code.strip(), note
        code = self._try_xml_invoke(text)
        if code:
            return code.strip(), "Converted Anthropic XML tool call to Python."
        code = self._try_json_tool(text)
        if code:
            return code.strip(), "Converted JSON tool call to Python"
        code = self._try_react(text)
        if code:
            return (code.strip(),
                    "Converted ReAct Action/Action Input to Python")
        return None, ""
