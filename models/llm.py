from typing import Any, Literal
from pydantic import BaseModel, Field


class Message(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class LLMRequest(BaseModel):
    """A normalised request sent to any provider."""
    model: str
    messages: list[Message]
    max_tokens: int = 1024
    temperature: float = 0.0
    stop_sequences: list[str] = Field(default_factory=lambda: [
        "<end_code>", "Observation:"],
        description="Stop the model BEFORE it hallucinates execution output")
    provider_url: str = ""
    api_key: str = ""
    extra: dict[str, Any] = Field(default_factory=dict)


class LLMResponse(BaseModel):
    """Normalised response from any provider."""
    content: str
    input_tokens: int = 0
    output_tokens: int = 0
    request_time_ms: float = 0.0
    model_name: str = ""
    api_url: str = ""
    retries: int = 0
    finish_reason: str = ""
    raw: dict[str, Any] = Field(default_factory=dict)
