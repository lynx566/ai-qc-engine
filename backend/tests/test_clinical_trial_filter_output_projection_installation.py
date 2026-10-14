"""Application installation guards for Filter-output projection bindings."""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from types import MappingProxyType

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from application.clinical_trial_doc_consistency_qc import (
    INSTALLED_CLINICAL_TRIAL_DOC_FILTER_CONFIGS,
    INSTALLED_CLINICAL_TRIAL_DOC_FILTER_OUTPUT_PROJECTION_JOBS,
    build_clinical_trial_doc_consistency_qc_application_composition,
)
from application.clinical_trial_doc_consistency_qc.filter_installation import (
    INSTALLED_FILTER_PROFILES,
)
from application.clinical_trial_doc_consistency_qc.filter_output_projection_installation import (
    CLINICAL_SAFETY_SEMANTIC_MODULE_ID,
    validate_filter_output_projection_installation,
)
from operations.filter_output_projection.contracts import (
    ResolvedFilterOutputProjectionJob,
)
from operations.filter_output_projection.registry import (
    build_filter_output_projection_job_index,
    resolve_filter_output_projection_job,
)
from plugins.clinical_trial_doc.filter_output_projection import (
    DIRECT_FILTER_OUTPUT_PROJECTION_STRATEGY_ID,
    DIRECT_PROJECTION_SEMANTIC_MODULE_ID_CONFIG_KEY,
    OVERVIEW_SEMANTIC_DECOMPOSITION_FILTER_OUTPUT_PROJECTION_STRATEGY_ID,
)
from plugins.clinical_trial_doc.filter_profiles import (
    CSR_CLINICAL_SAFETY_FILTER_PROFILE_ZH,
    CSR_OVERVIEW_FILTER_PROFILE_ZH,
    DSUR_CLINICAL_SAFETY_FILTER_PROFILE_ZH,
    DSUR_OVERVIEW_FILTER_PROFILE_ZH,
    IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH,
    IB_OVERVIEW_FILTER_PROFILE_ZH,
)

INSTALLATION_PATH = (
    BACKEND_ROOT
    / "application"
    / "clinical_trial_doc_consistency_qc"
    / "filter_output_projection_installation.py"
)

CLINICAL_SAFETY_PROFILES = (
    IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH,
    DSUR_CLINICAL_SAFETY_FILTER_PROFILE_ZH,
    CSR_CLINICAL_SAFETY_FILTER_PROFILE_ZH,
)

OVERVIEW_PROFILES = (
    IB_OVERVIEW_FILTER_PROFILE_ZH,
    DSUR_OVERVIEW_FILTER_PROFILE_ZH,
    CSR_OVERVIEW_FILTER_PROFILE_ZH,
)


def test_filter_and_projection_installations_share_installed_profile_catalog() -> None:
    assert len(INSTALLED_FILTER_PROFILES) == 6
    assert frozenset(
        profile.filter_job_id for profile in INSTALLED_FILTER_PROFILES
    ) == frozenset(
        config.filter_job_id for config in INSTALLED_CLINICAL_TRIAL_DOC_FILTER_CONFIGS.values()
    )
    assert tuple(profile.filter_job_id for profile in INSTALLED_FILTER_PROFILES) == (
        "ib_clinical_safety",
        "ib_overview",
        "dsur_clinical_safety",
        "dsur_overview",
        "csr_clinical_safety",
        "csr_overview",
    )

    source = INSTALLATION_PATH.read_text(encoding="utf-8")
    for profile_name in (
        "IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH",
        "IB_OVERVIEW_FILTER_PROFILE_ZH",
        "DSUR_CLINICAL_SAFETY_FILTER_PROFILE_ZH",
        "DSUR_OVERVIEW_FILTER_PROFILE_ZH",
        "CSR_CLINICAL_SAFETY_FILTER_PROFILE_ZH",
        "CSR_OVERVIEW_FILTER_PROFILE_ZH",
    ):
        assert profile_name not in source


def test_clinical_safety_jobs_resolve_to_direct_projection_with_configured_module() -> None:
    composition = build_clinical_trial_doc_consistency_qc_application_composition()

    for profile in CLINICAL_SAFETY_PROFILES:
        job = composition.resolve_filter_output_projection_job(profile.filter_job_id)
        assert job.strategy_id == DIRECT_FILTER_OUTPUT_PROJECTION_STRATEGY_ID
        assert (
            job.strategy_config[DIRECT_PROJECTION_SEMANTIC_MODULE_ID_CONFIG_KEY]
            == CLINICAL_SAFETY_SEMANTIC_MODULE_ID
        )


def test_overview_jobs_resolve_to_overview_semantic_projection_strategy() -> None:
    composition = build_clinical_trial_doc_consistency_qc_application_composition()

    for profile in OVERVIEW_PROFILES:
        job = composition.resolve_filter_output_projection_job(profile.filter_job_id)
        assert (
            job.strategy_id
            == OVERVIEW_SEMANTIC_DECOMPOSITION_FILTER_OUTPUT_PROJECTION_STRATEGY_ID
        )
        assert job.strategy_config == MappingProxyType(
            {"target_semantic_module_id": CLINICAL_SAFETY_SEMANTIC_MODULE_ID}
        )


def test_unknown_filter_job_raises_without_fallback() -> None:
    composition = build_clinical_trial_doc_consistency_qc_application_composition()

    with pytest.raises(ValueError, match="unknown Filter-output projection job"):
        composition.resolve_filter_output_projection_job("unknown_filter_job")


def test_duplicate_binding_index_raises() -> None:
    duplicate = ResolvedFilterOutputProjectionJob(
        filter_job_id=IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH.filter_job_id,
        strategy_id=DIRECT_FILTER_OUTPUT_PROJECTION_STRATEGY_ID,
        strategy_config=MappingProxyType(
            {
                DIRECT_PROJECTION_SEMANTIC_MODULE_ID_CONFIG_KEY: (
                    CLINICAL_SAFETY_SEMANTIC_MODULE_ID
                ),
            }
        ),
    )

    with pytest.raises(ValueError, match="duplicate installed Filter-output projection"):
        build_filter_output_projection_job_index((duplicate, duplicate))


def test_projection_bindings_cover_all_installed_filter_jobs() -> None:
    installed_filter_job_ids = frozenset(
        config.filter_job_id
        for config in INSTALLED_CLINICAL_TRIAL_DOC_FILTER_CONFIGS.values()
    )

    validate_filter_output_projection_installation(
        installed_filter_job_ids=installed_filter_job_ids,
        filter_output_projection_jobs=(
            INSTALLED_CLINICAL_TRIAL_DOC_FILTER_OUTPUT_PROJECTION_JOBS
        ),
    )

    assert set(INSTALLED_CLINICAL_TRIAL_DOC_FILTER_OUTPUT_PROJECTION_JOBS) == set(
        installed_filter_job_ids
    )


def test_resolved_job_config_isolation_from_caller_mutation() -> None:
    composition = build_clinical_trial_doc_consistency_qc_application_composition()
    job = composition.resolve_filter_output_projection_job(
        IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH.filter_job_id
    )

    with pytest.raises(TypeError):
        job.strategy_config["semantic_module_id"] = "mutated"  # type: ignore[index]


def test_neutral_resolver_does_not_branch_on_job_name_pattern() -> None:
    job = resolve_filter_output_projection_job(
        filter_job_id=IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH.filter_job_id,
        filter_output_projection_jobs=(
            INSTALLED_CLINICAL_TRIAL_DOC_FILTER_OUTPUT_PROJECTION_JOBS
        ),
    )
    assert job.strategy_id == DIRECT_FILTER_OUTPUT_PROJECTION_STRATEGY_ID


def test_installation_import_boundary_excludes_runtime_route_flow_provider() -> None:
    tree = ast.parse(
        INSTALLATION_PATH.read_text(encoding="utf-8"),
        filename=str(INSTALLATION_PATH),
    )
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)

    forbidden_prefixes = (
        "runtime.",
        "execution_flow.",
        "steps.route",
        "llm.providers",
    )
    forbidden_modules = {
        "runtime",
        "execution_flow",
    }
    for module in imported:
        if module in forbidden_modules:
            pytest.fail(f"installation must not import {module!r}")
        for prefix in forbidden_prefixes:
            if module.startswith(prefix):
                pytest.fail(f"installation must not import {module!r}")
