from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from plugins.clinical_trial_doc.prepare_analysis import (
    build_clinical_prepare_analysis_standalone_invocation,
)
from plugins.clinical_trial_doc.VERSION import CLINICAL_TRIAL_DOC_PLUGIN_VERSION
from runtime.prepare_analysis import PrepareAnalysisExecutionContext
from runtime.prepare_analysis import operations as prepare_analysis_operations
from scripts.stage_runners import prepare_analysis_runner


def _sample_extract_bundle() -> dict:
    return {
        "doc_id": "ib_001",
        "file_name": "ib_001.docx",
        "file_hash": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
        "source_type": "docx",
        "document_meta": {"language": "zh"},
        "content_blocks": [
            {
                "block_id": "C0001",
                "kind": "paragraph",
                "text": "研究者手册",
            }
        ],
        "front_matter_blocks": [],
        "table_blocks": [],
        "format_blocks": [],
    }


def test_prepare_analysis_runner_default_layout_uses_privacy_profile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    extract_dir = tmp_path / "extract" / "ib_001"
    extract_dir.mkdir(parents=True)
    bundle_path = extract_dir / "bundle.json"
    bundle_path.write_text(json.dumps(_sample_extract_bundle()), encoding="utf-8")

    monkeypatch.setattr(prepare_analysis_runner, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(
        prepare_analysis_operations,
        "snapshot_git_provenance_before_run",
        lambda **_: {"git_commit": "abc", "git_dirty": False},
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "prepare_analysis_runner.py",
            "--bundle",
            str(bundle_path),
            "--language",
            "zh",
            "--clinical-program",
            "clinical_program_001",
        ],
    )

    prepare_analysis_runner.main()

    outputs = list(
        (tmp_path / "runs" / "prepare_analysis").glob("*/*/analysis_bundle.json")
    )
    assert len(outputs) == 1

    run_dir = outputs[0].parent
    assert (run_dir / "analysis_bundle.json").is_file()
    assert not (run_dir / "masked_bundle.json").exists()
    assert not (run_dir / "doc_meta").exists()
    assert not (run_dir / "doc_meta_bundle.json").exists()

    summary = json.loads(run_dir.joinpath("run_summary.json").read_text())
    assert summary["stage"] == "prepare_analysis"
    assert summary["pipeline"] == ["extract", "prepare_analysis"]
    assert "privacy_profile_ref" not in summary
    assert "session_segment" not in summary
    assert "context" not in summary
    assert summary["stage_scope"] == "analysis_preparation"
    assert summary["language"] == "zh"
    assert summary["plugin"]["name"] == "clinical_trial_doc"
    assert summary["plugin"]["version"] == CLINICAL_TRIAL_DOC_PLUGIN_VERSION
    assert "components" not in summary["plugin"]
    assert summary["analysis_transform"] == "identity"
    assert summary["privacy_transform_applied"] is False
    assert summary["privacy_detectors_configured"] == []
    assert summary["privacy_detectors_used"] == []
    assert "privacy_transform" not in summary
    assert "privacy_transforms" not in summary
    assert "detectors" not in summary
    assert "privacy_transform_slot" not in summary
    assert "privacy_stages" not in summary
    assert "post_extract" not in summary
    assert "pre_llm" not in summary
    assert "privacy_preset" not in summary
    assert "privacy_mode" not in summary
    assert summary["outputs"]["analysis_bundle"] == "analysis_bundle.json"
    assert "masked_bundle" not in summary["outputs"]
    assert "mask_output" not in summary["outputs"]
    assert "privacy_audit" not in summary["outputs"]
    assert "mapping" not in summary["outputs"]
    assert summary.get("audit_outputs") == []
    assert (
        summary["output_privacy_contract"]["analysis_bundle"]["artifact_privacy_level"]
        == "local_raw_public"
    )
    assert (
        summary["output_privacy_contract"]["analysis_bundle"]["safe_for_export"]
        is False
    )
    assert not (run_dir / "privacy_audit.json").exists()
    assert not (run_dir / "mask_output.json").exists()
    assert not (run_dir / "mapping.json").exists()

    analysis_bundle = json.loads(
        run_dir.joinpath("analysis_bundle.json").read_text(encoding="utf-8")
    )
    assert analysis_bundle["analysis_bundle_id"] == summary["run_id"]
    assert analysis_bundle["doc_id"] == summary["doc_id"]


@pytest.mark.parametrize(
    ("flags", "detectors", "date_shift", "privacy_applied"),
    [
        ((), None, None, False),
        (("--privacy-detectors", "registry,regex"), "registry,regex", None, True),
        (("--date-shift",), None, True, True),
        (
            ("--privacy-detectors", "registry,regex", "--no-date-shift"),
            "registry,regex",
            False,
            True,
        ),
    ],
    ids=["identity", "registry-regex", "dates-only", "mask-no-date"],
)
def test_runner_path_matches_direct_canonical_runtime(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    flags: tuple[str, ...],
    detectors: str | None,
    date_shift: bool | None,
    privacy_applied: bool,
) -> None:
    bundle = _sample_extract_bundle()
    bundle_path = tmp_path / "bundle.json"
    bundle_path.write_text(json.dumps(bundle), encoding="utf-8")
    output_dir = tmp_path / "runner-output"
    monkeypatch.setattr(prepare_analysis_runner, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(
        prepare_analysis_operations,
        "snapshot_git_provenance_before_run",
        lambda **_: {"git_commit": "abc", "git_dirty": False},
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "prepare_analysis_runner.py",
            "--bundle",
            str(bundle_path),
            "--output-dir",
            str(output_dir),
            "--clinical-program",
            "clinical_program_001",
            *flags,
        ],
    )

    prepare_analysis_runner.main()

    runner_bundle = json.loads(
        (output_dir / "analysis_bundle.json").read_text(encoding="utf-8")
    )
    invocation = build_clinical_prepare_analysis_standalone_invocation(
        clinical_program_id="clinical_program_001",
        bundle=bundle,
        privacy_after_extract_detectors=detectors,
        date_shift_explicit=date_shift,
    )
    direct = prepare_analysis_operations.run_prepare_analysis_operation(
        execution=PrepareAnalysisExecutionContext(
            project_root=tmp_path,
            run_id=runner_bundle["analysis_bundle_id"],
            persist=False,
        ),
        prepare_analysis_config_id=invocation.prepare_analysis_config_id,
        config_registry=invocation.config_registry,
        request_options=invocation.request_options,
        bundle=bundle,
        runtime_context_label=invocation.runtime_context_label,
    )
    assert runner_bundle == direct.documents[0].artifacts.analysis_bundle
    assert (output_dir / "privacy_audit.json").exists() is privacy_applied
    assert (output_dir / "mapping.json").exists() is privacy_applied
    assert (output_dir / "private_audit_bundle.json").exists() is privacy_applied

