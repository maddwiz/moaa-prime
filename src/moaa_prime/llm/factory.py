from __future__ import annotations

import os
from typing import Optional

from moaa_prime.llm.client import LLMClient, StubLLMClient

try:
    from moaa_prime.llm.ollama_client import OllamaClient
except Exception:  # pragma: no cover
    OllamaClient = None  # type: ignore


def make_llm_from_env() -> LLMClient:
    """
    Default behavior (no env set): StubLLMClient (keeps tests passing).

    Env:
      MOAA_LLM_PROVIDER=stub|ollama
      MOAA_OLLAMA_HOST=http://127.0.0.1:11434
      MOAA_OLLAMA_MODEL=llama3.1:8b-instruct
    """
    provider = (os.getenv("MOAA_LLM_PROVIDER") or "stub").strip().lower()

    if provider == "ollama":
        if OllamaClient is None:
            return StubLLMClient(model="stub")
        host = os.getenv("MOAA_OLLAMA_HOST") or "http://127.0.0.1:11434"
        model = os.getenv("MOAA_OLLAMA_MODEL") or "llama3.1:8b-instruct"
        return OllamaClient(host=host, default_model=model)

    return StubLLMClient(model="stub")
