"""Tests for scripts/run_consistency_qc.py."""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from application import build_installed_document_consistency_qc_application_composition
from application.clinical_trial_doc_consistency_qc import (
    resume_installed_clinical_trial_document_consistency_qc,
)
from application.clinical_trial_doc_consistency_qc.capabilities import (
    INSTALLED_CLINICAL_TRIAL_DOC_CONSISTENCY_QC_CAPABILITIES,
)
from application.document_consistency_qc.execution_request import (
    DocumentConsistencyQcExecutionRequest,
)
from application.document_consistency_qc.resume_request import (
    DocumentConsistencyQcResumeRequest,
)
from artifacts.document_consistency_qc_flow_run_summary import (
    FLOW_STATUS_PAUSED_AT_CANDIDATE_SCOPE,
)
from capability import (
    DSUR_UPDATED_IB_CONSISTENCY_QC,
    INTERNAL_DSUR_CONSISTENCY_QC,
)
from core.document.doc_identity import DocumentProcessingIdentity
from core.document.document_schema import DocumentBundle
from execution_flow.document_consistency_qc import (
    CandidateScopeDecisionMode,
    DocumentConsistencyQcFlowReport,
    DocumentConsistencyQcFlowResult,
    DocumentConsistencyQcSlotResult,
)
from execution_flow.document_consistency_qc.candidate_scope_checkpoint import (
    automatic_candidate_scope_selections,
)
from execution_flow.document_consistency_qc.flow_loader import load_flow_run_execution
from operations.evidence_comparison.stage import (
    EvidenceComparisonStageResult,
)
from runtime.document_source_binding import DocumentIntakeSourceBinding
from runtime.extract.operations import (
    ExtractDocumentResult,
    ExtractOperationReport,
    ExtractOperationResult,
)
from runtime.prepare_analysis import PrepareAnalysisOperationReport
from runtime.request_file_intake.operations import (
    RequestFileIntakeOperationReport,
    RequestFileIntakeOperationResult,
)
from scripts import run_consistency_qc
from tests.candidate_scope_isolation import (
    SHOWCASE_DOCX,
    bridge_test_resume_dependencies,
)

RUN_CONSISTENCY_QC_PATH = BACKEND_ROOT / "scripts" / "run_consistency_qc.py"
INSTALLED_PREPARE_PATCH = (
    "scripts.run_consistency_qc.prepare_and_allocate_installed_clinical_trial_document_consistency_qc"
)


@contextmanager
def _patch_installed_execution():
    with (
        patch(INSTALLED_PREPARE_PATCH) as mock_prepare,
        patch(
            "scripts.run_consistency_qc.execute_prepared_installed_clinical_trial_document_consistency_qc"
        ) as mock_execute,
    ):
        mock_execute.side_effect = lambda prepared: mock_prepare.return_value
        yield mock_prepare


def _stub_application_result(
    report: DocumentConsistencyQcFlowReport,
):
    from application.document_consistency_qc.document_type_result import (
        DocumentConsistencyQcApplicationResult,
    )

    return DocumentConsistencyQcApplicationResult(flow_report=report, slots=())


def test_canonical_runner_importable_from_scripts_namespace() -> None:
    from scripts import run_consistency_qc as canonical_runner

    assert callable(canonical_runner.main)
    assert not hasattr(canonical_runner, "run_consistency_qc")


def test_legacy_dev_runner_executable_removed() -> None:
    legacy_path = BACKEND_ROOT / "scripts" / "dev" / "run_consistency_qc.py"
    assert not legacy_path.is_file()


def test_default_project_root_resolves_to_backend_directory() -> None:
    assert run_consistency_qc.DEFAULT_PROJECT_ROOT == BACKEND_ROOT


def test_direct_entry_help_smoke() -> None:
    result = subprocess.run(
        [sys.executable, str(RUN_CONSISTENCY_QC_PATH), "--help"],
        cwd=BACKEND_ROOT.parent,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "--capability" in result.stdout
    assert "--source-a" in result.stdout
    assert "--candidate-scope-mode" in result.stdout
    assert "prepare-context" not in result.stdout
    assert "--llm " not in result.stdout
    assert "--llm-profile" not in result.stdout
    assert "--thinking" not in result.stdout
    assert "--no-thinking" not in result.stdout
    assert "Filter Output Projection" in result.stdout
    assert "Route" in result.stdout
    assert "Evidence Comparison" in result.stdout


@pytest.mark.parametrize(
    ("mode_args", "expected_mode"),
    [
        ((), CandidateScopeDecisionMode.AUTOMATIC_CONTINUE),
        (
            ("--candidate-scope-mode", "automatic_continue"),
            CandidateScopeDecisionMode.AUTOMATIC_CONTINUE,
        ),
        (
            ("--candidate-scope-mode", "pause_at_candidate_scope"),
            CandidateScopeDecisionMode.PAUSE_AT_CANDIDATE_SCOPE,
        ),
    ],
)
def test_cli_explicitly_passes_candidate_scope_mode_to_execution_request(
    tmp_path: Path,
    mode_args: tuple[str, ...],
    expected_mode: CandidateScopeDecisionMode,
) -> None:
    source = tmp_path / "sample.docx"
    source.write_bytes(b"doc")
    mock_report = _flow_report(
        capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
        uploads={"source": source},
        tmp_path=tmp_path,
    )
    captured_kwargs: dict[str, object] = {}

    def _capture_request(**kwargs):
        captured_kwargs.update(kwargs)
        return DocumentConsistencyQcExecutionRequest(**kwargs)

    with (
        patch.object(
            run_consistency_qc,
            "DocumentConsistencyQcExecutionRequest",
            side_effect=_capture_request,
        ),
        _patch_installed_execution() as mock_execute,
    ):
        mock_execute.return_value = _stub_application_result(mock_report)
        run_consistency_qc.main(
            [
                "--capability",
                "internal_dsur",
                "--source",
                str(source),
                "--project-root",
                str(tmp_path),
                *mode_args,
            ]
        )

    assert captured_kwargs["candidate_scope_decision_mode"] is expected_mode


def test_cli_rejects_invalid_candidate_scope_mode(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit, match="2"):
        run_consistency_qc._parse_args(
            INSTALLED_CLINICAL_TRIAL_DOC_CONSISTENCY_QC_CAPABILITIES,
            [
                "--capability",
                "internal_dsur",
                "--candidate-scope-mode",
                "invalid",
            ],
        )

    assert "invalid choice" in capsys.readouterr().err


def _write_privacy_config(
    tmp_path: Path,
    suffix: str,
    *,
    enabled: bool = False,
    registry_enabled: bool = False,
    clinical_program_id: str | None = None,
) -> Path:
    privacy_path = tmp_path / f"privacy_{suffix}.json"
    payload: dict[str, object] = {
        "schema_version": "1",
        "enabled": enabled,
        "registry_enabled": registry_enabled,
        "regex_rule_set_ref": None,
        "uie_config_ref": None,
        "date_shift_enabled": False,
    }
    if clinical_program_id is not None:
        payload["clinical_program_id"] = clinical_program_id
    privacy_path.write_text(json.dumps(payload), encoding="utf-8")
    return privacy_path


def _identity(*, doc_id: str, file_hash: str) -> DocumentProcessingIdentity:
    return DocumentProcessingIdentity(
        doc_id=doc_id,
        file_hash=file_hash,
        file_name=f"{doc_id}.docx",
        display_name=doc_id,
        created_at="2026-01-01T00:00:00Z",
    )


def _bundle(*, doc_id: str, file_hash: str) -> DocumentBundle:
    return DocumentBundle(
        doc_id=doc_id,
        file_name=f"{doc_id}.docx",
        display_name=doc_id,
        file_hash=file_hash,
        source_type="docx",
    )


def _intake_report(
    *,
    run_id: str,
    file_hash: str,
    source_path: Path,
    output_dir: Path,
) -> RequestFileIntakeOperationReport:
    return RequestFileIntakeOperationReport(
        result=RequestFileIntakeOperationResult(
            run_id=run_id,
            output_dir=output_dir,
            request_file_intake_result={
                "document": {
                    "file_hash": file_hash,
                    "original_file_name": source_path.name,
                }
            },
            source_binding=DocumentIntakeSourceBinding(
                file_hash=file_hash,
                original_file_name=source_path.name,
                source_path=source_path,
            ),
            request_file_intake_result_path=output_dir
            / "request_file_intake_result.json",
            run_summary_path=output_dir / "run_summary.json",
            index_path=None,
        ),
        messages=(),
    )


def _extract_report(
    *,
    run_id: str,
    doc_id: str,
    file_hash: str,
    output_dir: Path,
) -> ExtractOperationReport:
    identity = _identity(doc_id=doc_id, file_hash=file_hash)
    doc_out = output_dir / doc_id
    doc_out.mkdir(parents=True, exist_ok=True)
    bundle_path = doc_out / "bundle.json"
    bundle_path.write_text("{}", encoding="utf-8")
    return ExtractOperationReport(
        result=ExtractOperationResult(
            run_id=run_id,
            output_dir=output_dir,
            document=ExtractDocumentResult(
                identity=identity,
                bundle=_bundle(doc_id=doc_id, file_hash=file_hash),
                output_dir=doc_out,
                bundle_path=bundle_path,
                run_summary_path=doc_out / "run_summary.json",
            ),
            index_path=output_dir / "index.json",
        ),
        messages=(),
    )


def _flow_report(
    *,
    capability_config,
    uploads: dict[str, Path],
    tmp_path: Path,
) -> DocumentConsistencyQcFlowReport:
    slots = []
    for slot in capability_config.slots:
        source = uploads[slot.slot_id]
        slots.append(
            DocumentConsistencyQcSlotResult(
                slot_id=slot.slot_id,
                admitted_source=DocumentIntakeSourceBinding(
                    file_hash=f"sha256:{slot.slot_id}",
                    original_file_name=source.name,
                    source_path=source,
                ),
                extract_report=_extract_report(
                    run_id=f"extract_{slot.slot_id}",
                    doc_id=f"doc_{slot.slot_id}",
                    file_hash=f"sha256:{slot.slot_id}",
                    output_dir=tmp_path / "extract" / slot.slot_id,
                ),
                prepare_analysis_report=PrepareAnalysisOperationReport(
                    status="success",
                    documents=(
                        SimpleNamespace(
                            run_id=f"prepare_analysis_{slot.slot_id}",
                            paths=None,
                        ),
                    ),
                    index_path=None,
                    messages=(),
                ),
                doc_meta_report={
                    "output_dir": str(tmp_path / "doc_meta" / slot.slot_id),
                    "doc_meta_bundle": {"warnings": []},
                    "doc_meta_bundle_path": str(
                        tmp_path / "doc_meta" / slot.slot_id / "doc_meta_bundle.json"
                    ),
                    "document_context_preview_path": str(
                        tmp_path / "doc_meta" / slot.slot_id / "preview.json"
                    ),
                    "run_summary_path": str(
                        tmp_path / "doc_meta" / slot.slot_id / "run_summary.json"
                    ),
                },
                filter_results=(),
            )
        )
    return DocumentConsistencyQcFlowReport(
        result=DocumentConsistencyQcFlowResult(slots=tuple(slots)),
        messages=(),
        flow_run_id="document_consistency_qc_20260101_000000_000000Z",
        flow_run_summary_path=tmp_path
        / "runs"
        / "document_consistency_qc"
        / "20260101_000000_000000Z"
        / "flow_run_summary.json",
    )


def _parse(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _imported_module_names(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


@pytest.mark.parametrize(
    "capability",
    [
        "internal_dsur",
        "internal_ib",
        "internal_csr",
    ],
)
def test_internal_capability_calls_flow_with_upload_mapping(
    tmp_path: Path,
    capability: str,
) -> None:
    source = tmp_path / "sample.docx"
    source.write_bytes(b"doc")
    capability_config = INSTALLED_CLINICAL_TRIAL_DOC_CONSISTENCY_QC_CAPABILITIES[
        capability
    ]
    mock_report = _flow_report(
        capability_config=capability_config,
        uploads={"source": source},
        tmp_path=tmp_path,
    )
    privacy_path = _write_privacy_config(tmp_path, "001")

    with _patch_installed_execution() as mock_execute:
        mock_execute.return_value = _stub_application_result(mock_report)
        run_consistency_qc.main(
            [
                "--capability",
                capability,
                "--source",
                str(source),
                "--privacy-config",
                str(privacy_path),
                "--project-root",
                str(tmp_path),
            ]
        )
        mock_execute.assert_called_once()
        request = mock_execute.call_args.kwargs["request"]
        assert request.project_root == tmp_path
        assert request.capability_id == capability
        binding = request.participant_inputs["source"]
        assert isinstance(binding, DocumentIntakeSourceBinding)
        assert binding.source_path.resolve() == source.resolve()
        assert binding.original_file_name == source.name
        assert request.source_language == "zh"
        assert request.participant_privacy_paths["source"] == privacy_path


def test_cross_capability_calls_flow_with_named_uploads(tmp_path: Path) -> None:
    source_a = tmp_path / "first.docx"
    source_b = tmp_path / "second.docx"
    source_a.write_bytes(b"first")
    source_b.write_bytes(b"second")
    mock_report = _flow_report(
        capability_config=DSUR_UPDATED_IB_CONSISTENCY_QC,
        uploads={"source_a": source_a, "source_b": source_b},
        tmp_path=tmp_path,
    )
    privacy_a = _write_privacy_config(
        tmp_path,
        "001",
        enabled=True,
        registry_enabled=True,
        clinical_program_id="clinical_program_001",
    )
    privacy_b = _write_privacy_config(
        tmp_path,
        "002",
        enabled=True,
        registry_enabled=True,
        clinical_program_id="clinical_program_002",
    )

    with _patch_installed_execution() as mock_execute:
        mock_execute.return_value = _stub_application_result(mock_report)
        run_consistency_qc.main(
            [
                "--capability",
                "dsur_updated_ib",
                "--source-a",
                str(source_a),
                "--source-b",
                str(source_b),
                "--privacy-config-a",
                str(privacy_a),
                "--privacy-config-b",
                str(privacy_b),
                "--project-root",
                str(tmp_path),
            ]
        )
        request = mock_execute.call_args.kwargs["request"]
        assert request.project_root == tmp_path
        assert request.capability_id == "dsur_updated_ib"
        for slot_id, path in (("source_a", source_a), ("source_b", source_b)):
            binding = request.participant_inputs[slot_id]
            assert isinstance(binding, DocumentIntakeSourceBinding)
            assert binding.source_path.resolve() == path.resolve()
        assert request.participant_privacy_paths["source_a"] == privacy_a
        assert request.participant_privacy_paths["source_b"] == privacy_b


def test_relative_source_paths_use_current_working_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = tmp_path / "project-root"
    source_dir = tmp_path / "backend" / "samples"
    source_dir.mkdir(parents=True)
    source_a = source_dir / "first.docx"
    source_b = source_dir / "second.docx"
    source_a.write_bytes(b"first")
    source_b.write_bytes(b"second")
    monkeypatch.chdir(tmp_path)

    mock_report = _flow_report(
        capability_config=DSUR_UPDATED_IB_CONSISTENCY_QC,
        uploads={"source_a": source_a, "source_b": source_b},
        tmp_path=tmp_path,
    )
    privacy_a = _write_privacy_config(tmp_path, "001")
    privacy_b = _write_privacy_config(tmp_path, "002")

    with _patch_installed_execution() as mock_execute:
        mock_execute.return_value = _stub_application_result(mock_report)
        run_consistency_qc.main(
            [
                "--capability",
                "dsur_updated_ib",
                "--source-a",
                "backend/samples/first.docx",
                "--source-b",
                "backend/samples/second.docx",
                "--privacy-config-a",
                str(privacy_a),
                "--privacy-config-b",
                str(privacy_b),
                "--project-root",
                str(project_root),
            ]
        )

    request = mock_execute.call_args.kwargs["request"]
    assert request.project_root == project_root
    assert request.capability_id == "dsur_updated_ib"
    for slot_id, path in (("source_a", source_a), ("source_b", source_b)):
        binding = request.participant_inputs[slot_id]
        assert isinstance(binding, DocumentIntakeSourceBinding)
        assert binding.source_path.resolve() == path.resolve()


def test_internal_mode_rejects_missing_source() -> None:
    with pytest.raises(SystemExit, match="requires --source"):
        run_consistency_qc.main(["--capability", "internal_dsur"])


def test_cross_mode_rejects_missing_either_source() -> None:
    with pytest.raises(SystemExit, match="requires --source-a"):
        run_consistency_qc.main(
            [
                "--capability",
                "dsur_updated_ib",
                "--source-b",
                "b.docx",
            ]
        )
    with pytest.raises(SystemExit, match="requires --source-b"):
        run_consistency_qc.main(
            [
                "--capability",
                "dsur_updated_ib",
                "--source-a",
                "a.docx",
            ]
        )


def test_internal_mode_rejects_cross_only_sources() -> None:
    with pytest.raises(SystemExit, match="one participant input set"):
        run_consistency_qc.main(
            [
                "--capability",
                "internal_dsur",
                "--source",
                "a.docx",
                "--source-a",
                "b.docx",
            ]
        )


def test_raw_single_slot_without_privacy_config(tmp_path: Path) -> None:
    source = tmp_path / "sample.docx"
    source.write_bytes(b"doc")
    capability_config = INSTALLED_CLINICAL_TRIAL_DOC_CONSISTENCY_QC_CAPABILITIES[
        "internal_dsur"
    ]
    mock_report = _flow_report(
        capability_config=capability_config,
        uploads={"source": source},
        tmp_path=tmp_path,
    )

    with _patch_installed_execution() as mock_execute:
        mock_execute.return_value = _stub_application_result(mock_report)
        run_consistency_qc.main(
            [
                "--capability",
                "internal_dsur",
                "--source",
                str(source),
                "--project-root",
                str(tmp_path),
            ]
        )
        request = mock_execute.call_args.kwargs["request"]
        assert request.participant_privacy_paths["source"] is None
        assert isinstance(
            request.participant_inputs["source"],
            DocumentIntakeSourceBinding,
        )


def test_raw_two_slot_without_privacy_config(tmp_path: Path) -> None:
    source_a = tmp_path / "first.docx"
    source_b = tmp_path / "second.docx"
    source_a.write_bytes(b"first")
    source_b.write_bytes(b"second")
    mock_report = _flow_report(
        capability_config=DSUR_UPDATED_IB_CONSISTENCY_QC,
        uploads={"source_a": source_a, "source_b": source_b},
        tmp_path=tmp_path,
    )

    with _patch_installed_execution() as mock_execute:
        mock_execute.return_value = _stub_application_result(mock_report)
        run_consistency_qc.main(
            [
                "--capability",
                "dsur_updated_ib",
                "--source-a",
                str(source_a),
                "--source-b",
                str(source_b),
                "--project-root",
                str(tmp_path),
            ]
        )
        request = mock_execute.call_args.kwargs["request"]
        for slot_id in ("source_a", "source_b"):
            assert request.participant_privacy_paths[slot_id] is None


def test_two_slot_rejects_one_sided_privacy_config(tmp_path: Path) -> None:
    source_a = tmp_path / "first.docx"
    source_b = tmp_path / "second.docx"
    source_a.write_bytes(b"first")
    source_b.write_bytes(b"second")
    privacy_a = _write_privacy_config(tmp_path, "001")

    with pytest.raises(
        SystemExit, match="both --privacy-config-a and --privacy-config-b"
    ):
        run_consistency_qc.main(
            [
                "--capability",
                "dsur_updated_ib",
                "--source-a",
                str(source_a),
                "--source-b",
                str(source_b),
                "--privacy-config-a",
                str(privacy_a),
            ]
        )


def test_cross_mode_rejects_internal_source_flag() -> None:
    with pytest.raises(SystemExit, match="two participant input sets"):
        run_consistency_qc.main(
            [
                "--capability",
                "dsur_updated_ib",
                "--source",
                "a.docx",
                "--source-a",
                "b.docx",
                "--source-b",
                "c.docx",
            ]
        )


def test_launcher_does_not_import_runtime_or_pipeline_directly() -> None:
    source = RUN_CONSISTENCY_QC_PATH.read_text(encoding="utf-8")
    imported = _imported_module_names(_parse(RUN_CONSISTENCY_QC_PATH))
    forbidden_prefixes = (
        "runtime",
        "pipeline",
    )
    allowed_runtime_modules = {
        "runtime.request_file_intake",
    }
    violations = [
        name
        for name in sorted(imported)
        if any(
            name == prefix or name.startswith(f"{prefix}.")
            for prefix in forbidden_prefixes
        )
        and name not in allowed_runtime_modules
        and not any(
            name == allowed or name.startswith(f"{allowed}.")
            for allowed in allowed_runtime_modules
        )
    ]
    assert not violations, f"forbidden imports: {violations}"

    forbidden_tokens = (
        "run_extract_operation",
        "run_extract_step",
        "WORD_EXTRACT_BLOCK",
        "extract_docx_document",
    )
    for token in forbidden_tokens:
        assert token not in source, f"launcher must not reference {token}"


def test_launcher_calls_installed_application_not_per_capability_wrappers() -> None:
    source = RUN_CONSISTENCY_QC_PATH.read_text(encoding="utf-8")
    assert "prepare_and_allocate_installed_clinical_trial_document_consistency_qc" in source
    assert "execute_prepared_installed_clinical_trial_document_consistency_qc" in source
    assert "run_document_consistency_qc_flow" not in source
    assert "run_word_zh_internal_dsur_consistency_qc" not in source
    assert "run_word_zh_dsur_updated_ib_consistency_qc" not in source


def test_summary_prints_input_intake_identity_extract_flow(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = tmp_path / "sample.docx"
    source.write_bytes(b"doc")
    mock_report = _flow_report(
        capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
        uploads={"source": source},
        tmp_path=tmp_path,
    )
    privacy_path = _write_privacy_config(tmp_path, "001")

    fake_intake = _intake_report(
        run_id="intake_source",
        file_hash="sha256:source",
        source_path=source,
        output_dir=tmp_path / "intake" / "source",
    )
    with (
        _patch_installed_execution() as mock_execute,
        patch.object(
            run_consistency_qc,
            "run_request_file_intake_operation",
            return_value=fake_intake,
        ),
    ):
        mock_execute.return_value = _stub_application_result(mock_report)
        run_consistency_qc.main(
            [
                "--capability",
                "internal_dsur",
                "--source",
                str(source),
                "--privacy-config",
                str(privacy_path),
                "--project-root",
                str(tmp_path),
            ]
        )

    out = capsys.readouterr().out
    assert "internal_dsur consistency QC flow" in out
    assert "--- Flow execution ---" in out
    assert "flow_run_id: document_consistency_qc_20260101_000000_000000Z" in out
    assert "flow_run_summary:" in out
    assert "comparison_relation" not in out
    assert "--- Input ---" in out
    assert f"source: {source.as_posix()}" in out
    assert "--- Intake ---" in out
    assert "run_id: intake_source" in out
    assert "file_hash: sha256:source" in out
    assert "original_file_name: sample.docx" in out
    assert "--- Processing identity ---" in out
    assert "doc_id: doc_source" in out
    assert "--- Extract ---" in out
    assert "run_id: extract_source" in out
    assert "source_type: docx" in out
    assert "--- Prepare Analysis ---" in out
    assert "run_id: prepare_analysis_source" in out

    input_pos = out.index("--- Input ---")
    intake_pos = out.index("--- Intake ---")
    identity_pos = out.index("--- Processing identity ---")
    extract_pos = out.index("--- Extract ---")
    prepare_pos = out.index("--- Prepare Analysis ---")
    assert input_pos < intake_pos < identity_pos < extract_pos < prepare_pos


def test_participant_privacy_paths_single_slot_with_config(tmp_path: Path) -> None:
    privacy_path = _write_privacy_config(tmp_path, "001")
    args = SimpleNamespace(
        privacy_config=str(privacy_path),
        privacy_config_a=None,
        privacy_config_b=None,
    )
    paths = run_consistency_qc._build_participant_privacy_paths(
        args,
        capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
    )
    assert paths == {"source": privacy_path}


def test_participant_privacy_paths_single_slot_without_config() -> None:
    args = SimpleNamespace(
        privacy_config=None,
        privacy_config_a=None,
        privacy_config_b=None,
    )
    paths = run_consistency_qc._build_participant_privacy_paths(
        args,
        capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
    )
    assert paths == {"source": None}


def test_participant_privacy_paths_two_slots(tmp_path: Path) -> None:
    privacy_a = _write_privacy_config(tmp_path, "a")
    privacy_b = _write_privacy_config(tmp_path, "b")
    args = SimpleNamespace(
        privacy_config=None,
        privacy_config_a=str(privacy_a),
        privacy_config_b=str(privacy_b),
    )
    paths = run_consistency_qc._build_participant_privacy_paths(
        args,
        capability_config=DSUR_UPDATED_IB_CONSISTENCY_QC,
    )
    assert paths == {"source_a": privacy_a, "source_b": privacy_b}


IB_SAFETY_TAG_INTEGRATION_DOCX = (
    BACKEND_ROOT
    / "tests"
    / "fixtures"
    / "clinical_trial_doc"
    / "tag_integration"
    / "ib_safety_tag_integration_001.docx"
)


def test_standalone_pause_persists_checkpoint_and_resumes_without_task_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert SHOWCASE_DOCX.is_file()
    resume_dependencies = bridge_test_resume_dependencies()
    monkeypatch.setattr(
        "application.clinical_trial_doc_consistency_qc.execution."
        "materialize_installed_projection_runtime_dependencies",
        lambda *, composition: resume_dependencies["projection_runtime_dependencies"],
    )
    monkeypatch.setattr(
        "application.clinical_trial_doc_consistency_qc.execution."
        "_materialize_installed_evidence_source_preparation_execution_dependencies",
        lambda *, composition: resume_dependencies[
            "evidence_source_preparation_execution_dependencies"
        ],
    )

    run_consistency_qc.main(
        [
            "--capability",
            "internal_dsur",
            "--source",
            str(SHOWCASE_DOCX),
            "--project-root",
            str(tmp_path),
            "--candidate-scope-mode",
            "pause_at_candidate_scope",
        ]
    )

    output = capsys.readouterr().out
    assert "run_status: (not run)" in output
    assert "Filter Output Projection (" not in output
    assert "Route (" not in output
    assert "Evidence Source Preparation (" not in output

    summary_path = next(
        tmp_path.glob("runs/document_consistency_qc/*/flow_run_summary.json")
    )
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["status"] == FLOW_STATUS_PAUSED_AT_CANDIDATE_SCOPE
    assert summary["candidate_scope_decision_mode"] == "pause_at_candidate_scope"
    assert not (tmp_path / "runs" / "task_runs").exists()

    slot = summary["slots"][0]
    assert slot["status"] == "paused_at_candidate_scope"
    assert Path(slot["analysis_bundle_path"]).is_file()
    assert Path(slot["block_manifest_path"]).is_file()
    assert Path(slot["doc_meta_bundle_path"]).is_file()
    assert slot["filter_jobs"]
    for filter_job in slot["filter_jobs"]:
        assert Path(filter_job["zone_match_bundle_path"]).is_file()
        assert Path(filter_job["run_summary_path"]).is_file()

    execution = load_flow_run_execution(
        project_root=tmp_path,
        flow_run_id=summary["flow_run_id"],
    )
    decisions_by_slot = {
        paused_slot.slot_id: automatic_candidate_scope_selections(
            filter_job_ids=tuple(paused_slot.filter_job_ids),
            filter_jobs=tuple(paused_slot.filter_jobs),
        )
        for paused_slot in execution.slot_provenance
    }
    resumed = resume_installed_clinical_trial_document_consistency_qc(
        composition=build_installed_document_consistency_qc_application_composition(),
        request=DocumentConsistencyQcResumeRequest(
            flow_run_id=summary["flow_run_id"],
            candidate_scope_decisions_by_slot=decisions_by_slot,
            project_root=tmp_path,
            participant_privacy_paths={"source": None},
        ),
        projection_runtime_dependencies=resume_dependencies[
            "projection_runtime_dependencies"
        ],
        evidence_source_preparation_execution_dependencies=resume_dependencies[
            "evidence_source_preparation_execution_dependencies"
        ],
        evidence_comparison_execution_dependencies=resume_dependencies[
            "evidence_comparison_execution_dependencies"
        ],
    )

    assert resumed.flow_report.result.paused_at_candidate_scope is False
    completed_summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert completed_summary["status"] == "success"
    assert not (tmp_path / "runs" / "task_runs").exists()


def test_internal_ib_cli_executes_installed_application_with_real_esp(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """CLI maps internal_ib inputs and runs canonical application execution with ESP."""

    assert IB_SAFETY_TAG_INTEGRATION_DOCX.is_file()
    from runtime.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.stage import (
        ClinicalTrialAggregateEvidenceSourcePreparationExecutionDependencies,
    )
    from tests.document_consistency_qc_flow_helpers import FlowOverviewFakeProvider

    monkeypatch.setattr(
        "application.clinical_trial_doc_consistency_qc.execution.materialize_llm_provider",
        lambda _config: FlowOverviewFakeProvider(),
    )
    monkeypatch.setattr(
        "application.clinical_trial_doc_consistency_qc.projection_runtime."
        "materialize_llm_provider",
        lambda _config: FlowOverviewFakeProvider(),
    )
    monkeypatch.setattr(
        "application.clinical_trial_doc_consistency_qc.execution."
        "_materialize_installed_evidence_source_preparation_execution_dependencies",
        lambda *, composition: (
            ClinicalTrialAggregateEvidenceSourcePreparationExecutionDependencies(
                llm_mode="mock",
            )
        ),
    )

    def _fake_comparison_stage(*, stage_input, stage_executor):
        output_dir = stage_input.context.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        run_summary_path = output_dir / "run_summary.json"
        run_summary_path.write_text("{}", encoding="utf-8")
        return EvidenceComparisonStageResult(
            output_dir=output_dir,
            run_id=stage_input.context.run_id or "comparison_mock",
            stage_executor_id="mock.comparison",
            run_status="success",
            run_summary_path=run_summary_path,
            declared_output_path=None,
        )

    monkeypatch.setattr(
        "execution_flow.document_consistency_qc.flow.run_evidence_comparison_stage",
        _fake_comparison_stage,
    )

    with patch.object(
        run_consistency_qc,
        "prepare_and_allocate_installed_clinical_trial_document_consistency_qc",
        wraps=run_consistency_qc.prepare_and_allocate_installed_clinical_trial_document_consistency_qc,
    ) as execute:
        run_consistency_qc.main(
            [
                "--capability",
                "internal_ib",
                "--source",
                str(IB_SAFETY_TAG_INTEGRATION_DOCX),
                "--project-root",
                str(tmp_path),
            ]
        )

    execute.assert_called_once()
    request = execute.call_args.kwargs["request"]
    assert request.capability_id == "internal_ib"
    binding = request.participant_inputs["source"]
    assert isinstance(binding, DocumentIntakeSourceBinding)
    assert binding.source_path.resolve() == IB_SAFETY_TAG_INTEGRATION_DOCX.resolve()
    assert request.project_root == tmp_path

    out = capsys.readouterr().out
    assert "=== internal_ib consistency QC flow ===" in out
    assert "evidence_source_preparation_invoked: True" in out
    assert "Evidence Source Preparation (clinical_safety)" in out
    assert "declared_output:" in out
    assert "aggregate_evidence_source_bundle.json" in out
    assert "--- Evidence Comparison ---" in out
    assert "handoff_status: ready" in out

    flow_summary_path = next(
        tmp_path.glob("runs/document_consistency_qc/*/flow_run_summary.json")
    )
    assert flow_summary_path.is_file()


def test_flow_stage_description_includes_evidence_comparison() -> None:
    assert "Evidence Comparison" in run_consistency_qc._FLOW_STAGE_DESCRIPTION


def _flow_report_with_evidence_comparison(
    *,
    capability_config,
    uploads: dict[str, Path],
    tmp_path: Path,
    handoff_status,
    stage_result: EvidenceComparisonStageResult | None,
) -> DocumentConsistencyQcFlowReport:
    from operations.evidence_comparison.handoff import (
        EvidenceComparisonHandoffResolution,
    )

    base = _flow_report(
        capability_config=capability_config,
        uploads=uploads,
        tmp_path=tmp_path,
    )
    return DocumentConsistencyQcFlowReport(
        result=DocumentConsistencyQcFlowResult(
            slots=base.result.slots,
            evidence_comparison_handoff_resolution=EvidenceComparisonHandoffResolution(
                status=handoff_status,
                consumer_binding=None,
                handoff=None,
            ),
            evidence_comparison_stage_result=stage_result,
        ),
        messages=base.messages,
        flow_run_id=base.flow_run_id,
        flow_run_summary_path=base.flow_run_summary_path,
    )


def _capture_summary(
    *, capability_config, report: DocumentConsistencyQcFlowReport, tmp_path: Path
) -> str:
    import io
    from contextlib import redirect_stdout

    standalone_intake_reports = {
        slot.slot_id: _intake_report(
            run_id=f"intake_{slot.slot_id}",
            file_hash=slot.admitted_source.file_hash,
            source_path=slot.admitted_source.source_path,
            output_dir=tmp_path / "intake" / slot.slot_id,
        )
        for slot in report.result.slots
    }
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        run_consistency_qc._print_summary(
            capability_config=capability_config,
            report=report,
            standalone_intake_reports=standalone_intake_reports,
        )
    return buffer.getvalue()


def test_print_summary_evidence_comparison_success(tmp_path: Path) -> None:
    from operations.evidence_comparison.handoff import (
        EvidenceComparisonHandoffResolutionStatus,
    )

    capability = INTERNAL_DSUR_CONSISTENCY_QC
    source = tmp_path / "sample.docx"
    source.write_bytes(b"doc")
    findings_path = tmp_path / "findings.json"
    findings_path.write_text(
        json.dumps(
            {
                "artifact_type": "findings",
                "schema_version": "0.1.0",
                "jobs": [
                    {
                        "frozen_job_index": 1,
                        "comparison_mode_id": "scope_local",
                        "comparison_groups": [],
                        "findings": [
                            {
                                "finding_id": "L001",
                                "conclusion": "c",
                                "label": "pass",
                                "source_sentence_aliases": ["S001"],
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    stage_result = EvidenceComparisonStageResult(
        output_dir=tmp_path / "participants" / "source" / "evidence_comparison",
        run_id="evidence_comparison_internal_dsur",
        stage_executor_id="clinical_trial_doc.clinical_safety.aggregate_evidence",
        run_status="success",
        run_summary_path=tmp_path / "run_summary.json",
        declared_output_path=findings_path,
    )
    report = _flow_report_with_evidence_comparison(
        capability_config=capability,
        uploads={"source": source},
        tmp_path=tmp_path,
        handoff_status=EvidenceComparisonHandoffResolutionStatus.READY,
        stage_result=stage_result,
    )
    out = _capture_summary(
        capability_config=capability,
        report=report,
        tmp_path=tmp_path,
    )
    assert "--- Evidence Comparison ---" in out
    assert "handoff_status: ready" in out
    assert "run_status: success" in out
    assert "job_final_finding_count: 1" in out
    assert f"declared_output_path: {findings_path.as_posix()}" in out


def test_print_summary_evidence_comparison_partial_failure(tmp_path: Path) -> None:
    from operations.evidence_comparison.handoff import (
        EvidenceComparisonHandoffResolutionStatus,
    )

    capability = INTERNAL_DSUR_CONSISTENCY_QC
    source = tmp_path / "sample.docx"
    source.write_bytes(b"doc")
    findings_path = tmp_path / "findings.json"
    findings_path.write_text(
        json.dumps(
            {
                "artifact_type": "findings",
                "schema_version": "0.1.0",
                "jobs": [],
            }
        ),
        encoding="utf-8",
    )
    stage_result = EvidenceComparisonStageResult(
        output_dir=tmp_path / "participants" / "source" / "evidence_comparison",
        run_id="evidence_comparison_internal_dsur",
        stage_executor_id="clinical_trial_doc.clinical_safety.aggregate_evidence",
        run_status="partial_failure",
        run_summary_path=tmp_path / "run_summary.json",
        declared_output_path=findings_path,
    )
    report = _flow_report_with_evidence_comparison(
        capability_config=capability,
        uploads={"source": source},
        tmp_path=tmp_path,
        handoff_status=EvidenceComparisonHandoffResolutionStatus.READY,
        stage_result=stage_result,
    )
    out = _capture_summary(
        capability_config=capability,
        report=report,
        tmp_path=tmp_path,
    )
    assert "run_status: partial_failure" in out
    assert "job_final_finding_count: 0" in out


def test_print_summary_evidence_comparison_failed_without_declared_output(
    tmp_path: Path,
) -> None:
    from operations.evidence_comparison.handoff import (
        EvidenceComparisonHandoffResolutionStatus,
    )

    capability = INTERNAL_DSUR_CONSISTENCY_QC
    source = tmp_path / "sample.docx"
    source.write_bytes(b"doc")
    stage_result = EvidenceComparisonStageResult(
        output_dir=tmp_path / "participants" / "source" / "evidence_comparison",
        run_id="evidence_comparison_internal_dsur",
        stage_executor_id="clinical_trial_doc.clinical_safety.aggregate_evidence",
        run_status="failed",
        run_summary_path=tmp_path / "run_summary.json",
        declared_output_path=None,
    )
    report = _flow_report_with_evidence_comparison(
        capability_config=capability,
        uploads={"source": source},
        tmp_path=tmp_path,
        handoff_status=EvidenceComparisonHandoffResolutionStatus.READY,
        stage_result=stage_result,
    )
    out = _capture_summary(
        capability_config=capability,
        report=report,
        tmp_path=tmp_path,
    )
    assert "run_status: failed" in out
    assert "declared_output_path: (none)" in out
    assert "job_final_finding_count: (none)" in out


@pytest.mark.parametrize(
    ("handoff_status_name",),
    [
        ("unbound",),
        ("incomplete",),
    ],
)
def test_print_summary_evidence_comparison_not_executed(
    tmp_path: Path,
    handoff_status_name: str,
) -> None:
    from operations.evidence_comparison.handoff import (
        EvidenceComparisonHandoffResolutionStatus,
    )

    capability = INTERNAL_DSUR_CONSISTENCY_QC
    source = tmp_path / "sample.docx"
    source.write_bytes(b"doc")
    handoff_status = EvidenceComparisonHandoffResolutionStatus(handoff_status_name)
    report = _flow_report_with_evidence_comparison(
        capability_config=capability,
        uploads={"source": source},
        tmp_path=tmp_path,
        handoff_status=handoff_status,
        stage_result=None,
    )
    out = _capture_summary(
        capability_config=capability,
        report=report,
        tmp_path=tmp_path,
    )
    assert f"handoff_status: {handoff_status_name}" in out
    assert "run_status: (not run)" in out
    assert "job_final_finding_count: (not run)" in out
