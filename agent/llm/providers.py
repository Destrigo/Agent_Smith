import time
from typing import Any
import requests
from collections.abc import Callable
from models.llm import LLMRequest, LLMResponse


class RateLimitError(Exception):
    """HTTP 429 or quota exhausted."""


class TransientError(Exception):
    """5xx or connection timeout — worth retrying."""


def _post(url: str, payload: dict[str, Any], api_key: str,
          headers: dict[str, str] | None = None) -> tuple[dict[str, Any], float]:
    t0 = time.monotonic()
    base_headers = {"Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"}
    if headers:
        base_headers.update(headers)
    resp = requests.post(url, json=payload, headers=base_headers, timeout=60)
    elapsed_ms = (time.monotonic() - t0) * 1000
    if resp.status_code == 429:
        raise RateLimitError(f"429 from {url}: {resp.text[:200]}")
    if resp.status_code >= 500:
        raise TransientError(f"{resp.status_code} from {url}: "
                             f"{resp.text[:200]}")
    resp.raise_for_status()
    return resp.json(), elapsed_ms


def _parse_response(data: dict[str, Any], elapsed_ms: float, api_url: str
                    ) -> LLMResponse:
    raw_content = data.get("choices", [{}])[0].get("message", {}).get(
        "content", "")
    # some providers return content as a list of blocks — flatten to string
    if isinstance(raw_content, list):
        choice = "".join(
            block.get("text", "") for block in raw_content
            if isinstance(block, dict) and block.get("type") == "text"
        )
    else:
        choice = raw_content or ""
    usage = data.get("usage", {})
    return LLMResponse(
        content=choice, input_tokens=usage.get("prompt_tokens", 0),
        output_tokens=usage.get("completion_tokens", 0),
        request_time_ms=elapsed_ms, model_name=data.get("model", ""),
        api_url=api_url, raw=data)


def openai_compatible_call(request: LLMRequest,
                           headers: dict[str, str] | None = None
                           ) -> LLMResponse:
    url = request.provider_url.rstrip("/") + "/chat/completions"
    payload: dict[str, Any] = {
        "model": request.model,
        "messages": [m.model_dump(exclude_none=True)
                     for m in request.messages],
        "max_tokens": request.max_tokens,
        "temperature": request.temperature}
    if request.stop_sequences:
        payload["stop"] = request.stop_sequences
    payload.update(request.extra)
    data, elapsed_ms = _post(url, payload, request.api_key, headers)
    return _parse_response(data, elapsed_ms, request.provider_url)


def _openrouter(request: LLMRequest) -> LLMResponse:
    return openai_compatible_call(
        request, headers={"HTTP-Referer": "https://agent-smith.42.fr"})


def _gemini(request: LLMRequest) -> LLMResponse:
    # Gemini via OpenAI-compat endpoint (requires GEMINI_API_KEY).
    # Use: AGENT_PROVIDER_URL=https://generativelanguage.googleapis.com/v1beta/openai
    return openai_compatible_call(request)


def _generic(request: LLMRequest) -> LLMResponse:
    return openai_compatible_call(request)


PROVIDER_REGISTRY: dict[str, Callable[[LLMRequest], LLMResponse]] = {
    "openrouter": _openrouter,
    "mistral":    _generic,
    "groq":       _generic,
    "gemini":     _gemini,
    "together":   _generic,
    "deepseek":   _generic,
}
