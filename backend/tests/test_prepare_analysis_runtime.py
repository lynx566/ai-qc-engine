from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from artifacts.block_manifest import BLOCK_MANIFEST_FILENAME
from artifacts.prepare_analysis import (
    ANALYSIS_BUNDLE_FILENAME,
    FAILURE_FILENAME,
    RUN_SUMMARY_FILENAME,
    build_analysis_bundle_artifact,
    validate_analysis_bundle,
)
from clinical_program_fixtures import prepare_analysis_bundle_for_test
from steps import prepare_analysis as prepare_step
from plugins.clinical_trial_doc.prepare_analysis import (
    build_clinical_prepare_analysis_standalone_invocation,
)
from privacy.config import PrivacyConfig
from runtime.prepare_analysis import (
    PrepareAnalysisExecutionContext,
    operations,
    run_prepare_analysis_operation,
)

FILE_HASH = "sha256:" + "a" * 64


def _bundle() -> dict:
    text = "稳定句子。"
    return {
        "doc_id": "runtime_doc",
        "file_hash": FILE_HASH,
        "file_name": "runtime_doc.docx",
        "source_type": "docx",
        "document_meta": {"language": "zh", "bundle_schema_version": "0.2.1"},
        "front_matter_blocks": [],
        "content_blocks": [
            {
                "block_id": "C0001",
                "kind": "paragraph",
                "normalized_text": text,
                "order": 1,
                "doc_order_index": 0,
                "source_ref": {
                    "source_type": "docx",
                    "locator_type": "paragraph",
                    "locator_payload": {"para_index": 0},
                },
                "sentences": [
                    {
                        "sentence_id": "C0001:S001",
                        "normalized_text": text,
                    }
                ],
            }
        ],
        "table_blocks": [],
        "format_blocks": [],
    }


def _execution(tmp_path: Path, **kwargs) -> PrepareAnalysisExecutionContext:
    return PrepareAnalysisExecutionContext(
        project_root=tmp_path,
        git_provenance={"git_commit": "abc", "git_dirty": False},
        **kwargs,
    )


def _runtime_composition(bundle: dict) -> dict:
    invocation = build_clinical_prepare_analysis_standalone_invocation(
        clinical_program_id="clinical_program_001",
        bundle=bundle,
        privacy_config=PrivacyConfig.default(),
    )
    return {
        "prepare_analysis_config_id": invocation.prepare_analysis_config_id,
        "config_registry": invocation.config_registry,
        "request_options": invocation.request_options,
        "runtime_context_label": invocation.runtime_context_label,
    }


def test_runtime_calls_canonical_step_and_persists_formal_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    called: list[str] = []
    real_step = operations.prepare_analysis_bundle

    def _capturing_step(bundle, **kwargs):
        called.append(str(bundle["doc_id"]))
        return real_step(bundle, **kwargs)

    monkeypatch.setattr(operations, "prepare_analysis_bundle", _capturing_step)
    output_dir = tmp_path / "caller-owned"
    bundle = _bundle()
    report = run_prepare_analysis_operation(
        execution=_execution(tmp_path, output_dir=output_dir, run_id="caller_run"),
        bundle=bundle,
        **_runtime_composition(bundle),
    )

    assert called == ["runtime_doc"]
    assert report.status == "success"
    assert report.documents[0].output_dir == output_dir.resolve()
    assert report.index_path == output_dir.resolve() / "index.json"
    assert (output_dir / ANALYSIS_BUNDLE_FILENAME).is_file()
    assert (output_dir / BLOCK_MANIFEST_FILENAME).is_file()
    assert (output_dir / RUN_SUMMARY_FILENAME).is_file()
    summary = json.loads(
        (output_dir / RUN_SUMMARY_FILENAME).read_text(encoding="utf-8")
    )
    assert summary["run_id"] == "caller_run"
    validate_analysis_bundle(report.documents[0].artifacts.analysis_bundle)


def test_composed_runtime_returns_artifacts_without_top_level_run(
    tmp_path: Path,
) -> None:
    bundle = _bundle()
    report = run_prepare_analysis_operation(
        execution=_execution(tmp_path, run_id="flow_participant", persist=False),
        bundle=bundle,
        **_runtime_composition(bundle),
    )

    document = report.documents[0]
    assert document.run_id == "flow_participant"
    assert document.paths is None
    assert document.output_dir is None
    assert report.index_path is None
    assert not (tmp_path / "runs" / "prepare_analysis").exists()
    assert (
        document.artifacts.block_manifest["analysis_bundle_ref"]["analysis_bundle_id"]
        == "flow_participant"
    )


def test_runtime_records_boundary_failure_in_caller_output(tmp_path: Path) -> None:
    malformed = _bundle()
    malformed["content_blocks"][0]["source_ref"].pop("locator_type")
    output_dir = tmp_path / "failed-run"

    with pytest.raises(ValueError, match="source_ref.locator_type"):
        run_prepare_analysis_operation(
            execution=_execution(tmp_path, output_dir=output_dir, run_id="bad_run"),
            bundle=malformed,
            **_runtime_composition(malformed),
        )

    failure = json.loads((output_dir / FAILURE_FILENAME).read_text(encoding="utf-8"))
    assert failure["stage"] == "prepare_analysis"
    assert failure["status"] == "failed"
    assert failure["run_id"] == "bad_run"
    assert failure["error"]["type"] == "ValueError"


@pytest.mark.parametrize(
    "mutation,match",
    [
        (lambda block: block["sentences"][0].pop("normalized_text"), "normalized_text"),
        (lambda block: block["sentences"][0].pop("sentence_id"), "sentence_id"),
        (
            lambda block: block["source_ref"].update(locator_payload="paragraph:0"),
            "locator_payload",
        ),
    ],
)
def test_step_rejects_malformed_extract_contract(mutation, match: str) -> None:
    bundle = _bundle()
    mutation(bundle["content_blocks"][0])
    with pytest.raises(ValueError, match=match):
        prepare_analysis_bundle_for_test(
            bundle,
            privacy_config=PrivacyConfig.default(),
            clinical_program_id="clinical_program_001",
        )


def test_step_validates_complete_result_projection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _IncompleteProjection:
        def __init__(self) -> None:
            self.content = {}
            self.tables = {}

    monkeypatch.setattr(
        prepare_step,
        "project_analysis_heading_paths",
        lambda _bundle: _IncompleteProjection(),
    )
    with pytest.raises(ValueError, match="cover every content/table block"):
        prepare_analysis_bundle_for_test(
            _bundle(),
            privacy_config=PrivacyConfig.default(),
            clinical_program_id="clinical_program_001",
        )


def test_formal_analysis_artifact_builder_round_trip() -> None:
    result = prepare_analysis_bundle_for_test(
        _bundle(),
        analysis_bundle_id="round_trip",
        privacy_config=PrivacyConfig.default(),
        clinical_program_id="clinical_program_001",
    )
    artifact = build_analysis_bundle_artifact(result.analysis_bundle)
    assert artifact == result.analysis_bundle
    assert artifact is not result.analysis_bundle
    validate_analysis_bundle(artifact)
    assert ANALYSIS_BUNDLE_FILENAME == "analysis_bundle.json"
    assert BLOCK_MANIFEST_FILENAME == "block_manifest.json"
