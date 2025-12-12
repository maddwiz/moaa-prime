from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict

from moaa_prime.contracts import Contract


@dataclass
class AgentResult:
    agent_name: str
    text: str
    meta: Dict[str, Any] | None = None


class BaseAgent(ABC):
    def __init__(self, contract: Contract):
        self.contract = contract

    @property
    def name(self) -> str:
        return self.contract.name

    @abstractmethod
    def handle(self, prompt: str) -> AgentResult:
        """
        Phase 2: return a stub response.
        Later: call LLM + tools + MRE memory.
        """
        raise NotImplementedError
