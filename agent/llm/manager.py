import logging
import os
import time
from typing import Optional
from models.llm import LLMRequest, LLMResponse
from agent.llm.providers import (PROVIDER_REGISTRY, RateLimitError,
                                 TransientError)

logger = logging.getLogger(__name__)

# Flat 60s backoff on all retries: avoids burning tokens on short sleeps
# that don't clear Mistral's per-minute rate-limit window.
_BACKOFF = [60, 60, 60, 60, 60]
# _BACKOFF = [1, 2, 4, 8, 60]
MAX_RETRIES = 5


class LLMManager:
    def __init__(self, provider_name: str, model: str, provider_url: str,
                 api_keys: list[str]) -> None:
        self.provider_name = provider_name
        self.current_model = model
        self.provider_url = provider_url
        self._keys = api_keys
        self._key_index = 0
        self._call_fn = PROVIDER_REGISTRY.get(provider_name,
                                              PROVIDER_REGISTRY["openrouter"])

        if not api_keys:
            raise ValueError(
                f"No API keys found for provider '{provider_name}'. "
                "Set them as environment variables, eg. OPENROUTER_API_KEY or "
                "OPENROUTER_API_KEY_1, OPENROUTER_API_KEY_2, ...")

    @classmethod
    def from_env(cls, provider: str, model: str, provider_url: str
                 ) -> "LLMManager":
        prefix = provider.upper().replace("-", "_") + "_API_KEY"
        keys: list[str] = []
        if val := os.getenv(prefix):
            keys.append(val)
        for i in range(1, 20):
            if val := os.getenv(f"{prefix}_{i}"):
                keys.append(val)
        logger.info("Provider '%s': found %d API key(s)", provider, len(keys))
        return cls(provider, model, provider_url, keys)

    def _current_key(self) -> str:
        return self._keys[self._key_index % len(self._keys)]

    def _rotate_key(self) -> None:
        self._key_index = (self._key_index + 1) % len(self._keys)

    def complete(self, request: LLMRequest
                 ) -> tuple[Optional[LLMResponse], int]:
        retries = 0
        last_error: Optional[Exception] = None
        for attempt in range(MAX_RETRIES + 1):
            call_request = request.model_copy(update={
                "api_key": self._current_key(),
                "provider_url": self.provider_url
            })
            try:
                response = self._call_fn(call_request)
                response.retries = retries
                return response, retries
            except RateLimitError as exc:
                logger.warning(
                    "Rate limit on key index %d (attempt %d/%d): %s",
                    self._key_index, attempt + 1, MAX_RETRIES, exc)
                self._rotate_key()
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
                logger.info("Sleeping %ds before retry %d", sleep, attempt + 2)
                time.sleep(sleep)
        logger.error("All %d retries exhausted. Last error: %s",
                     MAX_RETRIES + 1, last_error)
        return None, retries
