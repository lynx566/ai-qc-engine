"""Fail-closed guards blocking external LLM factory/execution during pytest."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from llm.providers.blocked_openai import (
    EXTERNAL_LLM_EXECUTION_DISABLED_MESSAGE,
    BlockedOpenAIClient,
)
from llm.providers.openai_client import EXTERNAL_LLM_DISABLED_ENV

EXTERNAL_LLM_FACTORY_DISABLED_MESSAGE = (
    "External LLM provider construction is disabled during tests. "
    "Inject mock/fake providers, mark with @pytest.mark.allow_external_provider_factory, "
    "or @pytest.mark.live_llm."
)

# Backward-compatible alias used by Slice A guard regressions.
EXTERNAL_LLM_DISABLED_MESSAGE = EXTERNAL_LLM_FACTORY_DISABLED_MESSAGE

_BUILD_API_PROVIDER_PATCH_TARGETS: tuple[str, ...] = (
    "llm.providers.factory.build_api_provider",
    (
        "runtime.evidence_source_preparation.clinical_trial_doc.clinical_safety."
        "aggregate_evidence.llm_execution_selection.build_api_provider"
    ),
    (
        "runtime.evidence_comparison.clinical_trial_doc.clinical_safety."
        "aggregate_evidence.comparison_finding_assessment.build_api_provider"
    ),
    (
        "runtime.evidence_comparison.clinical_trial_doc.clinical_safety."
        "aggregate_evidence.comparison_finding_verification.build_api_provider"
    ),
)

_MATERIALIZE_LLM_PROVIDER_PATCH_TARGETS: tuple[str, ...] = (
    "llm.execution_configs.materialize_llm_provider",
    "application.clinical_trial_doc_consistency_qc.execution.materialize_llm_provider",
    (
        "application.clinical_trial_doc_consistency_qc.projection_runtime."
        "materialize_llm_provider"
    ),
)


def _blocked_external_llm_factory_call(*_args: object, **_kwargs: object) -> object:
    raise RuntimeError(EXTERNAL_LLM_FACTORY_DISABLED_MESSAGE)


def install_external_llm_factory_guard(monkeypatch: Any) -> None:
    """Patch all known external LLM provider construction choke points."""

    for target in _BUILD_API_PROVIDER_PATCH_TARGETS:
        monkeypatch.setattr(target, _blocked_external_llm_factory_call)
    for target in _MATERIALIZE_LLM_PROVIDER_PATCH_TARGETS:
        monkeypatch.setattr(target, _blocked_external_llm_factory_call)


def install_external_llm_execution_guard(monkeypatch: Any) -> None:
    """Enable the production external-execution kill switch for in-process tests."""

    monkeypatch.setenv(EXTERNAL_LLM_DISABLED_ENV, "1")


def install_external_llm_fail_closed_guard(monkeypatch: Any) -> None:
    """Install both factory and execution fail-closed guards."""

    install_external_llm_factory_guard(monkeypatch)
    install_external_llm_execution_guard(monkeypatch)


def isolated_subprocess_env(
    *,
    backend_root: Path | None = None,
    disable_external_llm: bool = True,
    **updates: str,
) -> dict[str, str]:
    """Build subprocess env with provider-capable PYTHONPATH and fail-closed execution."""

    env = os.environ.copy()
    if backend_root is not None:
        env["PYTHONPATH"] = str(backend_root)
    if disable_external_llm:
        env[EXTERNAL_LLM_DISABLED_ENV] = "1"
    else:
        env.pop(EXTERNAL_LLM_DISABLED_ENV, None)
    env.update(updates)
    return env


def is_live_llm_opted_in(request: Any) -> bool:
    return request.node.get_closest_marker("live_llm") is not None


def is_allow_external_provider_factory_opted_in(request: Any) -> bool:
    return (
        request.node.get_closest_marker("allow_external_provider_factory") is not None
    )


__all__ = [
    "EXTERNAL_LLM_DISABLED_MESSAGE",
    "EXTERNAL_LLM_EXECUTION_DISABLED_MESSAGE",
    "EXTERNAL_LLM_FACTORY_DISABLED_MESSAGE",
    "BlockedOpenAIClient",
    "install_external_llm_execution_guard",
    "install_external_llm_factory_guard",
    "install_external_llm_fail_closed_guard",
    "is_allow_external_provider_factory_opted_in",
    "is_live_llm_opted_in",
    "isolated_subprocess_env",
]
