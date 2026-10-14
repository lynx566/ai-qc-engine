"""S5 guards for application-installed Prepare Analysis config bindings."""

from __future__ import annotations

import inspect
import sys
from dataclasses import fields
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from application.clinical_trial_doc_consistency_qc import (
    INSTALLED_CLINICAL_TRIAL_DOC_PREPARE_ANALYSIS_BINDINGS,
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
from operations.prepare_analysis.contracts import PrepareAnalysisConfigId
from operations.prepare_analysis.registry import PrepareAnalysisConfigRegistry
from plugins.clinical_trial_doc.prepare_analysis.config import (
    CURRENT_CLINICAL_PREPARE_ANALYSIS_CONFIG_ID,
    register_current_clinical_prepare_analysis_config,
)

CONTRACTS_PATH = (
    BACKEND_ROOT / "execution_flow/document_consistency_qc/contracts.py"
)
FLOW_PATH = (
    BACKEND_ROOT / "execution_flow/document_consistency_qc/flow.py"
)
INTERNAL_DSUR_PATH = (
    BACKEND_ROOT
    / "capability"
    / "clinical_trial_doc_consistency_qc"
    / "internal_dsur.py"
)

CURRENT_CAPABILITIES = (
    INTERNAL_IB_CONSISTENCY_QC,
    INTERNAL_DSUR_CONSISTENCY_QC,
    INTERNAL_CSR_CONSISTENCY_QC,
    DSUR_UPDATED_IB_CONSISTENCY_QC,
)


@pytest.mark.parametrize("value", ["", " pacfg_untrimmed", "pacfg_untrimmed "])
def test_prepare_analysis_config_id_rejects_empty_or_untrimmed_refs(value: str) -> None:
    with pytest.raises(ValueError, match="non-empty, trimmed"):
        PrepareAnalysisConfigId(value)


def test_capability_slot_contains_only_product_topology() -> None:
    field_names = {field.name for field in fields(DocumentConsistencyQcParticipantSlot)}
    assert field_names == {"slot_id"}
    assert not field_names.intersection(
        {
            "extract_config_id",
            "prepare_analysis_config_id",
            "filter_job_ids",
            "privacy_profile_id",
            "privacy_policy_ref",
            "detectors",
            "registry_id",
            "regex_rule_id",
            "uie_schema_id",
            "date_shift",
            "date_shift_offset_days",
            "language",
            "clinical_program_id",
            "document_type",
        }
    )


def test_every_current_capability_slot_has_topology_only() -> None:
    expected = {
        "internal_ib": ("source",),
        "internal_dsur": ("source",),
        "internal_csr": ("source",),
        "dsur_updated_ib": ("source_a", "source_b"),
    }
    actual = {
        capability.capability_id: tuple(slot.slot_id for slot in capability.slots)
        for capability in CURRENT_CAPABILITIES
    }
    assert actual == expected


def test_every_current_slot_prepare_binding_is_explicit() -> None:
    expected = {
        "internal_ib": {"source": CURRENT_CLINICAL_PREPARE_ANALYSIS_CONFIG_ID},
        "internal_dsur": {"source": CURRENT_CLINICAL_PREPARE_ANALYSIS_CONFIG_ID},
        "internal_csr": {"source": CURRENT_CLINICAL_PREPARE_ANALYSIS_CONFIG_ID},
        "dsur_updated_ib": {
            "source_a": CURRENT_CLINICAL_PREPARE_ANALYSIS_CONFIG_ID,
            "source_b": CURRENT_CLINICAL_PREPARE_ANALYSIS_CONFIG_ID,
        },
    }
    actual: dict[str, dict[str, PrepareAnalysisConfigId]] = {}
    for capability in CURRENT_CAPABILITIES:
        actual[capability.capability_id] = {}
        for slot in capability.slots:
            key = (capability.capability_id, slot.slot_id)
            actual[capability.capability_id][slot.slot_id] = (
                INSTALLED_CLINICAL_TRIAL_DOC_PREPARE_ANALYSIS_BINDINGS[key]
            )
    assert actual == expected


def test_every_current_slot_prepare_binding_resolves_under_explicit_composition() -> None:
    registry = PrepareAnalysisConfigRegistry()
    register_current_clinical_prepare_analysis_config(registry)

    resolved_ids: list[PrepareAnalysisConfigId] = []
    for capability in CURRENT_CAPABILITIES:
        for slot in capability.slots:
            key = (capability.capability_id, slot.slot_id)
            config_id = INSTALLED_CLINICAL_TRIAL_DOC_PREPARE_ANALYSIS_BINDINGS[key]
            resolved = registry.resolve(config_id)
            assert resolved.prepare_analysis_config_id == config_id
            resolved_ids.append(config_id)

    assert len(resolved_ids) == 5
    assert set(resolved_ids) == {CURRENT_CLINICAL_PREPARE_ANALYSIS_CONFIG_ID}


def test_capability_definitions_do_not_import_operation_implementation_config() -> None:
    source = INTERNAL_DSUR_PATH.read_text(encoding="utf-8")
    assert "plugins.clinical_trial_doc" not in source
    assert "CURRENT_CLINICAL_PREPARE_ANALYSIS_CONFIG_ID" not in source
    assert "extract_config_id" not in source
    assert "filter_job_ids" not in source


def test_neutral_contract_and_flow_keep_clinical_and_standalone_boundaries() -> None:
    contracts_source = CONTRACTS_PATH.read_text(encoding="utf-8")
    flow_source = FLOW_PATH.read_text(encoding="utf-8")

    assert "plugins.clinical_trial_doc" not in contracts_source
    assert "plugins.clinical_trial_doc" not in flow_source
    assert "prepare_analysis.standalone" not in contracts_source
    assert "prepare_analysis.standalone" not in flow_source
    assert "run_prepare_analysis_operation" in flow_source
    assert "prepare_analysis_bindings" in flow_source
    assert "slot.prepare_analysis_config_id" not in flow_source
    assert "CURRENT_CLINICAL_PREPARE_ANALYSIS_CONFIG_ID" not in flow_source
    assert "prepare_analysis_bundle" not in flow_source
