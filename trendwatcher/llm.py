"""Optional OpenRouter enrichment with a tiny file cache."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

import requests


DEFAULT_MODEL = "openai/gpt-5-nano"


class LLMClient:
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        cache_path: str | Path = "data/llm_cache.json",
    ) -> None:
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY", "")
        self.model = model or os.getenv("OPENROUTER_MODEL", DEFAULT_MODEL)
        self.cache_path = Path(cache_path)
        self.cache = self._load_cache()

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def _load_cache(self) -> dict[str, Any]:
        if not self.cache_path.exists():
            return {}
        try:
            return json.loads(self.cache_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

    def _save_cache(self) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(json.dumps(self.cache, ensure_ascii=False, indent=2), encoding="utf-8")

    def _key(self, task: str, payload: str) -> str:
        raw = f"{self.model}:{task}:{payload}".encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def enrich_signal(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Ask the model for compact JSON enrichment.

        If OpenRouter fails, return an empty dict and let deterministic fallbacks
        keep the prototype running.
        """

        compact_payload = json.dumps(payload, ensure_ascii=False, sort_keys=True)[:3500]
        cache_key = self._key("enrich_signal", compact_payload)
        if cache_key in self.cache:
            return self.cache[cache_key]
        if not self.enabled:
            return {}

        prompt = (
            "Ты аналитик финтех-публикаций для внутренней команды банка. "
            "Верни только JSON без markdown. Схема: "
            '{"summary":"2 предложения на русском","why_now":"1 короткое предложение",'
            '"category":"banking_product|payments|UX|partnership|regulation|market_signal|fraud_risk|other",'
            '"tags":["..."],"impact":1,"novelty":1,"urgency":1,"confidence":1,'
            '"suggested_action":"короткое действие для команды банка"}. '
            "Не выдумывай факты и ссылки. Данные сигнала: "
            f"{compact_payload}"
        )

        try:
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "http://localhost:8501",
                    "X-Title": "Fintech TrendWatcher MVP",
                },
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                    "max_tokens": 450,
                    "response_format": {"type": "json_object"},
                },
                timeout=30,
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            parsed = json.loads(content)
        except Exception:
            return {}

        self.cache[cache_key] = parsed
        self._save_cache()
        return parsed
