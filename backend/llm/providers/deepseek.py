from __future__ import annotations

from llm.providers.base import (
    CACHE_USAGE_COMPATIBILITY_FALLBACK,
    CACHE_USAGE_PARTIALLY_DERIVED,
    CACHE_USAGE_PROVIDER_REPORTED,
    CACHE_USAGE_UNAVAILABLE,
    LLMRawResult,
    prompt_cache_usage_closure,
)
from llm.providers.capabilities import (
    DEEPSEEK_CAPABILITIES,
    JSON_OBJECT_RESPONSE_FORMAT,
    ProviderCapabilities,
)
from llm.providers.config import ProviderConfig
from llm.providers.openai_client import build_openai_client

_DEFAULT_TIMEOUT_S = 120.0


def _value(value: object, field: str) -> object | None:
    if isinstance(value, dict):
        return value.get(field)
    return getattr(value, field, None)


def _optional_nonnegative_int(value: object | None) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result >= 0 else None


def _normalize_deepseek_usage(raw_usage: object) -> dict:
    """Normalize DeepSeek's official cache fields with an explicit fallback."""
    prompt_tokens = _optional_nonnegative_int(_value(raw_usage, "prompt_tokens"))
    completion_tokens = _optional_nonnegative_int(
        _value(raw_usage, "completion_tokens")
    )
    total_tokens = _optional_nonnegative_int(_value(raw_usage, "total_tokens"))
    official_hit = _optional_nonnegative_int(
        _value(raw_usage, "prompt_cache_hit_tokens")
    )
    official_miss = _optional_nonnegative_int(
        _value(raw_usage, "prompt_cache_miss_tokens")
    )

    hit = official_hit
    miss = official_miss
    used_fallback = False
    derived = False
    if hit is None:
        details = _value(raw_usage, "prompt_tokens_details")
        fallback_hit = _optional_nonnegative_int(_value(details, "cached_tokens"))
        if fallback_hit is not None:
            hit = fallback_hit
            used_fallback = True

    if prompt_tokens is not None:
        if hit is not None and miss is None and hit <= prompt_tokens:
            miss = prompt_tokens - hit
            derived = True
        elif miss is not None and hit is None and miss <= prompt_tokens:
            hit = prompt_tokens - miss
            derived = True

    if used_fallback:
        source = CACHE_USAGE_COMPATIBILITY_FALLBACK
    elif derived:
        source = CACHE_USAGE_PARTIALLY_DERIVED
    elif official_hit is not None or official_miss is not None:
        source = CACHE_USAGE_PROVIDER_REPORTED
    else:
        source = CACHE_USAGE_UNAVAILABLE

    usage = {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
    }
    usage.update(
        prompt_cache_usage_closure(
            prompt_tokens=prompt_tokens,
            prompt_cache_hit_tokens=hit,
            prompt_cache_miss_tokens=miss,
            cache_usage_source=source,
        )
    )
    return usage


class DeepSeekProvider:
    capabilities: ProviderCapabilities = DEEPSEEK_CAPABILITIES

    def __init__(self, config: ProviderConfig) -> None:
        self._config = config
        self._client = build_openai_client(
            api_key=config.api_key,
            base_url=config.base_url,
            timeout=_DEFAULT_TIMEOUT_S,
        )

    def generate(self, messages: list[dict[str, str]]) -> LLMRawResult:
        request_kwargs: dict = {
            "model": self._config.model,
            "messages": messages,
            "stream": False,
        }
        if self._config.thinking:
            request_kwargs["reasoning_effort"] = "high"
            request_kwargs["extra_body"] = {"thinking": {"type": "enabled"}}
        else:
            request_kwargs["extra_body"] = {"thinking": {"type": "disabled"}}

        caps = self.capabilities
        json_object_applied = False
        if (
            self._config.response_format == "json_object"
            and caps.supports_json_object_response_format
        ):
            request_kwargs["response_format"] = JSON_OBJECT_RESPONSE_FORMAT
            json_object_applied = True

        if getattr(self._config, "max_tokens", None) is not None:
            request_kwargs["max_tokens"] = self._config.max_tokens

        response = self._client.chat.completions.create(**request_kwargs)

        choice = response.choices[0]
        raw_text = choice.message.content or ""

        raw_usage = response.usage
        usage: dict | None = None
        if raw_usage is not None:
            usage = _normalize_deepseek_usage(raw_usage)

        return LLMRawResult(
            provider_name=self._config.provider_name,
            model=self._config.model,
            raw_text=raw_text,
            usage=usage,
            request_id=response.id or None,
            api_version=getattr(response, "system_fingerprint", None),
            finish_reason=choice.finish_reason,
            capabilities={
                "json_object_response_format": (
                    caps.supports_json_object_response_format
                ),
                "thinking_mode": self._config.thinking,
            },
            response_format_applied=json_object_applied,
            model_alias=self._config.model_alias,
            thinking=self._config.thinking,
        )
