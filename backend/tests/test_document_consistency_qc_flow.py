"""Tests for document-consistency QC flow and clinical-trial capability configs."""

from __future__ import annotations

import ast
import json
import sys
from dataclasses import asdict, fields
from pathlib import Path
from unittest.mock import patch

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import execution_flow.document_consistency_qc.flow as flow_module
import execution_flow.processing_launch as processing_launch_module
from application.clinical_trial_doc_consistency_qc import (
    INSTALLED_CLINICAL_TRIAL_DOC_FILTER_JOB_BINDINGS,
)
from artifacts.document_consistency_qc_flow_run_summary import validate_flow_run_summary
from capability import (
    DSUR_UPDATED_IB_CONSISTENCY_QC,
    INTERNAL_CSR_CONSISTENCY_QC,
    INTERNAL_DSUR_CONSISTENCY_QC,
    INTERNAL_IB_CONSISTENCY_QC,
)
from core.document.doc_identity import DocumentProcessingIdentity, compute_content_hash
from core.metadata.schemas import MetadataContextConfig, MetadataProfile
from execution_flow.document_consistency_qc.contracts import (
    DocumentConsistencyQcCapabilityConfig,
    DocumentConsistencyQcParticipantSlot,
    DocumentConsistencyQcParticipantRunInput,
)
from operations.prepare_analysis import PrepareAnalysisRequestOptions
from operations.prepare_analysis.registry import PrepareAnalysisConfigRegistry
from plugins.clinical_trial_doc.prepare_analysis.config import (
    register_current_clinical_prepare_analysis_config,
)
from plugins.clinical_trial_doc.prepare_analysis.inputs import (
    ClinicalPreparePrivacyConfig,
)
from runtime.extract.operations import ExtractDocumentResult
from runtime.io import load_json
from runtime.projected_source_route_stage import PersistedProjectionRouteStageOutcome
from tests.document_consistency_qc_flow_helpers import (
    admit_participant_source_binding,
    clinical_flow_invocation_kwargs,
)

SAMPLE_DOCX = (
    BACKEND_ROOT
    / "tests"
    / "fixtures"
    / "clinical_trial_doc"
    / "extract"
    / "ib_extract_minimal_001.docx"
)
SECOND_SAMPLE_DOCX = (
    BACKEND_ROOT
    / "tests"
    / "fixtures"
    / "clinical_trial_doc"
    / "tag_integration"
    / "ib_safety_tag_integration_001.docx"
)

FLOW_PATH = (
    BACKEND_ROOT / "execution_flow" / "document_consistency_qc" / "flow.py"
)
CONTRACTS_PATH = (
    BACKEND_ROOT / "execution_flow" / "document_consistency_qc" / "contracts.py"
)
SINGLE_DOCUMENT_PATH = (
    BACKEND_ROOT / "capability" / "clinical_trial_doc_consistency_qc" / "_single_document.py"
)
DOCUMENT_BRANCH_PATH = (
    BACKEND_ROOT / "execution_flow" / "document_branch.py"
)
EXECUTION_FLOW_ROOT = BACKEND_ROOT / "execution_flow"
EXECUTION_FLOW_QC_ROOT = EXECUTION_FLOW_ROOT / "document_consistency_qc"
PROCESSING_LAUNCH_PATH = EXECUTION_FLOW_ROOT / "processing_launch.py"
INTERNAL_DSUR_PATH = (
    BACKEND_ROOT
    / "capability"
    / "clinical_trial_doc_consistency_qc"
    / "internal_dsur.py"
)
INTERNAL_IB_PATH = (
    BACKEND_ROOT
    / "capability"
    / "clinical_trial_doc_consistency_qc"
    / "internal_ib.py"
)
INTERNAL_CSR_PATH = (
    BACKEND_ROOT
    / "capability"
    / "clinical_trial_doc_consistency_qc"
    / "internal_csr.py"
)
DSUR_UPDATED_IB_PATH = (
    BACKEND_ROOT
    / "capability"
    / "clinical_trial_doc_consistency_qc"
    / "dsur_updated_ib.py"
)

ALL_CAPABILITY_CONFIGS = (
    INTERNAL_DSUR_CONSISTENCY_QC,
    INTERNAL_IB_CONSISTENCY_QC,
    INTERNAL_CSR_CONSISTENCY_QC,
    DSUR_UPDATED_IB_CONSISTENCY_QC,
)
INTERNAL_CAPABILITY_CONFIGS = (
    INTERNAL_DSUR_CONSISTENCY_QC,
    INTERNAL_IB_CONSISTENCY_QC,
    INTERNAL_CSR_CONSISTENCY_QC,
)
CAPABILITY_MODULE_PATHS = (
    INTERNAL_DSUR_PATH,
    INTERNAL_IB_PATH,
    INTERNAL_CSR_PATH,
    DSUR_UPDATED_IB_PATH,
)


def _git_prov() -> dict[str, str | bool | None]:
    return {"git_commit": "abc", "git_dirty": False}


def _run_flow(
    *,
    capability_config: DocumentConsistencyQcCapabilityConfig,
    uploads: dict[str, Path | str | object],
    project_root: Path,
):
    from runtime.document_source_binding import DocumentIntakeSourceBinding

    admitted_uploads: dict[str, DocumentIntakeSourceBinding] = {}
    for slot_id, upload in uploads.items():
        if isinstance(upload, DocumentIntakeSourceBinding):
            admitted_uploads[slot_id] = upload
        else:
            admitted_uploads[slot_id] = admit_participant_source_binding(
                project_root,
                Path(upload),
            )
    registry = PrepareAnalysisConfigRegistry()
    register_current_clinical_prepare_analysis_config(registry)
    return flow_module.run_document_consistency_qc_flow(
        project_root=project_root,
        capability_config=capability_config,
        uploads=admitted_uploads,
        participant_inputs={
            slot_id: DocumentConsistencyQcParticipantRunInput(
                prepare_analysis_request_options=PrepareAnalysisRequestOptions(
                    ClinicalPreparePrivacyConfig.identity()
                ),
            )
            for slot_id in admitted_uploads
        },
        prepare_analysis_config_registry=registry,
        git_provenance=_git_prov(),
        **clinical_flow_invocation_kwargs(),
    )


def test_four_static_capability_configs_exist() -> None:
    assert INTERNAL_DSUR_PATH.is_file()
    assert INTERNAL_IB_PATH.is_file()
    assert INTERNAL_CSR_PATH.is_file()
    assert DSUR_UPDATED_IB_PATH.is_file()
    for config in ALL_CAPABILITY_CONFIGS:
        assert config.capability_id
        assert config.slots


def test_static_capability_modules_contain_no_path_or_runtime_binding() -> None:
    forbidden_tokens = (
        "run_word_zh_",
        "ConsistencyQcParticipantInput",
        "run_request_file_intake_operation",
        "run_extract_operation",
        "run_document_consistency_qc_flow",
        "source=",
        "dsur_source",
        "updated_ib_source",
    )
    for path in CAPABILITY_MODULE_PATHS:
        source = path.read_text(encoding="utf-8")
        for token in forbidden_tokens:
            assert token not in source, f"{path.name} must not contain {token!r}"


def test_internal_dsur_capability_config() -> None:
    config = INTERNAL_DSUR_CONSISTENCY_QC
    assert config.capability_id == "internal_dsur"
    assert len(config.slots) == 1
    assert config.slots[0].slot_id == "source"


def test_internal_ib_capability_config() -> None:
    config = INTERNAL_IB_CONSISTENCY_QC
    assert config.capability_id == "internal_ib"
    assert config.slots[0].slot_id == "source"


def test_internal_csr_capability_config() -> None:
    config = INTERNAL_CSR_CONSISTENCY_QC
    assert config.capability_id == "internal_csr"
    assert config.slots[0].slot_id == "source"


def test_cross_capability_config_slot_order() -> None:
    config = DSUR_UPDATED_IB_CONSISTENCY_QC
    assert config.capability_id == "dsur_updated_ib"
    assert [slot.slot_id for slot in config.slots] == ["source_a", "source_b"]


def test_internal_capabilities_share_single_slot_topology() -> None:
    internal_shapes = [
        (
            config.capability_id,
            tuple(slot.slot_id for slot in config.slots),
        )
        for config in INTERNAL_CAPABILITY_CONFIGS
    ]
    assert len({shape[1] for shape in internal_shapes}) == 1
    assert internal_shapes[0][1] == ("source",)
    assert len({shape[0] for shape in internal_shapes}) == 3


def test_cross_slots_differ_only_by_slot_id() -> None:
    cross_slots = DSUR_UPDATED_IB_CONSISTENCY_QC.slots
    assert [slot.slot_id for slot in cross_slots] == ["source_a", "source_b"]
    assert len({field.name for field in fields(cross_slots[0])}) == 1


def test_one_configured_slot_one_intake_launch_extract(tmp_path: Path) -> None:
    assert SAMPLE_DOCX.is_file()
    sequence_calls = 0
    original_sequence = flow_module.run_document_processing_launch_extract

    def _count_sequence(**kwargs):
        nonlocal sequence_calls
        sequence_calls += 1
        return original_sequence(**kwargs)

    with patch.object(
        flow_module,
        "run_document_processing_launch_extract",
        side_effect=_count_sequence,
    ):
        report = _run_flow(
            capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
            uploads={"source": SAMPLE_DOCX},
            project_root=tmp_path,
        )

    assert sequence_calls == 1
    slot = report.result.slots[0]
    assert isinstance(slot.extract_report.result.document, ExtractDocumentResult)
    assert slot.admitted_source.file_hash
    assert slot.admitted_source.original_file_name


def test_two_configured_slots_two_independent_lifecycles(tmp_path: Path) -> None:
    assert SAMPLE_DOCX.is_file()
    assert SECOND_SAMPLE_DOCX.is_file()
    sequence_calls = 0
    original_sequence = flow_module.run_document_processing_launch_extract

    def _count_sequence(**kwargs):
        nonlocal sequence_calls
        sequence_calls += 1
        return original_sequence(**kwargs)

    with patch.object(
        flow_module,
        "run_document_processing_launch_extract",
        side_effect=_count_sequence,
    ):
        _run_flow(
            capability_config=DSUR_UPDATED_IB_CONSISTENCY_QC,
            uploads={
                "source_a": SAMPLE_DOCX,
                "source_b": SECOND_SAMPLE_DOCX,
            },
            project_root=tmp_path,
        )

    assert sequence_calls == 2


def _invoke_flow_with_raw_uploads(
    *,
    capability_config: DocumentConsistencyQcCapabilityConfig,
    uploads: dict[str, Path | str | object],
    project_root: Path,
) -> None:
    registry = PrepareAnalysisConfigRegistry()
    register_current_clinical_prepare_analysis_config(registry)
    flow_module.run_document_consistency_qc_flow(
        project_root=project_root,
        capability_config=capability_config,
        uploads=uploads,
        participant_inputs={
            slot_id: DocumentConsistencyQcParticipantRunInput(
                prepare_analysis_request_options=PrepareAnalysisRequestOptions(
                    ClinicalPreparePrivacyConfig.identity()
                ),
            )
            for slot_id in uploads
        },
        prepare_analysis_config_registry=registry,
        git_provenance=_git_prov(),
        **clinical_flow_invocation_kwargs(),
    )


@pytest.mark.parametrize(
    ("raw_uploads", "match"),
    [
        ({"source_a": Path("b.docx")}, "missing upload"),
        ({"source_a": Path("a.docx"), "source_b": ""}, "DocumentIntakeSourceBinding"),
        ({"source_a": "", "source_b": Path("b.docx")}, "DocumentIntakeSourceBinding"),
    ],
)
def test_flow_rejects_invalid_upload_binding_before_intake(
    raw_uploads,
    match: str,
) -> None:
    sequence_calls = 0

    def _fake_sequence(**kwargs):
        nonlocal sequence_calls
        sequence_calls += 1
        raise AssertionError("Launch should not run for invalid upload binding")

    with patch.object(
        flow_module,
        "run_document_processing_launch_extract",
        side_effect=_fake_sequence,
    ):
        with pytest.raises((ValueError, TypeError), match=match):
            _invoke_flow_with_raw_uploads(
                capability_config=DSUR_UPDATED_IB_CONSISTENCY_QC,
                uploads=raw_uploads,
                project_root=Path("."),
            )
    assert sequence_calls == 0


def test_flow_rejects_unexpected_upload_slot_id() -> None:
    with pytest.raises(ValueError, match="unexpected upload slot id"):
        _invoke_flow_with_raw_uploads(
            capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
            uploads={"source": Path("a.docx"), "extra": Path("b.docx")},
            project_root=Path("."),
        )


def test_flow_rejects_duplicate_configured_slot_ids() -> None:
    duplicate_config = DocumentConsistencyQcCapabilityConfig(
        capability_id="test_duplicate_slots",
        slots=(
            DocumentConsistencyQcParticipantSlot(
                slot_id="source",
            ),
            DocumentConsistencyQcParticipantSlot(
                slot_id="source",
            ),
        ),
    )
    with pytest.raises(ValueError, match="duplicate slot_id"):
        _invoke_flow_with_raw_uploads(
            capability_config=duplicate_config,
            uploads={"source": Path("a.docx")},
            project_root=Path("."),
        )


def test_flow_executes_in_capability_slot_order(tmp_path: Path) -> None:
    assert SAMPLE_DOCX.is_file()
    assert SECOND_SAMPLE_DOCX.is_file()
    report = _run_flow(
        capability_config=DSUR_UPDATED_IB_CONSISTENCY_QC,
        uploads={
            "source_b": SECOND_SAMPLE_DOCX,
            "source_a": SAMPLE_DOCX,
        },
        project_root=tmp_path,
    )
    slot_ids = [slot.slot_id for slot in report.result.slots]
    assert slot_ids == ["source_a", "source_b"]
    assert report.result.slots[0].admitted_source.source_path.resolve() == SAMPLE_DOCX.resolve()
    assert (
        report.result.slots[1].admitted_source.source_path.resolve()
        == SECOND_SAMPLE_DOCX.resolve()
    )


def test_extract_receives_extract_config_id_from_application_binding(
    tmp_path: Path,
) -> None:
    assert SAMPLE_DOCX.is_file()
    seen_config_ids: list[str] = []
    original_sequence = flow_module.run_document_processing_launch_extract

    def _capture_sequence(**kwargs):
        seen_config_ids.append(kwargs["extract_config_id"])
        return original_sequence(**kwargs)

    with patch.object(
        flow_module,
        "run_document_processing_launch_extract",
        side_effect=_capture_sequence,
    ):
        _run_flow(
            capability_config=DSUR_UPDATED_IB_CONSISTENCY_QC,
            uploads={
                "source_a": SAMPLE_DOCX,
                "source_b": SECOND_SAMPLE_DOCX,
            },
            project_root=tmp_path,
        )

    assert seen_config_ids == ["docx", "docx"]


def test_flow_signature_has_no_flow_wide_extract_config_or_participants() -> None:
    source = FLOW_PATH.read_text(encoding="utf-8")
    assert "ConsistencyQcParticipantInput" not in source
    flow_sig = source.split("def run_document_consistency_qc_flow", 1)[1].split(")", 1)[0]
    assert "participants:" not in flow_sig
    assert "intake_output_dir" not in flow_sig
    assert "extract_output_dir" not in flow_sig
    assert "extract_config_id: str" not in flow_sig


def test_cross_same_bytes_two_slots_preserved(tmp_path: Path) -> None:
    assert SAMPLE_DOCX.is_file()
    first = tmp_path / "dsur.docx"
    second = tmp_path / "updated_ib.docx"
    shared = SAMPLE_DOCX.read_bytes()
    first.write_bytes(shared)
    second.write_bytes(shared)
    expected_hash = compute_content_hash(shared)

    report = _run_flow(
        capability_config=DSUR_UPDATED_IB_CONSISTENCY_QC,
        uploads={"source_a": first, "source_b": second},
        project_root=tmp_path,
    )

    assert len(report.result.slots) == 2
    hashes = [
        slot.admitted_source.file_hash
        for slot in report.result.slots
    ]
    assert hashes == [expected_hash, expected_hash]
    slot_ids = {slot.slot_id for slot in report.result.slots}
    assert slot_ids == {"source_a", "source_b"}
    assert (
        report.result.slots[0].extract_report.result.document.identity.doc_id
        != report.result.slots[1].extract_report.result.document.identity.doc_id
    )


def test_cross_identical_bytes_distinct_doc_ids_and_extract_run_ids(tmp_path: Path) -> None:
    assert SAMPLE_DOCX.is_file()
    first = tmp_path / "dsur.docx"
    second = tmp_path / "updated_ib.docx"
    shared = SAMPLE_DOCX.read_bytes()
    first.write_bytes(shared)
    second.write_bytes(shared)

    report = _run_flow(
        capability_config=DSUR_UPDATED_IB_CONSISTENCY_QC,
        uploads={"source_a": first, "source_b": second},
        project_root=tmp_path,
    )

    doc_ids = [
        slot.extract_report.result.document.identity.doc_id for slot in report.result.slots
    ]
    extract_run_ids = [slot.extract_report.result.run_id for slot in report.result.slots]
    assert len(set(doc_ids)) == 2
    assert len(set(extract_run_ids)) == 2


@pytest.mark.parametrize("capability_config", INTERNAL_CAPABILITY_CONFIGS)
def test_one_source_one_identity_one_extract_result(
    tmp_path: Path,
    capability_config: DocumentConsistencyQcCapabilityConfig,
) -> None:
    assert SAMPLE_DOCX.is_file()
    report = _run_flow(
        capability_config=capability_config,
        uploads={"source": SAMPLE_DOCX},
        project_root=tmp_path,
    )
    slot = report.result.slots[0]
    doc_result = slot.extract_report.result.document
    assert doc_result.identity.doc_id == doc_result.bundle.doc_id
    assert doc_result.identity.file_hash == slot.admitted_source.file_hash


@pytest.mark.parametrize("capability_config", INTERNAL_CAPABILITY_CONFIGS)
def test_identity_reuses_intake_file_hash(
    tmp_path: Path,
    capability_config: DocumentConsistencyQcCapabilityConfig,
) -> None:
    assert SAMPLE_DOCX.is_file()
    source = tmp_path / "one.docx"
    content = SAMPLE_DOCX.read_bytes()
    source.write_bytes(content)
    expected_hash = compute_content_hash(content)

    report = _run_flow(
        capability_config=capability_config,
        uploads={"source": source},
        project_root=tmp_path,
    )
    identity = report.result.slots[0].extract_report.result.document.identity
    assert identity.file_hash == expected_hash


@patch("core.document.doc_identity.compute_file_hash")
@pytest.mark.parametrize("capability_config", INTERNAL_CAPABILITY_CONFIGS)
def test_flow_does_not_recompute_file_hash_after_intake(
    mock_file_hash,
    tmp_path: Path,
    capability_config: DocumentConsistencyQcCapabilityConfig,
) -> None:
    assert SAMPLE_DOCX.is_file()
    source = tmp_path / "one.docx"
    source.write_bytes(SAMPLE_DOCX.read_bytes())

    _run_flow(
        capability_config=capability_config,
        uploads={"source": source},
        project_root=tmp_path,
    )

    mock_file_hash.assert_not_called()


@pytest.mark.parametrize("capability_config", INTERNAL_CAPABILITY_CONFIGS)
def test_original_file_name_from_intake_not_path(
    tmp_path: Path,
    capability_config: DocumentConsistencyQcCapabilityConfig,
) -> None:
    assert SAMPLE_DOCX.is_file()
    source = tmp_path / "uploaded_name.docx"
    source.write_bytes(SAMPLE_DOCX.read_bytes())

    report = _run_flow(
        capability_config=capability_config,
        uploads={"source": source},
        project_root=tmp_path,
    )
    slot = report.result.slots[0]
    identity = slot.extract_report.result.document.identity
    assert slot.admitted_source.original_file_name == "uploaded_name.docx"
    assert identity.file_name == "uploaded_name.docx"


@pytest.mark.parametrize("capability_config", INTERNAL_CAPABILITY_CONFIGS)
def test_source_path_from_binding(
    tmp_path: Path,
    capability_config: DocumentConsistencyQcCapabilityConfig,
) -> None:
    assert SAMPLE_DOCX.is_file()
    source = tmp_path / "bound.docx"
    source.write_bytes(SAMPLE_DOCX.read_bytes())

    report = _run_flow(
        capability_config=capability_config,
        uploads={"source": source},
        project_root=tmp_path,
    )
    slot = report.result.slots[0]
    doc_result = slot.extract_report.result.document
    assert slot.admitted_source.source_path == source.resolve()
    summary = __import__("runtime.io", fromlist=["load_json"]).load_json(
        doc_result.run_summary_path
    )
    assert summary["inputs"]["source_docx"] == source.resolve().as_posix()


@patch("runtime.document_processing_bootstrap.bootstrap_processing_identity_from_path")
@pytest.mark.parametrize("capability_config", INTERNAL_CAPABILITY_CONFIGS)
def test_flow_does_not_call_bootstrap(
    mock_bootstrap,
    tmp_path: Path,
    capability_config: DocumentConsistencyQcCapabilityConfig,
) -> None:
    assert SAMPLE_DOCX.is_file()
    source = tmp_path / "one.docx"
    source.write_bytes(SAMPLE_DOCX.read_bytes())
    _run_flow(
        capability_config=capability_config,
        uploads={"source": source},
        project_root=tmp_path,
    )
    mock_bootstrap.assert_not_called()


@pytest.mark.parametrize("capability_config", INTERNAL_CAPABILITY_CONFIGS)
def test_slot_result_exposes_reports_and_live_bundle(
    tmp_path: Path,
    capability_config: DocumentConsistencyQcCapabilityConfig,
) -> None:
    assert SAMPLE_DOCX.is_file()
    source = tmp_path / "one.docx"
    source.write_bytes(SAMPLE_DOCX.read_bytes())
    report = _run_flow(
        capability_config=capability_config,
        uploads={"source": source},
        project_root=tmp_path,
    )
    slot = report.result.slots[0]
    assert slot.admitted_source.file_hash
    doc_result = slot.extract_report.result.document
    assert doc_result.bundle.doc_id
    persisted = __import__("runtime.io", fromlist=["load_json"]).load_json(
        doc_result.bundle_path
    )
    assert persisted == asdict(doc_result.bundle)


@pytest.mark.parametrize("capability_config", INTERNAL_CAPABILITY_CONFIGS)
def test_admitted_source_binding_has_no_doc_id(
    tmp_path: Path,
    capability_config: DocumentConsistencyQcCapabilityConfig,
) -> None:
    assert SAMPLE_DOCX.is_file()
    report = _run_flow(
        capability_config=capability_config,
        uploads={"source": SAMPLE_DOCX},
        project_root=tmp_path,
    )
    binding = report.result.slots[0].admitted_source
    assert not hasattr(binding, "doc_id")


def test_document_processing_identity_has_no_processing_semantics() -> None:
    identity_fields = {field.name for field in fields(DocumentProcessingIdentity)}
    assert identity_fields == {
        "doc_id",
        "file_hash",
        "file_name",
        "display_name",
        "created_at",
    }


def test_flow_does_not_resolve_extract_strategy(tmp_path: Path) -> None:
    assert SAMPLE_DOCX.is_file()
    source = FLOW_PATH.read_text(encoding="utf-8")
    assert "resolve_extract_strategy" not in source

    with patch(
        "core.document.extract.strategies.resolve_extract_strategy",
        side_effect=AssertionError("Flow must not resolve Extract strategy"),
    ):
        _run_flow(
            capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
            uploads={"source": SAMPLE_DOCX},
            project_root=tmp_path,
        )


def test_generic_contracts_contain_no_clinical_literals() -> None:
    source = CONTRACTS_PATH.read_text(encoding="utf-8")
    for token in (
        "DocumentProcessingContext",
        "DocumentType",
        "Language",
        "comparison_relation",
        "DSUR",
        "IB",
        "CSR",
        "Literal",
    ):
        assert token not in source


def test_document_branch_module_removed() -> None:
    assert not DOCUMENT_BRANCH_PATH.is_file()
    assert not SINGLE_DOCUMENT_PATH.is_file()


def test_canonical_flow_module_exists() -> None:
    assert FLOW_PATH.is_file()
    assert CONTRACTS_PATH.is_file()
    assert callable(flow_module.run_document_consistency_qc_flow)


def test_flow_does_not_resolve_profiles_or_concrete_ids() -> None:
    for path in (FLOW_PATH, CONTRACTS_PATH):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imported.add(alias.name)
        forbidden_imports = (
            "plugins.clinical_trial_doc.consistency_qc.comparison_profiles",
            "plugins.clinical_trial_doc",
            "capability",
            "capability.clinical_trial_doc_consistency_qc",
            "plugins.clinical_trial_doc.evidence_source_preparation",
        )
        forbidden_tokens = (
            "AggregateEvidenceExecutionInput",
            "AggregateEvidenceExecution",
            "AggregateEvidenceSourcePreparationProcessor",
            "run_evidence_source_preparation(",
        )
        for module in imported:
            for forbidden in forbidden_imports:
                assert not (module == forbidden or module.startswith(forbidden + "."))
        for token in forbidden_tokens:
            assert token not in source, f"flow must not reference {token!r}"
        assert "dsur_updated_ib" not in source
        assert "processing_blocks" not in source
        for role_token in ("dsur", "updated_ib", "internal"):
            assert f'"{role_token}"' not in source
            assert f"'{role_token}'" not in source


def test_cross_capability_module_does_not_import_comparison_profiles() -> None:
    source = DSUR_UPDATED_IB_PATH.read_text(encoding="utf-8")
    assert "comparison_profiles" not in source
    assert "participant_roles" not in source


def test_flow_calls_singular_extract_without_list_wrapper() -> None:
    source = FLOW_PATH.read_text(encoding="utf-8")
    assert "documents=[" not in source
    assert "run_document_processing_launch_extract" in source
    assert "run_document_consistency_qc_flow" in source
    assert "LaunchedDocumentProcessing" not in source


def test_flow_uses_shared_intake_launch_extract_sequence() -> None:
    source = FLOW_PATH.read_text(encoding="utf-8")
    slot_fn = source.split("def _run_slot", 1)[1]
    seq_pos = slot_fn.index("run_document_processing_launch_extract")
    doc_meta_pos = slot_fn.index("run_doc_meta_stage")
    assert seq_pos < doc_meta_pos
    assert "run_request_file_intake_operation" not in slot_fn
    assert "launch_document_processing_from_intake" not in slot_fn
    assert "run_extract_operation" not in slot_fn


def test_doc_meta_receives_prepare_analysis_bundle_not_extract_bundle(
    tmp_path: Path,
) -> None:
    assert SAMPLE_DOCX.is_file()
    captured: list[dict[str, object]] = []
    original_doc_meta = flow_module.run_doc_meta_stage

    def capture_doc_meta(**kwargs):
        captured.append(kwargs)
        return original_doc_meta(**kwargs)

    with patch.object(flow_module, "run_doc_meta_stage", side_effect=capture_doc_meta):
        report = _run_flow(
            capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
            uploads={"source": SAMPLE_DOCX},
            project_root=tmp_path,
        )

    assert len(captured) == 1
    prepare_document = report.result.slots[0].prepare_analysis_report.documents[0]
    assert captured[0]["analysis_bundle"] is prepare_document.artifacts.analysis_bundle
    assert captured[0]["analysis_bundle"] is not prepare_document.source_bundle


def test_doc_meta_forwards_injected_profile_and_summary_builder(tmp_path: Path) -> None:
    assert SAMPLE_DOCX.is_file()
    profile = MetadataProfile(
        name="neutral.test",
        context=MetadataContextConfig(),
        doc_type_rules=[],
        field_rules=[],
    )
    summary_builder = lambda metadata_base: metadata_base
    captured: list[dict[str, object]] = []

    def capture_doc_meta(**kwargs):
        captured.append(kwargs)
        return {
            "output_dir": str(kwargs["output_dir"]),
            "doc_meta_bundle_path": str(kwargs["output_dir"]) + "/doc_meta_bundle.json",
            "document_context_preview_path": str(kwargs["output_dir"]) + "/preview.json",
            "run_summary_path": str(kwargs["output_dir"]) + "/run_summary.json",
        }

    invocation = clinical_flow_invocation_kwargs()
    registry = PrepareAnalysisConfigRegistry()
    register_current_clinical_prepare_analysis_config(registry)

    def fake_filter_stage(**kwargs):
        output_dir = Path(kwargs["invocation"].custom_output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        zone_bundle = output_dir / "zone_match_bundle.json"
        coverage_bundle = output_dir / "coverage_bundle.json"
        run_summary = output_dir / "run_summary.json"
        zone_bundle.write_text("{}", encoding="utf-8")
        coverage_bundle.write_text("{}", encoding="utf-8")
        run_summary.write_text("{}", encoding="utf-8")
        filter_profile = kwargs["profile"]
        return flow_module.FilterStageResult(
            output_dir=output_dir,
            run_id="filter_test",
            doc_id="doc_test",
            zone_key=filter_profile.zone_config_name,
            run_context=filter_profile.zone_config_name,
            zone_bundle_path=zone_bundle,
            coverage_bundle_path=coverage_bundle,
            zone_bundle_debug_path=None,
            run_summary_path=run_summary,
            bundle={},
            bundle_path=Path(kwargs["bundle_path"]),
        )

    def fake_projection_stage(**kwargs):
        output_dir = Path(kwargs["output_dir"])
        output_dir.mkdir(parents=True, exist_ok=True)
        bundle_path = output_dir / "filter_output_projection_bundle.json"
        bundle_path.write_text(
            json.dumps(
                {
                    "artifact_type": "filter_output_projection_bundle",
                    "schema_version": "0.2.0",
                    "filter_output_projection_bundle_id": f"test_{kwargs['filter_job_id']}",
                    "filter_job_id": kwargs["filter_job_id"],
                    "doc_id": "doc_test",
                    "file_hash": (
                        "sha256:0123456789abcdef0123456789abcdef"
                        "0123456789abcdef0123456789abcdef"
                    ),
                    "zone_key": "dsur_clinical_safety_zh",
                    "projected_sources": [],
                    "semantic_outcomes": [],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        run_summary = output_dir / "run_summary.json"
        run_summary.write_text("{}", encoding="utf-8")
        from operations.filter_output_projection.contracts import (
            FilterOutputProjectionStepResult,
        )
        from runtime.filter_output_projection_stage import (
            FilterOutputProjectionStageResult,
        )

        step_result = FilterOutputProjectionStepResult(
            filter_job_id=kwargs["filter_job_id"],
            doc_id="doc_test",
            file_hash=(
                "sha256:0123456789abcdef0123456789abcdef"
                "0123456789abcdef0123456789abcdef"
            ),
            zone_key="dsur_clinical_safety_zh",
        )
        return FilterOutputProjectionStageResult(
            output_dir=output_dir,
            run_id=kwargs.get("run_id") or "projection_test",
            filter_job_id=kwargs["filter_job_id"],
            doc_id="doc_test",
            zone_key="dsur_clinical_safety_zh",
            step_result=step_result,
            projection_bundle_path=bundle_path,
            run_summary_path=run_summary,
        )

    with (
        patch.object(flow_module, "run_doc_meta_stage", side_effect=capture_doc_meta),
        patch.object(flow_module, "run_filter_stage", side_effect=fake_filter_stage),
        patch.object(
            flow_module,
            "run_filter_output_projection_stage",
            side_effect=fake_projection_stage,
        ),
        patch.object(
            flow_module,
            "run_projected_source_route_from_projection_bundles",
            return_value=PersistedProjectionRouteStageOutcome(
                route_result=None,
                selected_projected_source_count=0,
                projection_bundle_count=1,
                projection_input_refs=(),
            ),
        ) as mock_route,
    ):
        flow_module.run_document_consistency_qc_flow(
            project_root=tmp_path,
            capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
            uploads={
                "source": admit_participant_source_binding(tmp_path, SAMPLE_DOCX),
            },
            participant_inputs={
                "source": DocumentConsistencyQcParticipantRunInput(
                    prepare_analysis_request_options=PrepareAnalysisRequestOptions(
                        ClinicalPreparePrivacyConfig.identity()
                    ),
                )
            },
            prepare_analysis_config_registry=registry,
            git_provenance=_git_prov(),
            doc_meta_profile=profile,
            doc_meta_summary_builder=summary_builder,
            **{
                key: value
                for key, value in invocation.items()
                if key not in {"doc_meta_profile", "doc_meta_summary_builder"}
            },
        )

    assert captured[0]["profile"] is profile
    assert captured[0]["build_summary"] is summary_builder
    mock_route.assert_called()


def test_doc_meta_slot_result_is_opaque_runtime_report(tmp_path: Path) -> None:
    assert SAMPLE_DOCX.is_file()
    fake_report = {
        "opaque_marker": "neutral-flow-only",
        "output_dir": "/tmp/doc_meta",
        "doc_meta_bundle_path": "/tmp/doc_meta/doc_meta_bundle.json",
        "document_context_preview_path": "/tmp/doc_meta/preview.json",
        "run_summary_path": "/tmp/doc_meta/run_summary.json",
    }
    with patch.object(flow_module, "run_doc_meta_stage", return_value=fake_report):
        report = _run_flow(
            capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
            uploads={"source": SAMPLE_DOCX},
            project_root=tmp_path,
        )

    slot = report.result.slots[0]
    assert slot.doc_meta_report == fake_report
    assert slot.doc_meta_report["opaque_marker"] == "neutral-flow-only"


def test_multi_slot_doc_meta_runs_independently(tmp_path: Path) -> None:
    assert SAMPLE_DOCX.is_file()
    assert SECOND_SAMPLE_DOCX.is_file()
    captured_dirs: list[str] = []
    original_doc_meta = flow_module.run_doc_meta_stage

    def capture_doc_meta(**kwargs):
        captured_dirs.append(str(kwargs["output_dir"]))
        return original_doc_meta(**kwargs)

    with patch.object(flow_module, "run_doc_meta_stage", side_effect=capture_doc_meta):
        report = _run_flow(
            capability_config=DSUR_UPDATED_IB_CONSISTENCY_QC,
            uploads={
                "source_a": SAMPLE_DOCX,
                "source_b": SECOND_SAMPLE_DOCX,
            },
            project_root=tmp_path,
        )

    flow_root = report.flow_run_summary_path.parent
    expected = {
        str((flow_root / "participants/source_a/doc_meta").resolve()),
        str((flow_root / "participants/source_b/doc_meta").resolve()),
    }
    assert set(captured_dirs) == expected
    assert len(report.result.slots) == 2
    assert all(slot.doc_meta_report for slot in report.result.slots)


def test_doc_meta_failure_preserves_prepare_provenance_and_partial_status(
    tmp_path: Path,
) -> None:
    assert SAMPLE_DOCX.is_file()
    with patch.object(
        flow_module,
        "run_doc_meta_stage",
        side_effect=RuntimeError("doc meta failed"),
    ):
        with pytest.raises(RuntimeError, match="doc meta failed"):
            _run_flow(
                capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
                uploads={"source": SAMPLE_DOCX},
                project_root=tmp_path,
            )

    flow_dirs = list((tmp_path / "runs" / "document_consistency_qc").iterdir())
    summary = load_json(flow_dirs[0] / "flow_run_summary.json")
    validate_flow_run_summary(summary)
    slot = summary["slots"][0]
    assert summary["status"] == "failed"
    assert slot["status"] == "partial"
    assert slot["prepare_analysis_run_id"]
    assert slot["analysis_bundle_path"]
    assert "doc_meta_output_dir" not in slot
    assert "doc_meta_bundle_path" not in slot


def test_processing_launch_creates_doc_id_from_intake(tmp_path: Path) -> None:
    from runtime.request_file_intake import run_request_file_intake_operation

    assert SAMPLE_DOCX.is_file()
    intake_report = run_request_file_intake_operation(
        project_root=tmp_path,
        source_file=SAMPLE_DOCX,
        git_provenance=_git_prov(),
    )
    launched = processing_launch_module.launch_document_processing_from_intake(intake_report)
    intake_hash = intake_report.result.request_file_intake_result["document"]["file_hash"]
    assert launched.identity.doc_id.startswith("doc_")
    assert launched.identity.file_hash == intake_hash
    assert launched.source_path == intake_report.result.source_binding.source_path


def test_processing_launch_module_owns_identity_builder() -> None:
    source = PROCESSING_LAUNCH_PATH.read_text(encoding="utf-8")
    assert "build_document_processing_identity" in source
    assert "document_type" not in source
    assert "extract_config_id" not in source


def test_processing_launch_under_execution_flow() -> None:
    assert PROCESSING_LAUNCH_PATH.is_file()
    assert PROCESSING_LAUNCH_PATH == EXECUTION_FLOW_ROOT / "processing_launch.py"


def test_installed_filter_job_bindings_match_product_topology() -> None:
    expected = {
        "internal_dsur": {
            "source": (
                "dsur_clinical_safety",
                "dsur_overview",
            ),
        },
        "internal_ib": {
            "source": (
                "ib_clinical_safety",
                "ib_overview",
            ),
        },
        "internal_csr": {
            "source": (
                "csr_clinical_safety",
                "csr_overview",
            ),
        },
        "dsur_updated_ib": {
            "source_a": (
                "dsur_clinical_safety",
                "dsur_overview",
            ),
            "source_b": (
                "ib_clinical_safety",
                "ib_overview",
            ),
        },
    }
    for config in ALL_CAPABILITY_CONFIGS:
        actual = {
            slot.slot_id: INSTALLED_CLINICAL_TRIAL_DOC_FILTER_JOB_BINDINGS[
                (config.capability_id, slot.slot_id)
            ]
            for slot in config.slots
        }
        assert actual == expected[config.capability_id]


@pytest.mark.parametrize("capability_config", INTERNAL_CAPABILITY_CONFIGS)
def test_flow_runs_two_filter_jobs_per_slot_in_declaration_order(
    tmp_path: Path,
    capability_config: DocumentConsistencyQcCapabilityConfig,
) -> None:
    assert SAMPLE_DOCX.is_file()
    seen_jobs: list[str] = []
    original_filter = flow_module.run_filter_stage

    def capture_filter(**kwargs):
        seen_jobs.append(kwargs["profile"].filter_job_id)
        return original_filter(**kwargs)

    with patch.object(flow_module, "run_filter_stage", side_effect=capture_filter):
        report = _run_flow(
            capability_config=capability_config,
            uploads={"source": SAMPLE_DOCX},
            project_root=tmp_path,
        )

    slot = report.result.slots[0]
    expected_jobs = INSTALLED_CLINICAL_TRIAL_DOC_FILTER_JOB_BINDINGS[
        (capability_config.capability_id, slot.slot_id)
    ]
    assert len(slot.filter_results) == 2
    assert tuple(job.filter_job_id for job in slot.filter_results) == expected_jobs
    assert seen_jobs == list(expected_jobs)


def test_filter_output_layout_uses_filter_job_id_not_zone_config_name(
    tmp_path: Path,
) -> None:
    assert SAMPLE_DOCX.is_file()
    report = _run_flow(
        capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
        uploads={"source": SAMPLE_DOCX},
        project_root=tmp_path,
    )
    flow_root = report.flow_run_summary_path.parent
    slot = report.result.slots[0]
    for job in slot.filter_results:
        expected = (
            flow_root
            / "participants"
            / "source"
            / "filter"
            / job.filter_job_id
        ).resolve()
        assert job.stage_result.output_dir.resolve() == expected
        assert job.stage_result.output_dir.name == job.filter_job_id
        assert job.zone_config_name.endswith("_zh")


def test_flow_summary_records_run_level_source_language_and_filter_jobs(
    tmp_path: Path,
) -> None:
    assert SAMPLE_DOCX.is_file()
    report = _run_flow(
        capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
        uploads={"source": SAMPLE_DOCX},
        project_root=tmp_path,
    )
    summary = load_json(report.flow_run_summary_path)
    validate_flow_run_summary(summary)
    assert summary["schema_version"] == "0.13.0"
    assert summary["source_language"] == "zh"
    slot = summary["slots"][0]
    assert slot["filter_job_ids"] == [
        "dsur_clinical_safety",
        "dsur_overview",
    ]
    assert len(slot["filter_jobs"]) == 2
    assert [job["filter_job_id"] for job in slot["filter_jobs"]] == slot[
        "filter_job_ids"
    ]
    assert all(job["source_language"] == "zh" for job in slot["filter_jobs"])
    assert all(job["zone_config_name"].endswith("_zh") for job in slot["filter_jobs"])


def test_unresolved_filter_variant_runs_zero_filter_runtime_calls(tmp_path: Path) -> None:
    assert SAMPLE_DOCX.is_file()
    from operations.filter.variant_registry import (
        resolve_filter_job_variant as real_resolve,
    )

    def fail_second_job(**kwargs):
        if kwargs["filter_job_id"] == "dsur_overview":
            raise ValueError("unsupported language variant for Filter job 'dsur_overview'")
        return real_resolve(**kwargs)

    invocation = clinical_flow_invocation_kwargs()
    registry = PrepareAnalysisConfigRegistry()
    register_current_clinical_prepare_analysis_config(registry)
    admitted_source = admit_participant_source_binding(tmp_path, SAMPLE_DOCX)
    with (
        patch.object(flow_module, "resolve_filter_job_variant", side_effect=fail_second_job),
        patch.object(flow_module, "run_filter_stage") as mock_filter,
    ):
        with pytest.raises(ValueError, match="unsupported language variant"):
            flow_module.run_document_consistency_qc_flow(
                project_root=tmp_path,
                capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
                uploads={"source": admitted_source},
                participant_inputs={
                    "source": DocumentConsistencyQcParticipantRunInput(
                        prepare_analysis_request_options=PrepareAnalysisRequestOptions(
                            ClinicalPreparePrivacyConfig.identity()
                        ),
                    )
                },
                prepare_analysis_config_registry=registry,
                **invocation,
            )

    mock_filter.assert_not_called()


def test_filter_runtime_failure_preserves_first_job_artifacts(tmp_path: Path) -> None:
    assert SAMPLE_DOCX.is_file()
    original_filter = flow_module.run_filter_stage
    call_count = 0

    def fail_second_runtime(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise RuntimeError("filter job 2 failed")
        return original_filter(**kwargs)

    with patch.object(flow_module, "run_filter_stage", side_effect=fail_second_runtime):
        with pytest.raises(RuntimeError, match="filter job 2 failed"):
            _run_flow(
                capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
                uploads={"source": SAMPLE_DOCX},
                project_root=tmp_path,
            )

    flow_dirs = list((tmp_path / "runs" / "document_consistency_qc").iterdir())
    summary = load_json(flow_dirs[0] / "flow_run_summary.json")
    slot = summary["slots"][0]
    assert slot["status"] == "partial"
    assert len(slot.get("filter_jobs", [])) == 1
    assert slot["filter_jobs"][0]["filter_job_id"] == "dsur_clinical_safety"


def test_flow_does_not_hardcode_source_language_in_source() -> None:
    source = FLOW_PATH.read_text(encoding="utf-8")
    assert 'source_language="zh"' not in source
    assert "source_language = \"zh\"" not in source


def test_execution_flow_production_source_has_no_concrete_business_ids() -> None:
    forbidden_tokens = (
        "dsur_updated_ib",
        "internal_dsur",
        "internal_ib",
        "internal_csr",
        "dsur_clinical_safety",
        "dsur_overview",
        "ib_clinical_safety",
        "ib_overview",
        "csr_clinical_safety",
        "csr_overview",
        '"zh"',
        "'zh'",
        '"en"',
        "'en'",
    )
    violations: list[str] = []
    for path in sorted(EXECUTION_FLOW_QC_ROOT.rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        for token in forbidden_tokens:
            if token in source:
                violations.append(f"{path.relative_to(BACKEND_ROOT)}: {token}")
    assert not violations, "concrete business ids in execution_flow:\n" + "\n".join(
        violations
    )


def test_no_production_import_of_capability_flow_package() -> None:
    backend_root = BACKEND_ROOT
    violations: list[str] = []
    for path in sorted(backend_root.rglob("*.py")):
        if path.parts[-2] == "tests":
            continue
        text = path.read_text(encoding="utf-8")
        if "capability_flow" in text:
            violations.append(str(path.relative_to(backend_root)))
    assert not violations, "stale capability_flow references:\n" + "\n".join(violations)
