"""Chat LLM provider for any OpenAI-compatible `/chat/completions` endpoint.

Verified against DeepSeek V4 (`deepseek-v4-flash`, `deepseek-v4-pro`). The same
class drives OpenAI, Together, vLLM and Ollama by changing ``base_url``.

DeepSeek V4 ships with thinking mode enabled by default, which is wrong for
benchmarking: it inflates latency, cost and output variance. RAGArena disables
it explicitly via ``extra_body["thinking"]`` unless ``thinking=True``.
"""

from __future__ import annotations

from typing import Any

from ..cache import ResponseCache
from ..errors import ProviderError
from .base import HTTPProviderBase, LLMResponse


class OpenAICompatLLM(HTTPProviderBase):
    name = "llm"

    def __init__(
        self,
        *,
        base_url: str = "https://api.deepseek.com",
        api_key: str,
        model: str = "deepseek-v4-flash",
        timeout_s: float = 180.0,
        max_retries: int = 4,
        retry_base_delay_s: float = 1.5,
        cache: ResponseCache | None = None,
        thinking: bool = False,
        supports_json_mode: bool = True,
        rpm: int = 0,
    ) -> None:
        super().__init__(
            base_url=base_url,
            api_key=api_key,
            timeout_s=timeout_s,
            max_retries=max_retries,
            retry_base_delay_s=retry_base_delay_s,
            cache=cache,
            rpm=rpm,
        )
        self.model = model
        self.thinking = thinking
        self.supports_json_mode = supports_json_mode
        self.name = f"llm:{model}"

    def _build_payload(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float,
        max_tokens: int | None,
        json_mode: bool,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"model": model, "messages": messages}
        if max_tokens:
            payload["max_tokens"] = max_tokens
        if json_mode and self.supports_json_mode:
            payload["response_format"] = {"type": "json_object"}

        if self._is_deepseek:
            payload["thinking"] = {"type": "enabled" if self.thinking else "disabled"}
            # Thinking mode ignores sampling params; sending them is harmless
            # but misleading, so only set temperature when it has an effect.
            if not self.thinking:
                payload["temperature"] = temperature
        else:
            payload["temperature"] = temperature
        return payload

    @property
    def _is_deepseek(self) -> bool:
        return "deepseek" in self.base_url or self.model.startswith("deepseek")

    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        json_mode: bool = False,
    ) -> LLMResponse:
        use_model = model or self.model
        payload = self._build_payload(
            messages,
            use_model,
            0.0 if temperature is None else temperature,
            max_tokens,
            json_mode,
        )

        cache_key = None
        if self.cache is not None:
            cache_key = ResponseCache.make_key("chat", use_model, payload)
            hit = self.cache.get(cache_key)
            if hit is not None:
                return LLMResponse(
                    text=hit["text"],
                    prompt_tokens=hit.get("prompt_tokens", 0),
                    completion_tokens=hit.get("completion_tokens", 0),
                    cached_prompt_tokens=hit.get("cached_prompt_tokens", 0),
                    model=use_model,
                    cached=True,
                )

        body = await self._post("/chat/completions", payload)
        result = self._parse(body, use_model)

        if self.cache is not None and cache_key is not None:
            self.cache.set(
                cache_key,
                "chat",
                use_model,
                {
                    "text": result.text,
                    "prompt_tokens": result.prompt_tokens,
                    "completion_tokens": result.completion_tokens,
                    "cached_prompt_tokens": result.cached_prompt_tokens,
                },
            )
        return result

    def _parse(self, body: dict[str, Any], model: str) -> LLMResponse:
        choices = body.get("choices") or []
        if not choices:
            raise ProviderError(self.name, f"no choices in response: {str(body)[:200]}")
        message = choices[0].get("message") or {}
        text = (message.get("content") or "").strip()
        if not text and message.get("reasoning_content"):
            # Thinking mode occasionally returns only CoT when it hits the
            # output cap. Surface it rather than silently returning "".
            text = str(message["reasoning_content"]).strip()

        usage = body.get("usage") or {}
        cached = int(
            usage.get("prompt_cache_hit_tokens")
            or (usage.get("prompt_tokens_details") or {}).get("cached_tokens")
            or 0
        )
        return LLMResponse(
            text=text,
            prompt_tokens=int(usage.get("prompt_tokens") or 0),
            completion_tokens=int(usage.get("completion_tokens") or 0),
            cached_prompt_tokens=cached,
            model=model,
            raw=body,
        )
