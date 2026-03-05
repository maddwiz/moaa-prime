from __future__ import annotations

import os

from moaa_prime.llm.client import LLMClient, StubLLMClient

try:
    from moaa_prime.llm.ollama_client import OllamaClient
except Exception:  # pragma: no cover
    OllamaClient = None  # type: ignore


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return float(default)
    try:
        return float(raw)
    except (TypeError, ValueError):
        return float(default)


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return int(default)
    try:
        return int(raw)
    except (TypeError, ValueError):
        return int(default)


def make_llm_from_env() -> LLMClient:
    """
    Default behavior (no env set): StubLLMClient (keeps tests passing).

    Env:
      MOAA_LLM_PROVIDER=stub|ollama
      MOAA_OLLAMA_HOST=http://127.0.0.1:11434
      MOAA_OLLAMA_MODEL=llama3.1:8b-instruct
      MOAA_OLLAMA_TIMEOUT_SEC=30
      MOAA_OLLAMA_MAX_RETRIES=2
      MOAA_OLLAMA_RETRY_BACKOFF_SEC=0.25
    """
    provider = (os.getenv("MOAA_LLM_PROVIDER") or "stub").strip().lower()

    if provider == "ollama":
        if OllamaClient is None:
            return StubLLMClient(model="stub")
        host = os.getenv("MOAA_OLLAMA_HOST") or "http://127.0.0.1:11434"
        model = os.getenv("MOAA_OLLAMA_MODEL") or "llama3.1:8b-instruct"
        timeout_sec = _env_float("MOAA_OLLAMA_TIMEOUT_SEC", 30.0)
        max_retries = _env_int("MOAA_OLLAMA_MAX_RETRIES", 2)
        retry_backoff_sec = _env_float("MOAA_OLLAMA_RETRY_BACKOFF_SEC", 0.25)
        return OllamaClient(
            host=host,
            default_model=model,
            request_timeout_sec=max(1.0, float(timeout_sec)),
            max_retries=max(0, int(max_retries)),
            retry_backoff_sec=max(0.0, float(retry_backoff_sec)),
        )

    return StubLLMClient(model="stub")
