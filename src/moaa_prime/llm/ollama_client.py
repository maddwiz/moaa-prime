from __future__ import annotations

import json
import time
import urllib.request
from urllib.error import URLError
from dataclasses import dataclass
from typing import Optional

from moaa_prime.llm.client import LLMResponse


@dataclass
class OllamaClient:
    host: str = "http://127.0.0.1:11434"
    default_model: str = "llama3.1:8b-instruct"
    request_timeout_sec: float = 30.0
    max_retries: int = 2
    retry_backoff_sec: float = 0.25

    def generate(self, prompt: str, *, system: str = "", model: Optional[str] = None) -> LLMResponse:
        m = model or self.default_model
        payload = {
            "model": m,
            "prompt": prompt if not system else f"System:\n{system}\n\nUser:\n{prompt}",
            "stream": False,
        }
        req = urllib.request.Request(
            f"{self.host}/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        timeout_sec = max(1.0, float(self.request_timeout_sec))
        retries = max(0, int(self.max_retries))
        backoff = max(0.0, float(self.retry_backoff_sec))

        last_error: Exception | None = None
        data: dict = {}
        for attempt in range(retries + 1):
            try:
                with urllib.request.urlopen(req, timeout=timeout_sec) as r:
                    data = json.loads(r.read().decode("utf-8"))
                break
            except (URLError, TimeoutError, OSError, ValueError) as exc:
                last_error = exc
                if attempt >= retries:
                    break
                if backoff > 0.0:
                    time.sleep(backoff * (2**attempt))

        if last_error is not None and not data:
            raise RuntimeError(
                f"ollama generate failed after {retries + 1} attempt(s): {last_error}"
            ) from last_error

        return LLMResponse(
            text=data.get("response", "").strip(),
            model=m,
            usage={"eval_count": data.get("eval_count"), "prompt_eval_count": data.get("prompt_eval_count")},
        )
