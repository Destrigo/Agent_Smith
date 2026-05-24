from typing import Literal

from pydantic import BaseModel


class Message(BaseModel):
    """A single message in the LLM conversation history."""

    role: Literal["system", "user", "assistant"]
    content: str
