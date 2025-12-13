from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol


@dataclass(frozen=True)
class LLMResponse:
    text: str
    model: str
    usage: dict


class LLMClient(Protocol):
    def generate(self, prompt: str, *, system: str = "", model: Optional[str] = None) -> LLMResponse:
        ...


class StubLLMClient:
    """
    Default fallback so tests keep passing even if no model is installed.
    """
    def __init__(self, model: str = "stub") -> None:
        self.model = model

    def generate(self, prompt: str, *, system: str = "", model: Optional[str] = None) -> LLMResponse:
        m = model or self.model
        return LLMResponse(text=f"[{m}] {prompt}", model=m, usage={})
