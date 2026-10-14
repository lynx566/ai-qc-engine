"""Installed runtime dependency materialization for Filter-output projection."""

from __future__ import annotations

from llm.execution_configs import materialize_llm_provider, resolve_llm_execution_config
from operations.filter_output_projection.runtime_dependencies import (
    FilterOutputProjectionRuntimeDependencies,
)
from plugins.clinical_trial_doc.filter_output_projection.overview.dependencies import (
    OVERVIEW_SEMANTIC_LLM_SLOT,
)

from application.document_consistency_qc.composition import (
    DocumentConsistencyQcApplicationComposition,
)


def materialize_installed_projection_runtime_dependencies(
    *,
    composition: DocumentConsistencyQcApplicationComposition,
) -> FilterOutputProjectionRuntimeDependencies:
    """Build projection runtime dependencies from installed LLM dependency bindings."""

    bindings = composition.llm_dependency_bindings
    try:
        config_id = bindings[OVERVIEW_SEMANTIC_LLM_SLOT]
    except KeyError as exc:
        raise ValueError(
            "missing installed LLM dependency binding for slot "
            f"{OVERVIEW_SEMANTIC_LLM_SLOT!r}"
        ) from exc
    config = resolve_llm_execution_config(config_id)
    provider = materialize_llm_provider(config)
    return FilterOutputProjectionRuntimeDependencies(
        llm_provider=provider,
        llm_execution_config=config.to_provenance_record(),
    )


__all__ = ["materialize_installed_projection_runtime_dependencies"]
