"""S6 integration guards for Extract to canonical Prepare Analysis in Flow."""

from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import execution_flow.document_consistency_qc.flow as flow_module
import execution_flow.document_processing_sequence as sequence_module
from artifacts.prepare_analysis import PrepareAnalysisArtifactPaths
from capability import INTERNAL_IB_CONSISTENCY_QC
from execution_flow.document_consistency_qc.contracts import (
    DocumentConsistencyQcCapabilityConfig,
    DocumentConsistencyQcParticipantRunInput,
    DocumentConsistencyQcParticipantSlot,
)
from operations.prepare_analysis.contracts import (
    PrepareAnalysisConfigId,
    PrepareAnalysisRequestOptions,
)
from operations.prepare_analysis.registry import (
    PrepareAnalysisConfigRegistry,
    UnknownPrepareAnalysisConfigError,
)
from plugins.clinical_trial_doc.prepare_analysis.config import (
    CURRENT_CLINICAL_PREPARE_ANALYSIS_CONFIG_ID,
    register_current_clinical_prepare_analysis_config,
)
from plugins.clinical_trial_doc.prepare_analysis.inputs import (
    CLINICAL_REGEX_RULE_SET_ZH,
    ClinicalPreparePrivacyConfig,
)
from runtime.prepare_analysis import (
    PrepareAnalysisDocumentResult,
    PrepareAnalysisOperationReport,
)
from runtime.prepare_analysis.persistence import PrepareAnalysisArtifactPayloads
from tests.document_consistency_qc_flow_helpers import (
    admitted_source_bindings,
    clinical_flow_invocation_kwargs,
    synthetic_operation_bindings_for_capability,
)

SAMPLE_DOCX = (
    BACKEND_ROOT
    / "tests/fixtures/clinical_trial_doc/extract/ib_extract_minimal_001.docx"
)
SECOND_SAMPLE_DOCX = (
    BACKEND_ROOT
    / "tests/fixtures/clinical_trial_doc/tag_integration/ib_safety_tag_integration_001.docx"
)
FLOW_PATH = BACKEND_ROOT / "execution_flow/document_consistency_qc/flow.py"


def _registry(*, registered: bool = True) -> PrepareAnalysisConfigRegistry:
    registry = PrepareAnalysisConfigRegistry()
    if registered:
        register_current_clinical_prepare_analysis_config(registry)
    return registry


def _participant(
    *,
    privacy_config: ClinicalPreparePrivacyConfig | None = None,
) -> DocumentConsistencyQcParticipantRunInput:
    return DocumentConsistencyQcParticipantRunInput(
        prepare_analysis_request_options=PrepareAnalysisRequestOptions(
            privacy_config or ClinicalPreparePrivacyConfig.identity()
        ),
    )


FLOW_PATH = BACKEND_ROOT / "execution_flow/document_consistency_qc/flow.py"
FLOW_DEPS = clinical_flow_invocation_kwargs()


def _fake_prepare_report(kwargs: dict[str, object]) -> PrepareAnalysisOperationReport:
    execution = kwargs["execution"]
    output_dir = Path(execution.output_dir)  # type: ignore[attr-defined]
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = PrepareAnalysisArtifactPaths(
        analysis_bundle=output_dir / "analysis_bundle.json",
        block_manifest=output_dir / "block_manifest.json",
        run_summary=output_dir / "run_summary.json",
    )
    bundle_dict = dict(kwargs["bundle"])  # type: ignore[arg-type]
    analysis_bundle = {
        "doc_id": str(bundle_dict.get("doc_id") or "doc_fake"),
        "file_hash": str(bundle_dict.get("file_hash") or "sha256_" + "a" * 64),
        "content_blocks": list(bundle_dict.get("content_blocks") or []),
        "stage": "prepare_analysis",
    }
    paths.analysis_bundle.write_text(json.dumps(analysis_bundle), encoding="utf-8")
    paths.block_manifest.write_text('{"blocks":[]}', encoding="utf-8")
    paths.run_summary.write_text("{}", encoding="utf-8")
    artifacts = PrepareAnalysisArtifactPayloads(
        analysis_bundle=analysis_bundle,
        block_manifest={"blocks": []},
        privacy_audit=None,
        mapping=None,
        private_audit_bundle=None,
    )
    document = PrepareAnalysisDocumentResult(
        run_id=str(execution.run_id),  # type: ignore[attr-defined]
        source_bundle=bundle_dict,
        step_result=SimpleNamespace(),
        artifacts=artifacts,
        paths=paths,
        output_dir=output_dir,
    )
    return PrepareAnalysisOperationReport(
        status="success",
        documents=(document,),
        index_path=None,
        messages=(),
    )


def test_single_participant_runs_real_prepare_and_captures_child_refs(
    tmp_path: Path,
) -> None:
    report = flow_module.run_document_consistency_qc_flow(
        project_root=tmp_path,
        capability_config=INTERNAL_IB_CONSISTENCY_QC,
        uploads=admitted_source_bindings({"source": SAMPLE_DOCX}),
        participant_inputs={"source": _participant()},
        prepare_analysis_config_registry=_registry(),
        **FLOW_DEPS,
    )

    slot = report.result.slots[0]
    prepare = slot.prepare_analysis_report
    assert prepare.status == "success"
    assert len(prepare.documents) == 1
    document = prepare.documents[0]
    assert document.paths is not None
    assert document.paths.analysis_bundle.is_file()
    assert document.paths.block_manifest.is_file()
    assert document.paths.run_summary.is_file()
    assert (
        document.output_dir
        == (
            report.flow_run_summary_path.parent / "participants/source/prepare_analysis"
        ).resolve()
    )
    assert not (tmp_path / "runs/prepare_analysis").exists()

    summary = json.loads(report.flow_run_summary_path.read_text(encoding="utf-8"))
    record = summary["slots"][0]
    assert record["prepare_analysis_config_id"] == str(
        CURRENT_CLINICAL_PREPARE_ANALYSIS_CONFIG_ID
    )
    assert record["prepare_analysis_run_id"] == document.run_id
    assert record["analysis_bundle_path"] == document.paths.analysis_bundle.as_posix()
    assert record["block_manifest_path"] == document.paths.block_manifest.as_posix()
    assert record["prepare_analysis_run_summary_path"] == (
        document.paths.run_summary.as_posix()
    )


def test_multi_participant_forwards_formal_prepare_inputs_unchanged(
    tmp_path: Path,
) -> None:
    config_a = PrepareAnalysisConfigId("pacfg_flow_a")
    config_b = PrepareAnalysisConfigId("pacfg_flow_b")
    capability = DocumentConsistencyQcCapabilityConfig(
        capability_id="flow_routing_test",
        slots=(
            DocumentConsistencyQcParticipantSlot(slot_id="source_a"),
            DocumentConsistencyQcParticipantSlot(slot_id="source_b"),
        ),
    )
    routing_bindings = synthetic_operation_bindings_for_capability(
        capability,
        extract_config_id="docx",
        prepare_analysis_config_id=config_a,
        per_slot_prepare_analysis_config_ids={
            "source_a": config_a,
            "source_b": config_b,
        },
    )
    captured: list[dict[str, object]] = []

    def fake_prepare(**kwargs):
        captured.append(kwargs)
        return _fake_prepare_report(kwargs)

    participant_a = _participant()
    participant_b = _participant()
    with patch.object(
        flow_module,
        "run_prepare_analysis_operation",
        side_effect=fake_prepare,
    ):
        report = flow_module.run_document_consistency_qc_flow(
            project_root=tmp_path,
            capability_config=capability,
            uploads=admitted_source_bindings(
                {"source_a": SAMPLE_DOCX, "source_b": SECOND_SAMPLE_DOCX}
            ),
            participant_inputs={
                "source_a": participant_a,
                "source_b": participant_b,
            },
            prepare_analysis_config_registry=_registry(registered=False),
            **{**FLOW_DEPS, **routing_bindings},
        )

    assert len(captured) == 2
    assert [call["prepare_analysis_config_id"] for call in captured] == [
        config_a,
        config_b,
    ]
    assert [call["request_options"] for call in captured] == [
        participant_a.prepare_analysis_request_options,
        participant_b.prepare_analysis_request_options,
    ]
    assert [slot.slot_id for slot in report.result.slots] == ["source_a", "source_b"]
    assert all(
        slot.prepare_analysis_report.documents[0].paths.analysis_bundle.is_file()
        for slot in report.result.slots
    )


def test_document_language_does_not_change_privacy_selector(tmp_path: Path) -> None:
    captured_options: list[PrepareAnalysisRequestOptions] = []
    real_extract = sequence_module.run_extract_operation

    def extract_with_language(**kwargs):
        report = real_extract(**kwargs)
        bundle = replace(
            report.result.document.bundle,
            document_meta={"language": "zh"},
        )
        document = replace(report.result.document, bundle=bundle)
        return replace(report, result=replace(report.result, document=document))

    def fake_prepare(**kwargs):
        captured_options.append(kwargs["request_options"])
        return _fake_prepare_report(kwargs)

    with (
        patch.object(
            sequence_module,
            "run_extract_operation",
            side_effect=extract_with_language,
        ),
        patch.object(
            flow_module,
            "run_prepare_analysis_operation",
            side_effect=fake_prepare,
        ),
    ):
        participant = _participant(
            privacy_config=ClinicalPreparePrivacyConfig(
                enabled=True,
                registry_enabled=False,
                regex_rule_set_ref=CLINICAL_REGEX_RULE_SET_ZH,
                uie_config_ref=None,
                date_shift_enabled=False,
            )
        )
        flow_module.run_document_consistency_qc_flow(
            project_root=tmp_path,
            capability_config=INTERNAL_IB_CONSISTENCY_QC,
            uploads=admitted_source_bindings({"source": SAMPLE_DOCX}),
            participant_inputs={"source": participant},
            prepare_analysis_config_registry=_registry(),
            **{
                **FLOW_DEPS,
                "filter_job_bindings": {
                    (INTERNAL_IB_CONSISTENCY_QC.capability_id, "source"): ()
                },
            },
        )

    assert captured_options == [participant.prepare_analysis_request_options]
    assert (
        captured_options[0].privacy_config.regex_rule_set_ref
        == CLINICAL_REGEX_RULE_SET_ZH
    )


def test_extract_failure_prevents_prepare(tmp_path: Path) -> None:
    with (
        patch.object(
            sequence_module,
            "run_extract_operation",
            side_effect=RuntimeError("extract failed"),
        ),
        patch.object(flow_module, "run_prepare_analysis_operation") as prepare,
        pytest.raises(RuntimeError, match="extract failed"),
    ):
        flow_module.run_document_consistency_qc_flow(
            project_root=tmp_path,
            capability_config=INTERNAL_IB_CONSISTENCY_QC,
            uploads=admitted_source_bindings({"source": SAMPLE_DOCX}),
            participant_inputs={"source": _participant()},
            prepare_analysis_config_registry=_registry(),
            **FLOW_DEPS,
        )
    prepare.assert_not_called()


def test_unknown_prepare_config_fails_flow_without_false_result_refs(
    tmp_path: Path,
) -> None:
    with pytest.raises(UnknownPrepareAnalysisConfigError):
        flow_module.run_document_consistency_qc_flow(
            project_root=tmp_path,
            capability_config=INTERNAL_IB_CONSISTENCY_QC,
            uploads=admitted_source_bindings({"source": SAMPLE_DOCX}),
            participant_inputs={"source": _participant()},
            prepare_analysis_config_registry=_registry(registered=False),
            **FLOW_DEPS,
        )

    flow_root = next((tmp_path / "runs/document_consistency_qc").iterdir())
    summary = json.loads(
        (flow_root / "flow_run_summary.json").read_text(encoding="utf-8")
    )
    assert summary["status"] == "failed"
    record = summary["slots"][0]
    assert record["status"] == "partial"
    assert record["prepare_analysis_run_id"] == "prepare_analysis_source"
    assert "analysis_bundle_path" not in record
    assert (flow_root / "participants/source/prepare_analysis/failure.json").is_file()


def test_missing_participant_run_input_fails_before_child_operations(
    tmp_path: Path,
) -> None:
    with (
        patch.object(flow_module, "run_document_processing_launch_extract") as sequence,
        pytest.raises(ValueError, match="missing participant run input"),
    ):
        flow_module.run_document_consistency_qc_flow(
            project_root=tmp_path,
            capability_config=INTERNAL_IB_CONSISTENCY_QC,
            uploads=admitted_source_bindings({"source": SAMPLE_DOCX}),
            participant_inputs={},
            prepare_analysis_config_registry=_registry(),
            **FLOW_DEPS,
        )
    sequence.assert_not_called()


def test_participant_run_input_requires_formal_prepare_contracts() -> None:
    with pytest.raises(TypeError, match="prepare_analysis_request_options"):
        DocumentConsistencyQcParticipantRunInput(
            prepare_analysis_request_options=object(),  # type: ignore[arg-type]
        )


def test_prepare_execution_failure_fails_flow_without_success_refs(
    tmp_path: Path,
) -> None:
    with (
        patch.object(
            flow_module,
            "run_prepare_analysis_operation",
            side_effect=RuntimeError("prepare execution failed"),
        ),
        pytest.raises(RuntimeError, match="prepare execution failed"),
    ):
        flow_module.run_document_consistency_qc_flow(
            project_root=tmp_path,
            capability_config=INTERNAL_IB_CONSISTENCY_QC,
            uploads=admitted_source_bindings({"source": SAMPLE_DOCX}),
            participant_inputs={"source": _participant()},
            prepare_analysis_config_registry=_registry(),
            **FLOW_DEPS,
        )

    flow_root = next((tmp_path / "runs/document_consistency_qc").iterdir())
    summary = json.loads(
        (flow_root / "flow_run_summary.json").read_text(encoding="utf-8")
    )
    assert summary["status"] == "failed"
    record = summary["slots"][0]
    assert record["prepare_analysis_run_id"] == "prepare_analysis_source"
    assert "analysis_bundle_path" not in record
    assert "block_manifest_path" not in record


def test_flow_source_keeps_prepare_semantics_outside_flow() -> None:
    source = FLOW_PATH.read_text(encoding="utf-8")
    assert "plugins.clinical_trial_doc" not in source
    assert "prepare_analysis.standalone" not in source
    assert "CURRENT_CLINICAL_PREPARE_ANALYSIS_CONFIG_ID" not in source
    assert "steps.prepare_analysis" not in source
    assert "prepare_analysis_bundle" not in source
    assert "ClinicalProgramRecord" not in source
    assert "export_clinical_registry_entries" not in source
    assert "date_shift" not in source
    assert "regex" not in source.lower()
    assert "uie" not in source.lower()
