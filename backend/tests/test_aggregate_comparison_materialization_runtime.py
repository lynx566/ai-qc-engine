"""Standalone Aggregate Comparison materialization runtime tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from artifacts.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence import (
    AGGREGATE_COMPARISON_EVIDENCE_FILENAME,
    AGGREGATE_COMPARISON_EVIDENCE_SCHEMA_VERSION,
    validate_aggregate_comparison_evidence,
)
from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.aggregate_evidence_source_bundle import (
    build_aggregate_evidence_source_bundle,
)
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.source_adapter import (
    adapt_clinical_safety_aggregate_source_bundle,
)
from runtime.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence.materialization import (
    run_aggregate_comparison_materialization,
)
from runtime.io import load_json, save_json


def _bundle(*, label: str, sentence_count: int = 1) -> dict:
    sentences = [
        {
            "sentence_id": f"{label}:S{index + 1:03d}",
            "sentence_order": index,
            "text": f"{label} sentence {index + 1}",
            "source_block_ids": [f"B-{label}"],
        }
        for index in range(sentence_count)
    ]
    return build_aggregate_evidence_source_bundle(
        doc_id=f"doc_{label}",
        file_hash=f"sha256:{label}",
        document_type="csr",
        heading_scopes=[
            {
                "scope_id": f"HS-{label}",
                "scope_order": 7,
                "heading_path": [f"Heading {label}"],
                "units": [
                    {
                        "unit_id": f"TU-{label}",
                        "unit_order": 0,
                        "text": f"unit {label}",
                        "source": {"block_ids": [f"B-{label}"]},
                        "sentences": sentences,
                    }
                ],
            }
        ],
    )


def test_single_source_materializes_and_persists_formal_artifact(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "source.json"
    save_json(source_path, _bundle(label="single", sentence_count=2))
    output_dir = tmp_path / "output"

    report = run_aggregate_comparison_materialization(
        project_root=tmp_path,
        source_adapter=adapt_clinical_safety_aggregate_source_bundle,
        source=source_path,
        output_dir=output_dir,
        run_id="single_test",
    )

    artifact_path = output_dir / AGGREGATE_COMPARISON_EVIDENCE_FILENAME
    assert report.result.aggregate_comparison_evidence_path == artifact_path.resolve()
    assert artifact_path.is_file()
    artifact = load_json(artifact_path)
    validate_aggregate_comparison_evidence(artifact)
    assert [participant["role_id"] for participant in artifact["participants"]] == [
        "source"
    ]
    assert artifact["participants"][0]["scopes"][0]["scope_alias"] == "H0001"

    summary = load_json(report.result.run_summary_path)
    assert summary["inputs"] == {
        "participants": [
            {
                "role_id": "source",
                "source_bundle": source_path.resolve().as_posix(),
                "aggregate_evidence_source_bundle_id": artifact["participants"][0][
                    "aggregate_evidence_source_bundle_id"
                ],
                "doc_id": "doc_single",
                "file_hash": "sha256:single",
            }
        ]
    }
    assert summary["outputs"] == {
        "run_summary": "run_summary.json",
        "aggregate_comparison_evidence": AGGREGATE_COMPARISON_EVIDENCE_FILENAME,
        "aggregate_comparison_evidence_schema_version": (
            AGGREGATE_COMPARISON_EVIDENCE_SCHEMA_VERSION
        ),
    }
    assert summary["stage"] == "evidence_comparison"
    assert "document_type" not in summary
    assert summary["evidence_scope"] == "clinical_safety"
    assert summary["specialization"] == "aggregate"
    assert summary["phase"] == "materialize"
    assert summary["completed_operation"] == (
        "aggregate_evidence.materialize_aggregate_comparison_evidence"
    )
    assert summary["status"] == "success"
    assert summary["run_status"] == "success"
    assert summary["run_dir_layout"] == (
        "stage/evidence_scope/specialization/phase/run_id"
    )
    assert summary["created_at"].endswith("Z")
    assert summary["git_commit"] is None
    assert summary["git_dirty"] is None
    assert summary["git_dirty_checked_at"] == "before_run"
    assert {"doc_id", "file_hash", "upstream_run_id", "upstream_stage"}.isdisjoint(
        summary
    )


def test_cross_sources_preserve_a_then_b_and_continue_aliases(
    tmp_path: Path,
) -> None:
    source_a_path = tmp_path / "source_a.json"
    source_b_path = tmp_path / "source_b.json"
    save_json(source_a_path, _bundle(label="a", sentence_count=2))
    save_json(source_b_path, _bundle(label="b", sentence_count=1))

    report = run_aggregate_comparison_materialization(
        project_root=tmp_path,
        source_adapter=adapt_clinical_safety_aggregate_source_bundle,
        source_a=source_a_path,
        source_b=source_b_path,
        output_dir=tmp_path / "cross_output",
    )

    artifact = report.result.aggregate_comparison_evidence
    assert [participant["role_id"] for participant in artifact["participants"]] == [
        "source_a",
        "source_b",
    ]
    first_scope = artifact["participants"][0]["scopes"][0]
    second_scope = artifact["participants"][1]["scopes"][0]
    assert first_scope["scope_alias"] == "H0001"
    assert first_scope["units"][0]["unit_alias"] == "U0001"
    assert first_scope["units"][0]["sentences"][-1]["sentence_alias"] == "T0002"
    assert second_scope["scope_alias"] == "H0002"
    assert second_scope["units"][0]["unit_alias"] == "U0002"
    assert second_scope["units"][0]["sentences"][0]["sentence_alias"] == "T0003"

    summary = load_json(report.result.run_summary_path)
    assert summary["inputs"]["participants"] == [
        {
            "role_id": "source_a",
            "source_bundle": source_a_path.resolve().as_posix(),
            "aggregate_evidence_source_bundle_id": artifact["participants"][0][
                "aggregate_evidence_source_bundle_id"
            ],
            "doc_id": "doc_a",
            "file_hash": "sha256:a",
        },
        {
            "role_id": "source_b",
            "source_bundle": source_b_path.resolve().as_posix(),
            "aggregate_evidence_source_bundle_id": artifact["participants"][1][
                "aggregate_evidence_source_bundle_id"
            ],
            "doc_id": "doc_b",
            "file_hash": "sha256:b",
        },
    ]
    assert {"doc_id", "file_hash", "upstream_run_id", "upstream_stage"}.isdisjoint(
        summary
    )


def test_invalid_source_fails_before_any_artifact_is_persisted(tmp_path: Path) -> None:
    source_path = tmp_path / "invalid.json"
    invalid = _bundle(label="invalid")
    invalid["artifact_type"] = "wrong"
    save_json(source_path, invalid)
    output_dir = tmp_path / "output"

    with pytest.raises(ValueError, match="artifact_type"):
        run_aggregate_comparison_materialization(
            project_root=tmp_path,
            source_adapter=adapt_clinical_safety_aggregate_source_bundle,
            source=source_path,
            output_dir=output_dir,
        )

    assert not (output_dir / AGGREGATE_COMPARISON_EVIDENCE_FILENAME).exists()


def test_default_output_uses_aggregate_specialization_materialize_run_layout(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "source.json"
    save_json(source_path, _bundle(label="layout"))

    report = run_aggregate_comparison_materialization(
        project_root=tmp_path,
        source_adapter=adapt_clinical_safety_aggregate_source_bundle,
        source=source_path,
    )

    relative = report.result.output_dir.relative_to(tmp_path)
    assert relative.parts[:5] == (
        "runs",
        "evidence_comparison",
        "clinical_safety",
        "aggregate",
        "materialize",
    )
    assert relative.parts[5] == report.result.run_id
    assert report.result.run_summary_path == (
        report.result.output_dir / "run_summary.json"
    )
    assert report.result.run_summary_path.is_file()
