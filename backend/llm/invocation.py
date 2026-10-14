"""Shared per-attempt telemetry and explicit provider transport retry."""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from time import perf_counter
from typing import Any, Literal

from llm.model_registry import resolve_llm_profile
from llm.providers.base import LLMProvider, LLMRawResult
from llm.providers.pricing import estimate_llm_cost

_EXCEPTION_INVOCATIONS_ATTRIBUTE = "_llm_invocations"
logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class LLMInvocationRecord:
    """Serializable outcome of exactly one provider.generate call."""

    provider: str | None
    model: str | None
    config_id: str | None
    profile_id: str | None
    status: Literal["success", "failed"]
    elapsed_ms: int
    request_id: str | None
    usage: dict[str, Any] | None
    error_type: str | None
    error_message: str | None
    attempt_index: int
    model_alias: str | None = None
    api_version: str | None = None
    finish_reason: str | None = None
    capabilities: dict[str, Any] | None = None
    response_format: str | None = None
    response_format_applied: bool = False
    thinking: bool | None = None
    cost_estimate: dict[str, Any] | None = None
    estimated_cost: float | None = None

    def __post_init__(self) -> None:
        if self.attempt_index < 1:
            raise ValueError("attempt_index must be >= 1")
        if self.elapsed_ms < 0:
            raise ValueError("elapsed_ms must be >= 0")

    def to_dict(self) -> dict[str, Any]:
        """Return the canonical JSON-ready invocation representation."""

        payload: dict[str, Any] = {
            "provider": self.provider,
            "model": self.model,
            "config_id": self.config_id,
            "profile_id": self.profile_id,
            "status": self.status,
            "elapsed_ms": self.elapsed_ms,
            "request_id": self.request_id,
            "usage": dict(self.usage) if self.usage is not None else None,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "attempt_index": self.attempt_index,
            "response_format_applied": self.response_format_applied,
        }
        optional = {
            "model_alias": self.model_alias,
            "api_version": self.api_version,
            "finish_reason": self.finish_reason,
            "capabilities": (
                dict(self.capabilities) if self.capabilities is not None else None
            ),
            "response_format": self.response_format,
            "thinking": self.thinking,
            "cost_estimate": (
                dict(self.cost_estimate) if self.cost_estimate is not None else None
            ),
            "estimated_cost": self.estimated_cost,
        }
        payload.update({key: value for key, value in optional.items() if value is not None})
        return payload


@dataclass(frozen=True, slots=True)
class LLMInvocationOutcome:
    """Raw provider result or original exception, paired with telemetry."""

    raw_result: LLMRawResult | None
    invocation: LLMInvocationRecord
    error: Exception | None = None
    history: tuple[LLMInvocationRecord, ...] = ()

    @property
    def invocations(self) -> tuple[LLMInvocationRecord, ...]:
        """All actual attempts in order; invocation remains the final attempt."""
        return self.history or (self.invocation,)

    def unwrap(self) -> LLMRawResult:
        """Return the raw result or re-raise the original provider exception."""

        if self.error is not None:
            raise self.error
        if self.raw_result is None:  # pragma: no cover - constructor invariant guard.
            raise RuntimeError("successful invocation outcome missing raw_result")
        return self.raw_result


def serialize_llm_invocations(
    invocations: Sequence[LLMInvocationRecord],
) -> list[dict[str, Any]]:
    return [invocation.to_dict() for invocation in invocations]


def attach_llm_invocations(
    error: Exception,
    invocations: Sequence[LLMInvocationRecord],
) -> None:
    """Attach telemetry to an exception without changing its type or traceback."""

    setattr(error, _EXCEPTION_INVOCATIONS_ATTRIBUTE, tuple(invocations))


def llm_invocations_from_exception(
    error: BaseException,
) -> tuple[LLMInvocationRecord, ...]:
    value = getattr(error, _EXCEPTION_INVOCATIONS_ATTRIBUTE, ())
    if not isinstance(value, tuple):
        return ()
    return tuple(item for item in value if isinstance(item, LLMInvocationRecord))


def _execution_identity(
    execution_config: Mapping[str, Any] | None,
) -> tuple[str | None, str | None, str | None, str | None, bool | None]:
    if execution_config is None:
        return None, None, None, None, None
    config_id = str(execution_config.get("config_id") or "").strip() or None
    profile_id = str(execution_config.get("profile_id") or "").strip() or None
    response_format = (
        str(execution_config.get("response_format") or "").strip() or None
    )
    thinking_raw = execution_config.get("thinking")
    thinking = bool(thinking_raw) if thinking_raw is not None else None
    if profile_id is None:
        return config_id, None, None, response_format, thinking
    try:
        _, profile = resolve_llm_profile(profile_id)
    except ValueError:
        return config_id, profile_id, None, response_format, thinking
    return config_id, profile_id, profile.provider, response_format, thinking


def invoke_llm(
    provider: LLMProvider,
    messages: list[dict[str, str]],
    *,
    execution_config: Mapping[str, Any] | None = None,
    attempt_index: int = 1,
) -> LLMInvocationOutcome:
    """Invoke with at most one explicit, provider-opted-in transport retry."""
    history: list[LLMInvocationRecord] = []
    for offset in range(2):
        outcome = _invoke_llm_once(
            provider, messages, execution_config=execution_config,
            attempt_index=attempt_index + offset,
        )
        history.append(outcome.invocation)
        if outcome.error is None:
            return replace(outcome, history=tuple(history))
        classifier = getattr(provider, "is_transient_request_error", None)
        transient = classifier is not None and classifier(outcome.error)
        retrying = transient and offset == 0
        if transient:
            record = outcome.invocation
            logger.warning(
                "LLM request provider=%s model=%s attempt=%s error_type=%s elapsed_ms=%s %s",
                record.provider, record.model,
                record.attempt_index, record.error_type, record.elapsed_ms,
                "retrying" if retrying else "exhausted",
            )
        if not retrying:
            attach_llm_invocations(outcome.error, history)
            return replace(outcome, history=tuple(history))
    raise AssertionError("unreachable")  # pragma: no cover


def _invoke_llm_once(
    provider: LLMProvider,
    messages: list[dict[str, str]],
    *,
    execution_config: Mapping[str, Any] | None = None,
    attempt_index: int = 1,
) -> LLMInvocationOutcome:
    """Time one provider call and return telemetry for either outcome."""

    if attempt_index < 1:
        raise ValueError("attempt_index must be >= 1")
    config_id, profile_id, configured_provider, response_format, configured_thinking = (
        _execution_identity(execution_config)
    )
    configured_model: str | None = None
    if profile_id is not None:
        try:
            _, profile = resolve_llm_profile(profile_id)
        except ValueError:
            pass
        else:
            configured_model = profile.model

    provider_config = getattr(provider, "_config", None)
    configured_provider = configured_provider or getattr(
        provider_config, "provider_name", None
    )
    configured_model = configured_model or getattr(provider_config, "model", None)

    started = perf_counter()
    try:
        raw_result = provider.generate(messages)
    except Exception as error:  # noqa: BLE001 - telemetry must cover provider failures.
        elapsed_ms = round((perf_counter() - started) * 1000)
        invocation = LLMInvocationRecord(
            provider=configured_provider,
            model=configured_model,
            config_id=config_id,
            profile_id=profile_id,
            status="failed",
            elapsed_ms=elapsed_ms,
            request_id=None,
            usage=None,
            error_type=type(error).__name__,
            error_message=str(error),
            attempt_index=attempt_index,
            model_alias=profile_id,
            response_format=response_format,
            thinking=configured_thinking,
        )
        attach_llm_invocations(error, (invocation,))
        return LLMInvocationOutcome(
            raw_result=None,
            invocation=invocation,
            error=error,
        )

    elapsed_ms = round((perf_counter() - started) * 1000)
    pricing = estimate_llm_cost(
        raw_result.provider_name,
        raw_result.model,
        raw_result.usage,
        model_alias=raw_result.model_alias,
    )
    invocation = LLMInvocationRecord(
        provider=raw_result.provider_name,
        model=raw_result.model,
        config_id=config_id,
        profile_id=profile_id,
        status="success",
        elapsed_ms=elapsed_ms,
        request_id=raw_result.request_id,
        usage=dict(raw_result.usage) if raw_result.usage is not None else None,
        error_type=None,
        error_message=None,
        attempt_index=attempt_index,
        model_alias=raw_result.model_alias,
        api_version=raw_result.api_version,
        finish_reason=raw_result.finish_reason,
        capabilities=(
            dict(raw_result.capabilities)
            if raw_result.capabilities is not None
            else None
        ),
        response_format=response_format,
        response_format_applied=bool(raw_result.response_format_applied),
        thinking=(
            raw_result.thinking
            if raw_result.thinking is not None
            else configured_thinking
        ),
        cost_estimate=(pricing["cost_estimate"] if pricing is not None else None),
        estimated_cost=(pricing["cost"] if pricing is not None else None),
    )
    return LLMInvocationOutcome(raw_result=raw_result, invocation=invocation)


__all__ = [
    "LLMInvocationOutcome",
    "LLMInvocationRecord",
    "attach_llm_invocations",
    "invoke_llm",
    "llm_invocations_from_exception",
    "serialize_llm_invocations",
]
