"""Neutral capability-slot binding topology validation for Application Composition."""

from __future__ import annotations

from collections.abc import Mapping

from execution_flow.document_consistency_qc import DocumentConsistencyQcCapabilityConfig
from operations.prepare_analysis.contracts import PrepareAnalysisConfigId
from operations.prepare_analysis.registry import (
    PrepareAnalysisConfigRegistry,
    UnknownPrepareAnalysisConfigError,
)


def _format_binding_key(key: tuple[str, str]) -> str:
    capability_id, slot_id = key
    return f"({capability_id!r}, {slot_id!r})"


def validate_capability_slot_bindings(
    *,
    capabilities: Mapping[str, DocumentConsistencyQcCapabilityConfig],
    extract_bindings: Mapping[tuple[str, str], str],
    prepare_analysis_bindings: Mapping[tuple[str, str], PrepareAnalysisConfigId],
    filter_job_bindings: Mapping[tuple[str, str], tuple[str, ...]],
    expected_document_type_bindings: Mapping[tuple[str, str], str],
) -> None:
    """Validate installed bindings against capability topology."""

    installed_capability_ids = set(capabilities)

    for binding_name, bindings in (
        ("extract", extract_bindings),
        ("prepare_analysis", prepare_analysis_bindings),
        ("filter_job", filter_job_bindings),
        ("expected_document_type", expected_document_type_bindings),
    ):
        for key in bindings:
            capability_id, slot_id = key
            if capability_id not in installed_capability_ids:
                raise ValueError(
                    f"{binding_name} binding references unknown capability_id: "
                    f"{capability_id!r}"
                )
            capability = capabilities[capability_id]
            installed_slot_ids = {slot.slot_id for slot in capability.slots}
            if slot_id not in installed_slot_ids:
                raise ValueError(
                    f"{binding_name} binding references unknown slot_id "
                    f"{slot_id!r} for capability {capability_id!r}"
                )

    for capability in capabilities.values():
        for slot in capability.slots:
            key = (capability.capability_id, slot.slot_id)
            if key not in extract_bindings:
                raise ValueError(
                    "missing Extract binding for capability slot "
                    + _format_binding_key(key)
                )
            if key not in prepare_analysis_bindings:
                raise ValueError(
                    "missing Prepare Analysis binding for capability slot "
                    + _format_binding_key(key)
                )
            if key not in filter_job_bindings:
                raise ValueError(
                    "missing Filter job binding for capability slot "
                    + _format_binding_key(key)
                )
            filter_jobs = filter_job_bindings[key]
            if not isinstance(filter_jobs, tuple):
                raise TypeError(
                    "filter_job_bindings values must be tuples for "
                    + _format_binding_key(key)
                )
            if key not in expected_document_type_bindings:
                raise ValueError(
                    "missing expected document-type binding for capability slot "
                    + _format_binding_key(key)
                )


def validate_filter_job_bindings_against_installed_filter_jobs(
    *,
    filter_job_bindings: Mapping[tuple[str, str], tuple[str, ...]],
    installed_filter_job_ids: frozenset[str] | set[str],
) -> None:
    """Reject capability Filter job bindings that reference uninstalled filter_job_ids."""

    installed_ids = frozenset(installed_filter_job_ids)
    for key, filter_job_ids in filter_job_bindings.items():
        if not isinstance(filter_job_ids, tuple):
            raise TypeError(
                "filter_job_bindings values must be tuples for "
                + _format_binding_key(key)
            )
        for filter_job_id in filter_job_ids:
            if filter_job_id not in installed_ids:
                raise ValueError(
                    "filter_job binding references unknown filter_job_id "
                    f"{filter_job_id!r} for capability slot " + _format_binding_key(key)
                )


def validate_prepare_analysis_bindings_against_installed_registry(
    *,
    prepare_analysis_bindings: Mapping[tuple[str, str], PrepareAnalysisConfigId],
    prepare_analysis_config_registry: PrepareAnalysisConfigRegistry,
) -> None:
    """Reject capability Prepare bindings that reference unregistered config IDs."""

    if not isinstance(prepare_analysis_config_registry, PrepareAnalysisConfigRegistry):
        raise TypeError(
            "prepare_analysis_config_registry must be a PrepareAnalysisConfigRegistry"
        )

    for key, config_id in prepare_analysis_bindings.items():
        try:
            prepare_analysis_config_registry.resolve(config_id)
        except UnknownPrepareAnalysisConfigError as exc:
            raise ValueError(
                "prepare_analysis binding references unknown "
                f"prepare_analysis_config_id {config_id!r} for capability slot "
                + _format_binding_key(key)
            ) from exc


def validate_candidate_scope_manual_default_filter_job_bindings(
    *,
    manual_default_filter_job_bindings: Mapping[tuple[str, str], str],
    filter_job_bindings: Mapping[tuple[str, str], tuple[str, ...]],
) -> None:
    """Reject manual Candidate Scope ownership policies outside installed filter jobs."""

    for key, manual_default_filter_job_id in manual_default_filter_job_bindings.items():
        if key not in filter_job_bindings:
            raise ValueError(
                "candidate_scope manual-default binding references unknown capability slot "
                + _format_binding_key(key)
            )
        installed_filter_job_ids = filter_job_bindings[key]
        if manual_default_filter_job_id not in installed_filter_job_ids:
            raise ValueError(
                "candidate_scope manual-default filter_job_id "
                f"{manual_default_filter_job_id!r} is not installed for capability slot "
                + _format_binding_key(key)
            )


__all__ = [
    "validate_candidate_scope_manual_default_filter_job_bindings",
    "validate_capability_slot_bindings",
    "validate_filter_job_bindings_against_installed_filter_jobs",
    "validate_prepare_analysis_bindings_against_installed_registry",
]
