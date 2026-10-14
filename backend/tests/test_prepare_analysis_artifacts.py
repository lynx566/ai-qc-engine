from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from artifacts.block_manifest import BLOCK_MANIFEST_FILENAME, assert_block_manifest_safe
from runtime.prepare_analysis import operations as prepare_analysis_operations
from scripts.stage_runners import prepare_analysis_runner

_FORBIDDEN_SUBSTRINGS = (
    "normalized_text",
    "span_map",
    "source_ref",
    "document_meta",
    "privacy_transforms",
    "sentences",
)

LINEAGE_FILE_HASH = (
    "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
)


def _sample_extract_bundle() -> dict:
    return {
        "doc_id": "ib_001",
        "file_name": "ib_001.docx",
        "file_hash": LINEAGE_FILE_HASH,
        "source_type": "docx",
        "document_meta": {"language": "zh"},
        "content_blocks": [
            {
                "block_id": "C0001",
                "kind": "paragraph",
                "text": "试验参与者张三于2024年3月15日入组。",
            }
        ],
        "front_matter_blocks": [],
        "table_blocks": [],
        "format_blocks": [],
    }


def _run_prepare_analysis(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    bundle_path: Path | None = None,
    extra_argv: tuple[str, ...] = (),
) -> Path:
    if bundle_path is None:
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
            *extra_argv,
        ],
    )
    prepare_analysis_runner.main()

    outputs = list(
        (tmp_path / "runs" / "prepare_analysis").glob("*/*/analysis_bundle.json")
    )
    assert len(outputs) == 1
    return outputs[0].parent


def test_prepare_analysis_identity_outputs_no_audit_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_dir = _run_prepare_analysis(tmp_path, monkeypatch)

    assert (run_dir / "analysis_bundle.json").is_file()
    assert (run_dir / BLOCK_MANIFEST_FILENAME).is_file()
    assert (run_dir / "run_summary.json").is_file()
    assert not (run_dir / "privacy_audit.json").exists()
    assert not (run_dir / "mask_output.json").exists()
    assert not (run_dir / "mapping.json").exists()
    assert not (run_dir / "private_audit_bundle.json").exists()
    assert not (run_dir / "block_manifest_run_summary.json").exists()

    summary = json.loads((run_dir / "run_summary.json").read_text(encoding="utf-8"))
    assert summary["outputs"] == {
        "analysis_bundle": "analysis_bundle.json",
        "block_manifest": "block_manifest.json",
    }
    assert summary["analysis_transform"] == "identity"
    assert summary["privacy_transform_applied"] is False
    assert summary["privacy_detectors_configured"] == []
    assert summary["privacy_detectors_used"] == []
    assert summary["audit_outputs"] == []
    assert summary["output_privacy_contract"]["analysis_bundle"][
        "artifact_privacy_level"
    ] == "local_raw_public"
    assert summary["output_privacy_contract"]["analysis_bundle"]["safe_for_export"] is False
    assert summary["output_privacy_contract"]["private_outputs"] == {}
    assert "privacy_transform" not in summary
    assert "privacy_transforms" not in summary
    assert "privacy_profile_ref" not in summary
    assert "components" not in summary.get("plugin", {})

    analysis_bundle = json.loads(
        (run_dir / "analysis_bundle.json").read_text(encoding="utf-8")
    )
    block_manifest = json.loads((run_dir / BLOCK_MANIFEST_FILENAME).read_text(encoding="utf-8"))
    assert "clinical_program_id" not in analysis_bundle
    assert "clinical_program_id_source" not in analysis_bundle
    assert "clinical_program_id" not in summary.get("stats", {})
    block = analysis_bundle["content_blocks"][0]
    out_block = block_manifest["blocks"][0]
    assert "analysis_text" in block
    assert "span_map" not in block
    assert analysis_bundle["privacy_enabled"] is False
    assert analysis_bundle["analysis_bundle_contract"] == "local_raw_v0.3"
    assert analysis_bundle["analysis_bundle_id"] == summary["run_id"]
    assert analysis_bundle["doc_id"] == summary["doc_id"]
    assert block_manifest["analysis_bundle_ref"]["analysis_bundle_id"] == (
        analysis_bundle["analysis_bundle_id"]
    )
    assert len(block_manifest["blocks"]) == len(analysis_bundle["content_blocks"])
    assert out_block["analysis_text"] == block["analysis_text"]
    assert out_block["text_ref"] == {
        "analysis_bundle_id": analysis_bundle["analysis_bundle_id"],
        "block_id": block["block_id"],
    }

    serialized = json.dumps(block_manifest, ensure_ascii=False)
    for forbidden in _FORBIDDEN_SUBSTRINGS:
        assert forbidden not in serialized
    assert_block_manifest_safe(block_manifest)

    index = json.loads(
        (run_dir.parent / "index.json").read_text(encoding="utf-8")
    )
    entry = index["documents"][0]
    assert "privacy_level" not in entry
    assert entry["analysis_transform"] == "identity"
    assert entry["privacy_transform_applied"] is False
    assert entry["privacy_detectors"] == []
    assert "masked" not in json.dumps(index, ensure_ascii=False)


def test_prepare_analysis_dates_only_outputs_audit_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """dates-only runner path: explicit date shift, empty detectors, audit trio."""
    run_dir = _run_prepare_analysis(
        tmp_path,
        monkeypatch,
        extra_argv=("--date-shift",),
    )

    assert (run_dir / "analysis_bundle.json").is_file()
    assert (run_dir / BLOCK_MANIFEST_FILENAME).is_file()
    assert (run_dir / "privacy_audit.json").is_file()
    assert (run_dir / "mapping.json").is_file()
    assert (run_dir / "private_audit_bundle.json").is_file()
    assert not (run_dir / "mask_output.json").exists()

    summary = json.loads((run_dir / "run_summary.json").read_text(encoding="utf-8"))
    assert summary["outputs"] == {
        "analysis_bundle": "analysis_bundle.json",
        "block_manifest": "block_manifest.json",
        "privacy_audit": "privacy_audit.json",
        "mapping": "mapping.json",
        "private_audit_bundle": "private_audit_bundle.json",
    }
    assert summary["analysis_transform"] == "privacy_transform"
    assert summary["privacy_transform_applied"] is True
    assert summary["privacy_detectors_configured"] == []
    assert summary["privacy_detectors_used"] == []
    assert summary["audit_outputs"] == [
        "privacy_audit",
        "mapping",
        "private_audit_bundle",
    ]
    assert summary["privacy_transform"]["settings"]["date_shift_offset_days"] == 17

    analysis_bundle = json.loads(
        (run_dir / "analysis_bundle.json").read_text(encoding="utf-8")
    )
    assert analysis_bundle["analysis_bundle_contract"] == "public_masked_v0.4"
    assert analysis_bundle["privacy_transforms"]["after_extract"]["applied"] is True
    block = analysis_bundle["content_blocks"][0]
    assert "2024-03-15" not in block["analysis_text"]
    assert "2024年3月15日" not in block["analysis_text"]
    assert "2024-04-01" in block["analysis_text"] or "2024年4月1日" in block["analysis_text"]
    assert "normalized_text" not in block
    assert "span_map" not in block


def test_prepare_analysis_privacy_outputs_audit_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_dir = _run_prepare_analysis(
        tmp_path,
        monkeypatch,
        extra_argv=("--privacy-detectors", "registry,regex"),
    )

    assert (run_dir / "analysis_bundle.json").is_file()
    assert (run_dir / BLOCK_MANIFEST_FILENAME).is_file()
    assert (run_dir / "privacy_audit.json").is_file()
    assert (run_dir / "mapping.json").is_file()
    assert (run_dir / "private_audit_bundle.json").is_file()
    assert not (run_dir / "mask_output.json").exists()
    assert not (run_dir / "block_manifest_run_summary.json").exists()

    summary = json.loads((run_dir / "run_summary.json").read_text(encoding="utf-8"))
    assert summary["outputs"] == {
        "analysis_bundle": "analysis_bundle.json",
        "block_manifest": "block_manifest.json",
        "privacy_audit": "privacy_audit.json",
        "mapping": "mapping.json",
        "private_audit_bundle": "private_audit_bundle.json",
    }
    assert summary["audit_outputs"] == [
        "privacy_audit",
        "mapping",
        "private_audit_bundle",
    ]
    contract = summary["output_privacy_contract"]
    assert contract["analysis_bundle"]["artifact_privacy_level"] == "public_masked_v0.4"
    assert contract["analysis_bundle"]["safe_for_export"] is False
    assert contract["private_outputs"]["private_audit_bundle"] == "private_raw_audit"
    assert summary["analysis_transform"] == "privacy_transform"
    assert summary["privacy_transform_applied"] is True
    assert summary["privacy_detectors_used"] == ["registry", "regex"]
    assert summary["privacy_transform"]["settings"]["date_shift_offset_days"] == 17
    assert summary["privacy_profile_ref"] == "clinical_trial_doc"
    assert "uie_schema_zh" not in summary["plugin"]["components"]
    assert "registry" in summary["plugin"]["components"]
    assert "regex_rules_zh" in summary["plugin"]["components"]
    assert "privacy_transforms" not in summary

    analysis_bundle = json.loads(
        (run_dir / "analysis_bundle.json").read_text(encoding="utf-8")
    )
    block_manifest = json.loads((run_dir / BLOCK_MANIFEST_FILENAME).read_text(encoding="utf-8"))
    assert "clinical_program_id" not in analysis_bundle
    assert "clinical_program_id_source" not in analysis_bundle
    assert summary["stats"]["clinical_program_id"] == "clinical_program_001"
    assert "clinical_program_id_source" not in summary.get("stats", {})
    assert analysis_bundle["privacy_enabled"] is True
    assert analysis_bundle["analysis_bundle_contract"] == "public_masked_v0.4"
    assert analysis_bundle["analysis_bundle_id"] == summary["run_id"]
    assert "normalized_text" not in json.dumps(analysis_bundle, ensure_ascii=False)
    block = analysis_bundle["content_blocks"][0]
    assert "analysis_text" in block
    assert "normalized_text" not in block
    assert analysis_bundle["doc_id"] == summary["doc_id"]
    assert block_manifest["analysis_bundle_ref"]["analysis_bundle_id"] == (
        analysis_bundle["analysis_bundle_id"]
    )
    assert len(block_manifest["blocks"]) == len(analysis_bundle["content_blocks"])

    index = json.loads(
        (run_dir.parent / "index.json").read_text(encoding="utf-8")
    )
    entry = index["documents"][0]
    assert "privacy_level" not in entry
    assert entry["analysis_transform"] == "privacy_transform"
    assert entry["privacy_transform_applied"] is True
    assert entry["privacy_detectors"] == ["registry", "regex"]
    assert "masked" not in json.dumps(index, ensure_ascii=False)
