"""Application-composition guards for Document Consistency QC."""

from __future__ import annotations

import ast
import sys
from dataclasses import fields
from pathlib import Path
from types import MappingProxyType
from unittest.mock import patch

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import application as application_surface
import application.clinical_trial_doc_consistency_qc.composition as clinical_qc_composition
from application.clinical_trial_doc_consistency_qc import (
    INSTALLED_CLINICAL_TRIAL_DOC_FILTER_CONFIGS,
    INSTALLED_CLINICAL_TRIAL_DOC_FILTER_JOB_BINDINGS,
    INSTALLED_CLINICAL_TRIAL_DOC_FILTER_JOB_VARIANTS,
    INSTALLED_CLINICAL_TRIAL_DOC_FILTER_OUTPUT_PROJECTION_JOBS,
    INSTALLED_CLINICAL_TRIAL_DOC_PREPARE_ANALYSIS_BINDINGS,
    build_clinical_trial_doc_consistency_qc_application_composition,
)
from application.clinical_trial_doc_consistency_qc.capabilities import (
    INSTALLED_CLINICAL_TRIAL_DOC_CONSISTENCY_QC_CAPABILITIES,
)
from application.clinical_trial_doc_consistency_qc.capability_bindings import (
    INSTALLED_CLINICAL_TRIAL_DOC_EXPECTED_DOCUMENT_TYPE_BINDINGS,
)
from application.clinical_trial_doc_consistency_qc.capability_bindings import (
    internal_ib as internal_ib_capability_bindings,
)
from application.clinical_trial_doc_consistency_qc.extract_installation import (
    INSTALLED_CLINICAL_TRIAL_DOC_EXTRACT_BINDINGS,
    INSTALLED_CLINICAL_TRIAL_DOC_EXTRACT_CONFIG_ID,
    build_installed_clinical_trial_doc_extract_bindings,
    resolve_installed_extract_config_id,
)
from application.clinical_trial_doc_consistency_qc.evidence_source_preparation_consumer_installation import (
    CLINICAL_SAFETY_AGGREGATE_ROUTE_OUTPUT_KIND,
    INSTALLED_CLINICAL_TRIAL_DOC_EVIDENCE_SOURCE_PREPARATION_CONSUMER_BINDINGS,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.evidence_form_identity import (
    AGGREGATE_EVIDENCE_FORM_ID,
)
from application.clinical_trial_doc_consistency_qc.filter_output_projection_installation import (
    CLINICAL_SAFETY_SEMANTIC_MODULE_ID,
)
from application.clinical_trial_doc_consistency_qc.projected_source_route_installation import (
    INSTALLED_CLINICAL_TRIAL_DOC_PROJECTED_SOURCE_ROUTE_EXECUTOR,
)
from application.clinical_trial_doc_consistency_qc.evidence_source_preparation_installation import (
    INSTALLED_CLINICAL_TRIAL_DOC_AGGREGATE_EVIDENCE_SOURCE_PREPARATION_STAGE_EXECUTOR,
)
from operations.evidence_source_preparation.consumer_bindings import (
    EvidenceSourcePreparationConsumerBinding,
    EvidenceSourcePreparationConsumerBindings,
)
from application.document_consistency_qc import (
    DocumentConsistencyQcApplicationComposition,
    validate_capability_slot_bindings,
)
from capability import (
    DSUR_UPDATED_IB_CONSISTENCY_QC,
    INTERNAL_CSR_CONSISTENCY_QC,
    INTERNAL_DSUR_CONSISTENCY_QC,
    INTERNAL_IB_CONSISTENCY_QC,
)
from execution_flow.document_consistency_qc.contracts import (
    DocumentConsistencyQcParticipantSlot,
)
from operations.prepare_analysis.registry import (
    PrepareAnalysisConfigRegistry,
)
from application.clinical_trial_doc_consistency_qc.doc_meta_installation import (
    resolve_installed_doc_meta_dependencies,
)
from plugins.clinical_trial_doc.prepare_analysis import (
    config as prepare_config_module,
)
from plugins.clinical_trial_doc.prepare_analysis.config import (
    CURRENT_CLINICAL_PREPARE_ANALYSIS_CONFIG,
    CURRENT_CLINICAL_PREPARE_ANALYSIS_CONFIG_ID,
    build_current_clinical_prepare_analysis_config_registry,
    register_current_clinical_prepare_analysis_config,
)
from plugins.clinical_trial_doc.prepare_analysis.inputs import (
    load_clinical_prepare_request_options,
)

COMPOSITION_PATH = (
    BACKEND_ROOT
    / "application"
    / "document_consistency_qc"
    / "composition.py"
)
CLINICAL_COMPOSITION_PATH = (
    BACKEND_ROOT
    / "application"
    / "clinical_trial_doc_consistency_qc"
    / "composition.py"
)
BINDING_VALIDATION_PATH = (
    BACKEND_ROOT
    / "application"
    / "document_consistency_qc"
    / "binding_validation.py"
)
CLINICAL_PREPARE_INSTALLATION_PATH = (
    BACKEND_ROOT
    / "application"
    / "clinical_trial_doc_consistency_qc"
    / "prepare_analysis_installation.py"
)
CLINICAL_TRIAL_DOC_LEGACY_PACKAGE_DIR = (
    BACKEND_ROOT / "application" / "clinical_trial_doc"
)
CLINICAL_TRIAL_DOC_CONSISTENCY_QC_PACKAGE_DIR = (
    BACKEND_ROOT / "application" / "clinical_trial_doc_consistency_qc"
)


def _imported_module_names(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_installed_catalogue_is_complete_unique_immutable_and_self_keyed() -> None:
    expected = (
        INTERNAL_DSUR_CONSISTENCY_QC,
        INTERNAL_IB_CONSISTENCY_QC,
        INTERNAL_CSR_CONSISTENCY_QC,
        DSUR_UPDATED_IB_CONSISTENCY_QC,
    )
    catalogue = INSTALLED_CLINICAL_TRIAL_DOC_CONSISTENCY_QC_CAPABILITIES

    assert isinstance(catalogue, MappingProxyType)
    assert tuple(catalogue) == tuple(config.capability_id for config in expected)
    assert len(catalogue) == len(expected)
    assert len(set(catalogue)) == len(expected)
    for capability_id, config in catalogue.items():
        assert capability_id == config.capability_id
        assert config in expected
    with pytest.raises(TypeError):
        catalogue["new"] = expected[0]  # type: ignore[index]


def test_installed_catalogue_preserves_current_slot_topology() -> None:
    catalogue = INSTALLED_CLINICAL_TRIAL_DOC_CONSISTENCY_QC_CAPABILITIES
    expected_slots = {
        "internal_dsur": ("source",),
        "internal_ib": ("source",),
        "internal_csr": ("source",),
        "dsur_updated_ib": ("source_a", "source_b"),
    }

    assert set(catalogue) == set(expected_slots)
    for capability_id, slot_ids in expected_slots.items():
        slots = catalogue[capability_id].slots
        assert tuple(slot.slot_id for slot in slots) == slot_ids
        assert {field.name for field in fields(DocumentConsistencyQcParticipantSlot)} == {
            "slot_id"
        }


def test_assembled_capability_bindings_match_canonical_values() -> None:
    expected_prepare = {
        ("internal_dsur", "source"): CURRENT_CLINICAL_PREPARE_ANALYSIS_CONFIG_ID,
        ("internal_ib", "source"): CURRENT_CLINICAL_PREPARE_ANALYSIS_CONFIG_ID,
        ("internal_csr", "source"): CURRENT_CLINICAL_PREPARE_ANALYSIS_CONFIG_ID,
        ("dsur_updated_ib", "source_a"): CURRENT_CLINICAL_PREPARE_ANALYSIS_CONFIG_ID,
        ("dsur_updated_ib", "source_b"): CURRENT_CLINICAL_PREPARE_ANALYSIS_CONFIG_ID,
    }
    expected_filter = {
        ("internal_dsur", "source"): (
            "dsur_clinical_safety",
            "dsur_overview",
        ),
        ("internal_ib", "source"): (
            "ib_clinical_safety",
            "ib_overview",
        ),
        ("internal_csr", "source"): (
            "csr_clinical_safety",
            "csr_overview",
        ),
        ("dsur_updated_ib", "source_a"): (
            "dsur_clinical_safety",
            "dsur_overview",
        ),
        ("dsur_updated_ib", "source_b"): (
            "ib_clinical_safety",
            "ib_overview",
        ),
    }
    expected_document_type = {
        ("internal_dsur", "source"): "DSUR",
        ("internal_ib", "source"): "IB",
        ("internal_csr", "source"): "CSR",
        ("dsur_updated_ib", "source_a"): "DSUR",
        ("dsur_updated_ib", "source_b"): "IB",
    }

    assert dict(INSTALLED_CLINICAL_TRIAL_DOC_PREPARE_ANALYSIS_BINDINGS) == expected_prepare
    assert dict(INSTALLED_CLINICAL_TRIAL_DOC_FILTER_JOB_BINDINGS) == expected_filter
    assert (
        dict(INSTALLED_CLINICAL_TRIAL_DOC_EXPECTED_DOCUMENT_TYPE_BINDINGS)
        == expected_document_type
    )


def test_internal_ib_capability_bindings_use_slot_local_keys_only() -> None:
    assert internal_ib_capability_bindings.CAPABILITY_ID == "internal_ib"
    assert set(internal_ib_capability_bindings.PREPARE_ANALYSIS_BINDINGS) == {"source"}
    assert set(internal_ib_capability_bindings.FILTER_JOB_BINDINGS) == {"source"}
    assert set(internal_ib_capability_bindings.EXPECTED_DOCUMENT_TYPE_BINDINGS) == {
        "source"
    }
    assert not hasattr(internal_ib_capability_bindings, "EXTRACT_BINDINGS")


def test_installed_extract_bindings_project_installed_config_onto_every_slot() -> None:
    expected = {
        ("internal_dsur", "source"): INSTALLED_CLINICAL_TRIAL_DOC_EXTRACT_CONFIG_ID,
        ("internal_ib", "source"): INSTALLED_CLINICAL_TRIAL_DOC_EXTRACT_CONFIG_ID,
        ("internal_csr", "source"): INSTALLED_CLINICAL_TRIAL_DOC_EXTRACT_CONFIG_ID,
        ("dsur_updated_ib", "source_a"): INSTALLED_CLINICAL_TRIAL_DOC_EXTRACT_CONFIG_ID,
        ("dsur_updated_ib", "source_b"): INSTALLED_CLINICAL_TRIAL_DOC_EXTRACT_CONFIG_ID,
    }
    assert dict(INSTALLED_CLINICAL_TRIAL_DOC_EXTRACT_BINDINGS) == expected
    assert (
        dict(
            build_installed_clinical_trial_doc_extract_bindings(
                INSTALLED_CLINICAL_TRIAL_DOC_CONSISTENCY_QC_CAPABILITIES
            )
        )
        == expected
    )


def test_capability_binding_modules_do_not_author_extract_config() -> None:
    for module_name in ("internal_dsur", "internal_ib", "internal_csr", "dsur_updated_ib"):
        module_path = (
            CLINICAL_TRIAL_DOC_CONSISTENCY_QC_PACKAGE_DIR
            / "capability_bindings"
            / f"{module_name}.py"
        )
        source = module_path.read_text(encoding="utf-8")
        assert "EXTRACT_BINDINGS" not in source


def test_resolve_installed_extract_config_id_uses_installation_source_of_truth() -> None:
    assert resolve_installed_extract_config_id() is INSTALLED_CLINICAL_TRIAL_DOC_EXTRACT_CONFIG_ID


def test_installed_prepare_bindings_match_current_values() -> None:
    for capability_id, slot_id in (
        ("internal_dsur", "source"),
        ("internal_ib", "source"),
        ("internal_csr", "source"),
        ("dsur_updated_ib", "source_a"),
        ("dsur_updated_ib", "source_b"),
    ):
        assert (
            INSTALLED_CLINICAL_TRIAL_DOC_PREPARE_ANALYSIS_BINDINGS[
                (capability_id, slot_id)
            ]
            == CURRENT_CLINICAL_PREPARE_ANALYSIS_CONFIG_ID
        )


def test_installed_filter_job_bindings_match_current_values_and_order() -> None:
    expected = {
        "internal_dsur": {
            "source": ("dsur_clinical_safety", "dsur_overview"),
        },
        "internal_ib": {
            "source": ("ib_clinical_safety", "ib_overview"),
        },
        "internal_csr": {
            "source": ("csr_clinical_safety", "csr_overview"),
        },
        "dsur_updated_ib": {
            "source_a": ("dsur_clinical_safety", "dsur_overview"),
            "source_b": ("ib_clinical_safety", "ib_overview"),
        },
    }
    for capability_id, slot_bindings in expected.items():
        for slot_id, jobs in slot_bindings.items():
            assert (
                INSTALLED_CLINICAL_TRIAL_DOC_FILTER_JOB_BINDINGS[
                    (capability_id, slot_id)
                ]
                == jobs
            )


def test_installed_expected_document_type_bindings_match_current_values() -> None:
    expected = {
        ("internal_dsur", "source"): "DSUR",
        ("internal_ib", "source"): "IB",
        ("internal_csr", "source"): "CSR",
        ("dsur_updated_ib", "source_a"): "DSUR",
        ("dsur_updated_ib", "source_b"): "IB",
    }
    assert dict(INSTALLED_CLINICAL_TRIAL_DOC_EXPECTED_DOCUMENT_TYPE_BINDINGS) == expected


def test_binding_validation_rejects_missing_and_orphan_keys() -> None:
    capabilities = INSTALLED_CLINICAL_TRIAL_DOC_CONSISTENCY_QC_CAPABILITIES
    complete_extract = dict(INSTALLED_CLINICAL_TRIAL_DOC_EXTRACT_BINDINGS)
    complete_prepare = dict(INSTALLED_CLINICAL_TRIAL_DOC_PREPARE_ANALYSIS_BINDINGS)
    complete_filter = dict(INSTALLED_CLINICAL_TRIAL_DOC_FILTER_JOB_BINDINGS)
    complete_expected = dict(INSTALLED_CLINICAL_TRIAL_DOC_EXPECTED_DOCUMENT_TYPE_BINDINGS)

    validate_capability_slot_bindings(
        capabilities=capabilities,
        extract_bindings=complete_extract,
        prepare_analysis_bindings=complete_prepare,
        filter_job_bindings=complete_filter,
        expected_document_type_bindings=complete_expected,
    )

    missing_extract = dict(complete_extract)
    missing_extract.pop(("internal_dsur", "source"))
    with pytest.raises(ValueError, match="missing Extract binding"):
        validate_capability_slot_bindings(
            capabilities=capabilities,
            extract_bindings=missing_extract,
            prepare_analysis_bindings=complete_prepare,
            filter_job_bindings=complete_filter,
            expected_document_type_bindings=complete_expected,
        )

    missing_prepare = dict(complete_prepare)
    missing_prepare.pop(("internal_ib", "source"))
    with pytest.raises(ValueError, match="missing Prepare Analysis binding"):
        validate_capability_slot_bindings(
            capabilities=capabilities,
            extract_bindings=complete_extract,
            prepare_analysis_bindings=missing_prepare,
            filter_job_bindings=complete_filter,
            expected_document_type_bindings=complete_expected,
        )

    missing_filter = dict(complete_filter)
    missing_filter.pop(("internal_csr", "source"))
    with pytest.raises(ValueError, match="missing Filter job binding"):
        validate_capability_slot_bindings(
            capabilities=capabilities,
            extract_bindings=complete_extract,
            prepare_analysis_bindings=complete_prepare,
            filter_job_bindings=missing_filter,
            expected_document_type_bindings=complete_expected,
        )

    orphan_extract = dict(complete_extract)
    orphan_extract[("unknown_capability", "source")] = "docx"
    with pytest.raises(ValueError, match="unknown capability_id"):
        validate_capability_slot_bindings(
            capabilities=capabilities,
            extract_bindings=orphan_extract,
            prepare_analysis_bindings=complete_prepare,
            filter_job_bindings=complete_filter,
            expected_document_type_bindings=complete_expected,
        )

    orphan_slot = dict(complete_extract)
    orphan_slot[("internal_dsur", "missing_slot")] = "docx"
    with pytest.raises(ValueError, match="unknown slot_id"):
        validate_capability_slot_bindings(
            capabilities=capabilities,
            extract_bindings=orphan_slot,
            prepare_analysis_bindings=complete_prepare,
            filter_job_bindings=complete_filter,
            expected_document_type_bindings=complete_expected,
        )


def test_explicit_empty_filter_binding_is_structurally_valid() -> None:
    capabilities = INSTALLED_CLINICAL_TRIAL_DOC_CONSISTENCY_QC_CAPABILITIES
    extract_bindings = dict(INSTALLED_CLINICAL_TRIAL_DOC_EXTRACT_BINDINGS)
    prepare_bindings = dict(INSTALLED_CLINICAL_TRIAL_DOC_PREPARE_ANALYSIS_BINDINGS)
    filter_bindings = dict(INSTALLED_CLINICAL_TRIAL_DOC_FILTER_JOB_BINDINGS)
    filter_bindings[("internal_dsur", "source")] = ()
    validate_capability_slot_bindings(
        capabilities=capabilities,
        extract_bindings=extract_bindings,
        prepare_analysis_bindings=prepare_bindings,
        filter_job_bindings=filter_bindings,
        expected_document_type_bindings=dict(
            INSTALLED_CLINICAL_TRIAL_DOC_EXPECTED_DOCUMENT_TYPE_BINDINGS
        ),
    )


def test_clinical_prepare_registry_builder_returns_populated_neutral_registry() -> None:
    with patch.object(
        prepare_config_module,
        "register_current_clinical_prepare_analysis_config",
        wraps=prepare_config_module.register_current_clinical_prepare_analysis_config,
    ) as register:
        registry = build_current_clinical_prepare_analysis_config_registry()

    assert isinstance(registry, PrepareAnalysisConfigRegistry)
    register.assert_called_once_with(registry)
    assert (
        registry.resolve(CURRENT_CLINICAL_PREPARE_ANALYSIS_CONFIG_ID)
        is CURRENT_CLINICAL_PREPARE_ANALYSIS_CONFIG
    )


def test_clinical_installation_binds_domain_dependencies() -> None:
    registry = PrepareAnalysisConfigRegistry()
    register_current_clinical_prepare_analysis_config(registry)
    with patch.object(
        clinical_qc_composition,
        "build_current_clinical_prepare_analysis_config_registry",
        return_value=registry,
    ) as build_registry:
        composition = (
            build_clinical_trial_doc_consistency_qc_application_composition()
        )

    build_registry.assert_called_once_with()
    assert isinstance(composition, DocumentConsistencyQcApplicationComposition)
    assert (
        composition.capabilities
        is INSTALLED_CLINICAL_TRIAL_DOC_CONSISTENCY_QC_CAPABILITIES
    )
    assert dict(composition.extract_bindings) == dict(
        INSTALLED_CLINICAL_TRIAL_DOC_EXTRACT_BINDINGS
    )
    for extract_config_id in composition.extract_bindings.values():
        assert extract_config_id is INSTALLED_CLINICAL_TRIAL_DOC_EXTRACT_CONFIG_ID
    assert (
        composition.prepare_analysis_bindings
        is INSTALLED_CLINICAL_TRIAL_DOC_PREPARE_ANALYSIS_BINDINGS
    )
    assert (
        composition.filter_job_bindings
        is INSTALLED_CLINICAL_TRIAL_DOC_FILTER_JOB_BINDINGS
    )
    assert (
        composition.expected_document_type_bindings
        is INSTALLED_CLINICAL_TRIAL_DOC_EXPECTED_DOCUMENT_TYPE_BINDINGS
    )
    assert (
        composition.expected_document_type_bindings[("dsur_updated_ib", "source_a")]
        == "DSUR"
    )
    assert (
        composition.expected_document_type_bindings[("dsur_updated_ib", "source_b")]
        == "IB"
    )
    assert composition.prepare_analysis_config_registry is registry
    assert (
        composition.load_prepare_request_options
        is load_clinical_prepare_request_options
    )
    installed_doc_meta = resolve_installed_doc_meta_dependencies()
    assert composition.doc_meta_profile is installed_doc_meta.profile
    assert (
        composition.doc_meta_summary_builder
        is installed_doc_meta.summary_builder
    )
    assert composition.filter_configs is INSTALLED_CLINICAL_TRIAL_DOC_FILTER_CONFIGS
    assert (
        composition.filter_job_variants
        is INSTALLED_CLINICAL_TRIAL_DOC_FILTER_JOB_VARIANTS
    )
    assert (
        composition.filter_output_projection_jobs
        is INSTALLED_CLINICAL_TRIAL_DOC_FILTER_OUTPUT_PROJECTION_JOBS
    )
    assert (
        composition.projected_source_route_executor
        is INSTALLED_CLINICAL_TRIAL_DOC_PROJECTED_SOURCE_ROUTE_EXECUTOR
    )
    assert isinstance(
        composition.evidence_source_preparation_consumer_bindings,
        EvidenceSourcePreparationConsumerBindings,
    )
    assert (
        composition.evidence_source_preparation_consumer_bindings
        is INSTALLED_CLINICAL_TRIAL_DOC_EVIDENCE_SOURCE_PREPARATION_CONSUMER_BINDINGS
    )
    assert set(
        composition.evidence_source_preparation_consumer_bindings.bindings
    ) == {CLINICAL_SAFETY_SEMANTIC_MODULE_ID}
    installed_binding = (
        composition.evidence_source_preparation_consumer_bindings.bindings[
            CLINICAL_SAFETY_SEMANTIC_MODULE_ID
        ]
    )
    assert isinstance(
        installed_binding,
        EvidenceSourcePreparationConsumerBinding,
    )
    assert installed_binding.semantic_module_id == CLINICAL_SAFETY_SEMANTIC_MODULE_ID
    assert (
        installed_binding.required_route_output_kind
        == CLINICAL_SAFETY_AGGREGATE_ROUTE_OUTPUT_KIND
    )
    assert installed_binding.evidence_form_id == AGGREGATE_EVIDENCE_FORM_ID
    assert (
        installed_binding.stage_executor
        is INSTALLED_CLINICAL_TRIAL_DOC_AGGREGATE_EVIDENCE_SOURCE_PREPARATION_STAGE_EXECUTOR
    )
    resolved_binding = (
        composition.evidence_source_preparation_consumer_bindings.resolve_consumer_binding(
            CLINICAL_SAFETY_SEMANTIC_MODULE_ID
        )
    )
    assert resolved_binding is installed_binding


def test_installed_filter_catalog_is_complete_unique_immutable_and_self_keyed() -> None:
    expected_ids = {
        "ib_clinical_safety_zh",
        "ib_overview_zh",
        "dsur_clinical_safety_zh",
        "dsur_overview_zh",
        "csr_clinical_safety_zh",
        "csr_overview_zh",
    }
    catalogue = INSTALLED_CLINICAL_TRIAL_DOC_FILTER_CONFIGS

    assert isinstance(catalogue, MappingProxyType)
    assert set(catalogue) == expected_ids
    assert len(catalogue) == len(expected_ids)
    for config_id, config in catalogue.items():
        assert config_id == config.zone_config_name
    with pytest.raises(TypeError):
        catalogue["new"] = next(iter(catalogue.values()))  # type: ignore[index]


def test_installed_filter_job_variants_is_immutable() -> None:
    catalogue = INSTALLED_CLINICAL_TRIAL_DOC_FILTER_JOB_VARIANTS
    assert isinstance(catalogue, MappingProxyType)
    with pytest.raises(TypeError):
        catalogue[("new", "zh")] = next(iter(catalogue.values()))  # type: ignore[index]


def test_installed_filter_catalog_matches_application_composition() -> None:
    composition = build_clinical_trial_doc_consistency_qc_application_composition()
    assert composition.filter_configs is INSTALLED_CLINICAL_TRIAL_DOC_FILTER_CONFIGS


def test_stable_application_surface_delegates_to_installed_composition() -> None:
    installed = object()
    with patch.object(
        application_surface,
        "build_clinical_trial_doc_consistency_qc_application_composition",
        return_value=installed,
    ) as build:
        result = (
            application_surface.build_installed_document_consistency_qc_application_composition()
        )

    build.assert_called_once_with()
    assert result is installed


def test_neutral_binding_validation_has_zero_clinical_dependencies() -> None:
    source = BINDING_VALIDATION_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(BINDING_VALIDATION_PATH))
    imported = _imported_module_names(tree)

    assert not any(
        module == "application.clinical_trial_doc_consistency_qc"
        or module.startswith("application.clinical_trial_doc_consistency_qc.")
        or module == "plugins.clinical_trial_doc"
        or module.startswith(
            ("plugins.clinical_trial_doc.", "capability.clinical_trial_doc_")
        )
        for module in imported
    )
    for token in ("ClinicalTrialDocumentType", "CLINICAL_TRIAL_DOCUMENT_TYPES", '"IB"', '"CSR"', '"DSUR"'):
        assert token not in source


def test_neutral_composition_contract_has_zero_clinical_dependencies() -> None:
    source = COMPOSITION_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(COMPOSITION_PATH))
    imported = _imported_module_names(tree)

    assert not any(
        module == "application.clinical_trial_doc_consistency_qc"
        or module.startswith("application.clinical_trial_doc_consistency_qc.")
        or module == "plugins.clinical_trial_doc"
        or module.startswith(
            ("plugins.clinical_trial_doc.", "capability.clinical_trial_doc_")
        )
        for module in imported
    )
    for token in (
        "internal_ib",
        "internal_dsur",
        "internal_csr",
        "dsur_updated_ib",
        "ClinicalPrepare",
        "load_clinical",
        "register_current_clinical",
        "build_current_clinical",
    ):
        assert token not in source


def test_clinical_qc_intersection_composition_is_wiring_only() -> None:
    source = CLINICAL_COMPOSITION_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(CLINICAL_COMPOSITION_PATH))
    imported = _imported_module_names(tree)

    assert any(module in {"capabilities", "capability_bindings"} for module in imported)
    assert "from .capabilities import" in source
    assert "from .capability_bindings import" in source
    assert "from .prepare_analysis_installation import" in source
    for token in (
        "argparse",
        "run_document_consistency_qc_flow",
        "DocumentConsistencyQcParticipantRunInput",
        "runtime.",
        "steps",
        "json.load",
        "json.loads",
        "print(",
        "plugins.clinical_trial_doc",
        "capability.clinical_trial_doc_",
    ):
        assert token not in source


def test_clinical_prepare_installation_module_binds_plugin_dependencies() -> None:
    source = CLINICAL_PREPARE_INSTALLATION_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(CLINICAL_PREPARE_INSTALLATION_PATH))
    imported = _imported_module_names(tree)

    assert any(module.startswith("plugins.clinical_trial_doc.") for module in imported)


def test_document_consistency_qc_product_application_namespace() -> None:
    """Product Application contracts resolve from the explicit product subpackage."""
    from application.document_consistency_qc import (
        DocumentConsistencyQcApplicationComposition,
        build_document_consistency_qc_application_result,
        validate_capability_slot_bindings,
    )

    assert DocumentConsistencyQcApplicationComposition is not None
    assert callable(validate_capability_slot_bindings)
    assert callable(build_document_consistency_qc_application_result)

    flattened_paths = (
        BACKEND_ROOT / "application" / "composition.py",
        BACKEND_ROOT / "application" / "binding_validation.py",
        BACKEND_ROOT / "application" / "document_type_result.py",
    )
    for path in flattened_paths:
        assert not path.is_file(), f"flattened module still exists: {path}"


def test_clinical_trial_doc_consistency_qc_is_canonical_coordinate_package() -> None:
    """The concrete coordinate lives in one flat package; legacy D-APP parent is gone."""

    assert CLINICAL_TRIAL_DOC_CONSISTENCY_QC_PACKAGE_DIR.is_dir()
    assert not CLINICAL_TRIAL_DOC_LEGACY_PACKAGE_DIR.exists()
    for required in (
        "composition.py",
        "execution.py",
        "capabilities.py",
        "filter_installation.py",
        "prepare_analysis_installation.py",
    ):
        path = CLINICAL_TRIAL_DOC_CONSISTENCY_QC_PACKAGE_DIR / required
        assert path.is_file(), f"missing canonical coordinate module: {path}"


def test_clinical_trial_doc_document_consistency_qc_intersection_namespace() -> None:
    """Concrete Clinical Trial × Document Consistency QC installation resolves from one package."""
    from application.clinical_trial_doc_consistency_qc import (
        build_clinical_trial_doc_consistency_qc_application_composition,
    )
    from application.clinical_trial_doc_consistency_qc.capabilities import (
        INSTALLED_CLINICAL_TRIAL_DOC_CONSISTENCY_QC_CAPABILITIES,
    )
    from application.clinical_trial_doc_consistency_qc.extract_installation import (
        INSTALLED_CLINICAL_TRIAL_DOC_EXTRACT_BINDINGS,
    )
    from application.clinical_trial_doc_consistency_qc.capability_bindings import (
        INSTALLED_CLINICAL_TRIAL_DOC_EXPECTED_DOCUMENT_TYPE_BINDINGS,
    )
    from application.clinical_trial_doc_consistency_qc.composition import (
        build_clinical_trial_doc_consistency_qc_application_composition as composition_builder,
    )
    from application.clinical_trial_doc_consistency_qc.route_semantic_module_installation import (
        INSTALLED_CLINICAL_TRIAL_DOC_ROUTE_SEMANTIC_MODULE_SEQUENCE,
    )

    assert callable(build_clinical_trial_doc_consistency_qc_application_composition)
    assert callable(composition_builder)
    assert INSTALLED_CLINICAL_TRIAL_DOC_CONSISTENCY_QC_CAPABILITIES is not None
    assert INSTALLED_CLINICAL_TRIAL_DOC_EXTRACT_BINDINGS is not None
    assert INSTALLED_CLINICAL_TRIAL_DOC_EXPECTED_DOCUMENT_TYPE_BINDINGS is not None
    assert INSTALLED_CLINICAL_TRIAL_DOC_ROUTE_SEMANTIC_MODULE_SEQUENCE is not None

    former_intersection_paths = (
        BACKEND_ROOT
        / "application"
        / "clinical_trial_doc"
        / "document_consistency_qc"
        / "capabilities.py",
        BACKEND_ROOT
        / "application"
        / "clinical_trial_doc"
        / "document_consistency_qc"
        / "extract_installation.py",
        BACKEND_ROOT
        / "application"
        / "clinical_trial_doc"
        / "capabilities.py",
        BACKEND_ROOT
        / "application"
        / "clinical_trial_doc"
        / "extract_installation.py",
    )
    for path in former_intersection_paths:
        assert not path.is_file(), f"former intersection module still exists: {path}"
