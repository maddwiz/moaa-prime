from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass
from typing import Optional

from moaa_prime.llm.client import LLMResponse


@dataclass
class OllamaClient:
    host: str = "http://127.0.0.1:11434"
    default_model: str = "llama3.1:8b-instruct"

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
        with urllib.request.urlopen(req, timeout=120) as r:
            data = json.loads(r.read().decode("utf-8"))
        return LLMResponse(
            text=data.get("response", "").strip(),
            model=m,
            usage={"eval_count": data.get("eval_count"), "prompt_eval_count": data.get("prompt_eval_count")},
        )
