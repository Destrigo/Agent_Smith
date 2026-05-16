import logging
import os
import time
from typing import Optional
from models.llm import LLMRequest, LLMResponse

logger = logging.getLogger(__name__)

# how long to wait between retries (seconds): 1s, 2s, 4s, 8s
_BACKOFF = [1, 2, 4, 8]
MAX_RETRIES = 4


class RateLimitError(Exception):
    """HTTP 429 or quota exhausted."""


class TransientError(Exception):
    """5xx or connection timeout — worth retrying."""


class LLMManager:
    def __init__(self, provider_name: str, model: str, provider_url: str,
                 api_keys: list[str]) -> None:
        self.provider_name = provider_name
        self.current_model = model
        self.provider_url = provider_url
        self._keys = api_keys
        self._key_index = 0

        if not api_keys:
            raise ValueError(
                f"No API keys found for provider '{provider_name}'."
                "Set them as environment variables, eg. OPENROUTER_API_KEY or"
                "OPENROUTER_API_KEY_1, OPENROUTER_API_KEY_2, ...")

        @classmethod
        def from_env(cls, provider: str, model: str, provider_url: str
                     ) -> LLMManager:
            prefix = provider.upper().replace("-", "_") + "_API_KEY"
            keys: list[str] = []
            if val := os.getenv(prefix):
                keys.append(val)
            for i in range(1, 20):
                if val := os.getenv(f"{prefix}_{i}"):
                    keys.append(val)
            logger.info("Provider '%s': found %d API key(s)",
                        provider, len(keys))
            return cls(provider, model, provider_url, keys)

        def complete(self, request: LLMRequest
                     ) -> tuple[Optional[LLMResponse], int]:
            retries = 0
            last_error: Optional[Exception] = None
            for attempt in range(MAX_RETRIES + 1):
                key = self._next_key()
                request.api_key = key
                request.provider_url = self.provider_url
                try:
                    response = self._dispatch(request)
                    response.retries = retries
                    return response, retries
                except RateLimitError as exc:
                    logger.warning(
                        "Rate limit on key index %d (attempt %d/%d): %s",
                        self._key_index, attempt + 1, MAX_RETRIES, exc)
                    last_error = exc
                except TransientError as exc:
                    logger.warning(
                        "Transient error (attempt %d): %s", attempt + 1, exc)
                    last_error = exc
                except Exception as exc:
                    logger.error("Non-retryable error: %s", exc)
                    return None, retries
                retries += 1
                if attempt < MAX_RETRIES:
                    sleep = _BACKOFF[min(attempt, len(_BACKOFF) - 1)]
                    logger.info("Sleeping %ds before retry %d",
                                sleep, attempt + 2)
                    time.sleep(sleep)
            logger.error("All %d retries exhausted. Last error: %s",
                         MAX_RETRIES, last_error)
            return None, retries

        def _next_key(self) -> str:
            key = self._keys[self._key_index]
            self._key_index = (self._key_index + 1) % len(self._keys)
            return key

        def _dispatch(self, request: LLMRequest) -> LLMResponse:
            provider_map = {
                "openrouter": _openrouter_call,
                "groq": _groq_call,
                "gemini": _gemini_call,
                "mistral": _mistral_call,
                "cohere": _cohere_call,
                "together": _together_call,
            }
            fn = provider_map.get(self.provider_name, _openai_compatible_call)
            return fn(request)