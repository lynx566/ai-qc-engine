from __future__ import annotations

import logging
from collections.abc import Iterator
from time import perf_counter
from typing import Any

from llm.providers.base import LLMRawResult
from llm.providers.capabilities import (
    BAILIAN_QWEN_CAPABILITIES,
    JSON_OBJECT_RESPONSE_FORMAT,
    ProviderCapabilities,
)
from llm.providers.config import ProviderConfig
from llm.providers.openai_client import build_openai_client

_DEFAULT_TIMEOUT_S = 300.0

logger = logging.getLogger(__name__)


class BailianQwenProvider:
    capabilities: ProviderCapabilities = BAILIAN_QWEN_CAPABILITIES

    @staticmethod
    def is_transient_request_error(error: Exception) -> bool:
        """Classify SDK transport/status failures; never inspect error text."""
        from openai import (
            APIConnectionError,
            APIStatusError,
            APITimeoutError,
            RateLimitError,
        )

        return isinstance(error, (APITimeoutError, APIConnectionError, RateLimitError)) or (
            isinstance(error, APIStatusError)
            and (error.status_code == 429 or 500 <= error.status_code < 600)
        )

    def __init__(self, config: ProviderConfig) -> None:
        self._config = config
        self._client = build_openai_client(
            api_key=config.api_key,
            base_url=config.base_url,
            timeout=_DEFAULT_TIMEOUT_S,
            max_retries=0,
        )

    def generate(self, messages: list[dict[str, str]]) -> LLMRawResult:
        request_kwargs: dict = {
            "model": self._config.model,
            "messages": messages,
            "stream": False,
        }
        if self._config.thinking is True:
            request_kwargs["extra_body"] = {"enable_thinking": True}
        elif self._config.thinking is False:
            request_kwargs["extra_body"] = {"enable_thinking": False}
        if self._config.seed is not None:
            request_kwargs["seed"] = self._config.seed

        caps = self.capabilities
        json_object_applied = False
        if (
            self._config.response_format == "json_object"
            and caps.supports_json_object_response_format
        ):
            request_kwargs["response_format"] = JSON_OBJECT_RESPONSE_FORMAT
            json_object_applied = True

        model = self._config.model
        logger.info("bailian generate started model=%s", model)
        started = perf_counter()
        try:
            stream = self._client.chat.completions.create(**request_kwargs)
            raw_text, request_id, api_version, finish_reason, raw_usage = (
                self._consume_completion_stream(stream)
            )
        except Exception as error:
            elapsed_ms = round((perf_counter() - started) * 1000)
            logger.warning(
                "bailian generate failed model=%s elapsed_ms=%s error_type=%s",
                model,
                elapsed_ms,
                type(error).__name__,
            )
            raise
        elapsed_ms = round((perf_counter() - started) * 1000)
        logger.info(
            "bailian generate finished model=%s elapsed_ms=%s finish_reason=%s",
            model,
            elapsed_ms,
            finish_reason,
        )

        usage: dict | None = None
        if raw_usage is not None:
            usage = {
                "prompt_tokens": getattr(raw_usage, "prompt_tokens", None),
                "completion_tokens": getattr(raw_usage, "completion_tokens", None),
                "total_tokens": getattr(raw_usage, "total_tokens", None),
            }

        return LLMRawResult(
            provider_name=self._config.provider_name,
            model=self._config.model,
            raw_text=raw_text,
            usage=usage,
            request_id=request_id,
            api_version=api_version,
            finish_reason=finish_reason,
            capabilities={
                "json_object_response_format": (
                    caps.supports_json_object_response_format
                ),
                **(
                    {"enable_thinking": self._config.thinking}
                    if self._config.thinking is not None
                    else {}
                ),
            },
            response_format_applied=json_object_applied,
            model_alias=self._config.model_alias,
            thinking=self._config.thinking,
        )

    def _consume_completion_stream(
        self,
        stream: Any,
    ) -> tuple[str, str | None, str | None, str | None, Any]:
        if not isinstance(stream, Iterator):
            return self._consume_non_streaming_response(stream)

        content_parts: list[str] = []
        request_id: str | None = None
        api_version: str | None = None
        finish_reason: str | None = None
        raw_usage = None

        for chunk in stream:
            if request_id is None:
                request_id = getattr(chunk, "id", None) or None
            chunk_fingerprint = getattr(chunk, "system_fingerprint", None)
            if chunk_fingerprint is not None:
                api_version = chunk_fingerprint

            chunk_usage = getattr(chunk, "usage", None)
            if chunk_usage is not None:
                raw_usage = chunk_usage

            choices = getattr(chunk, "choices", None)
            if not choices:
                continue

            choice = choices[0]
            delta = choice.delta
            delta_content = getattr(delta, "content", None)
            if delta_content:
                content_parts.append(delta_content)

            chunk_finish_reason = getattr(choice, "finish_reason", None)
            if chunk_finish_reason is not None:
                finish_reason = chunk_finish_reason

        return "".join(content_parts), request_id, api_version, finish_reason, raw_usage

    def _consume_non_streaming_response(
        self,
        response: Any,
    ) -> tuple[str, str | None, str | None, str | None, Any]:
        choice = response.choices[0]
        raw_text = choice.message.content or ""
        return (
            raw_text,
            getattr(response, "id", None) or None,
            getattr(response, "system_fingerprint", None),
            getattr(choice, "finish_reason", None),
            getattr(response, "usage", None),
        )
