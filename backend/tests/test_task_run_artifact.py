"""Tests for the neutral persisted TaskRun artifact contract."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from application.task_run import (
    allocate_task_run_id,
    attach_flow_run,
    create_task_run,
    create_task_run_for_flow,
    load_task_run,
)
from artifacts.task_run import (
    TASK_RUN_SCHEMA_VERSION,
    TASK_RUN_SCHEMA_VERSION_0_2_0,
    FlowExecutionRef,
    build_task_run_manifest,
    load_task_run_manifest,
    save_task_run_manifest,
    task_run_manifest_path,
    validate_task_run_manifest,
)


def _manifest(
    *,
    flow_runs: object,
    schema_version: str = TASK_RUN_SCHEMA_VERSION,
) -> dict[str, object]:
    return {
        "artifact_type": "task_run",
        "schema_version": schema_version,
        "task_run_id": "task_run_20260920_010203_123456Z",
        "task_id": "internal_dsur_qc",
        "created_at": "2026-09-20T01:02:03Z",
        "updated_at": "2026-09-20T01:02:04Z",
        "flow_runs": flow_runs,
    }


def test_task_run_manifest_round_trip(tmp_path: Path) -> None:
    manifest = build_task_run_manifest(
        task_run_id="task_run_20260920_010203_123456Z",
        task_id="internal_dsur_qc",
        created_at="2026-09-20T01:02:03Z",
        updated_at="2026-09-20T01:02:04Z",
        flow_runs=(
            FlowExecutionRef(
                flow_id="document_consistency_qc",
                flow_run_id="document_consistency_qc_20260920_010204_123456Z",
            ),
        ),
    )

    path = save_task_run_manifest(project_root=tmp_path, manifest=manifest)

    assert path == (
        tmp_path / "runs" / "task_runs" / manifest["task_run_id"] / "task_run.json"
    )
    assert (
        load_task_run_manifest(
            project_root=tmp_path,
            task_run_id=str(manifest["task_run_id"]),
        )
        == manifest
    )


@pytest.mark.parametrize("flow_runs", [None, {}, "flow", ()])
def test_task_run_rejects_invalid_flow_run_containers(flow_runs: object) -> None:
    with pytest.raises((TypeError, ValueError), match="flow_runs"):
        validate_task_run_manifest(_manifest(flow_runs=flow_runs))


def test_task_run_schema_0_2_0_requires_non_empty_flow_runs() -> None:
    with pytest.raises(ValueError, match="flow_runs must contain at least one entry"):
        validate_task_run_manifest(
            _manifest(flow_runs=[], schema_version=TASK_RUN_SCHEMA_VERSION_0_2_0)
        )


def test_task_run_schema_0_3_0_allows_empty_flow_runs() -> None:
    validate_task_run_manifest(_manifest(flow_runs=[]))


def test_task_run_schema_0_2_0_non_empty_flow_runs_remains_valid() -> None:
    validate_task_run_manifest(
        _manifest(
            flow_runs=[
                {
                    "flow_id": "document_consistency_qc",
                    "flow_run_id": "document_consistency_qc_run",
                }
            ],
            schema_version=TASK_RUN_SCHEMA_VERSION_0_2_0,
        )
    )


@pytest.mark.parametrize(
    "flow_ref",
    [
        {"flow_id": "document_consistency_qc"},
        {"flow_run_id": "document_consistency_qc_run"},
        {
            "flow_id": "document_consistency_qc",
            "flow_run_id": "document_consistency_qc_run",
            "status": "success",
        },
    ],
)
def test_flow_execution_ref_requires_exact_identity_fields(
    flow_ref: dict[str, str],
) -> None:
    with pytest.raises(ValueError, match=r"flow_runs\[0\]"):
        validate_task_run_manifest(_manifest(flow_runs=[flow_ref]))


def test_task_run_rejects_duplicate_flow_run_ids() -> None:
    flow_runs = [
        {
            "flow_id": "document_consistency_qc",
            "flow_run_id": "shared_run",
        },
        {
            "flow_id": "regulatory_template_compliance",
            "flow_run_id": "shared_run",
        },
    ]

    with pytest.raises(ValueError, match="duplicate flow_run_id"):
        validate_task_run_manifest(_manifest(flow_runs=flow_runs))


def test_task_run_allows_same_flow_id_with_distinct_run_ids() -> None:
    manifest = _manifest(
        flow_runs=[
            {
                "flow_id": "document_consistency_qc",
                "flow_run_id": "document_consistency_qc_first",
            },
            {
                "flow_id": "document_consistency_qc",
                "flow_run_id": "document_consistency_qc_rerun",
            },
        ]
    )

    validate_task_run_manifest(manifest)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("task_run_id", ""),
        ("task_id", "  "),
        ("created_at", None),
        ("updated_at", ""),
    ],
)
def test_task_run_requires_non_empty_identity_and_timestamps(
    field: str,
    value: object,
) -> None:
    manifest = _manifest(
        flow_runs=[
            {
                "flow_id": "document_consistency_qc",
                "flow_run_id": "document_consistency_qc_run",
            }
        ]
    )
    manifest[field] = value

    with pytest.raises(ValueError, match=field):
        validate_task_run_manifest(manifest)


@pytest.mark.parametrize("task_run_id", ["../escape", "task/run", "task\\run"])
def test_task_run_path_rejects_unsafe_ids(
    tmp_path: Path,
    task_run_id: str,
) -> None:
    with pytest.raises(ValueError, match="task_run_id"):
        task_run_manifest_path(project_root=tmp_path, task_run_id=task_run_id)


def test_allocate_task_run_id_is_unique_url_safe_and_does_not_persist(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    first = allocate_task_run_id()
    second = allocate_task_run_id()

    assert first.startswith("task_run_")
    assert first != second
    assert re.fullmatch(r"[A-Za-z0-9_]+", first)
    assert not (tmp_path / "runs" / "task_runs").exists()


def test_create_task_run_persists_empty_membership(tmp_path: Path) -> None:
    task_run_id = "task_run_20260920_010203_123456Z_empty"

    path = create_task_run(
        project_root=tmp_path,
        task_run_id=task_run_id,
        task_id="internal_dsur_qc",
    )

    assert path == tmp_path / "runs" / "task_runs" / task_run_id / "task_run.json"
    manifest = load_task_run(project_root=tmp_path, task_run_id=task_run_id)
    assert manifest["schema_version"] == TASK_RUN_SCHEMA_VERSION
    assert manifest["task_id"] == "internal_dsur_qc"
    assert manifest["flow_runs"] == []
    assert manifest["created_at"] == manifest["updated_at"]


def test_create_then_attach_first_flow_run(tmp_path: Path) -> None:
    task_run_id = "task_run_20260920_010203_123456Z_attach_first"
    create_task_run(
        project_root=tmp_path,
        task_run_id=task_run_id,
        task_id="internal_dsur_qc",
    )
    attach_flow_run(
        project_root=tmp_path,
        task_run_id=task_run_id,
        flow_id="document_consistency_qc",
        flow_run_id="document_consistency_qc_first",
    )
    manifest = load_task_run(project_root=tmp_path, task_run_id=task_run_id)
    assert manifest["schema_version"] == TASK_RUN_SCHEMA_VERSION
    assert manifest["flow_runs"] == [
        {
            "flow_id": "document_consistency_qc",
            "flow_run_id": "document_consistency_qc_first",
        }
    ]


def test_attach_upgrades_legacy_schema_version_on_write(tmp_path: Path) -> None:
    task_run_id = "task_run_20260920_010203_123456Z"
    legacy = _manifest(
        flow_runs=[
            {
                "flow_id": "document_consistency_qc",
                "flow_run_id": "document_consistency_qc_first",
            }
        ],
        schema_version=TASK_RUN_SCHEMA_VERSION_0_2_0,
    )
    legacy["task_run_id"] = task_run_id
    save_task_run_manifest(project_root=tmp_path, manifest=legacy)

    attach_flow_run(
        project_root=tmp_path,
        task_run_id=task_run_id,
        flow_id="document_consistency_qc",
        flow_run_id="document_consistency_qc_rerun",
    )

    manifest = load_task_run(project_root=tmp_path, task_run_id=task_run_id)
    assert manifest["schema_version"] == TASK_RUN_SCHEMA_VERSION


def test_create_task_run_for_flow_persists_one_membership(tmp_path: Path) -> None:
    task_run_id = "task_run_20260920_010203_123456Z_parent"

    path = create_task_run_for_flow(
        project_root=tmp_path,
        task_run_id=task_run_id,
        task_id="internal_dsur_qc",
        flow_id="document_consistency_qc",
        flow_run_id="document_consistency_qc_first",
    )

    assert path == tmp_path / "runs" / "task_runs" / task_run_id / "task_run.json"
    manifest = load_task_run(project_root=tmp_path, task_run_id=task_run_id)
    assert manifest["schema_version"] == TASK_RUN_SCHEMA_VERSION
    assert manifest["task_id"] == "internal_dsur_qc"
    assert "capability_id" not in manifest
    assert manifest["created_at"] == manifest["updated_at"]
    assert manifest["flow_runs"] == [
        {
            "flow_id": "document_consistency_qc",
            "flow_run_id": "document_consistency_qc_first",
        }
    ]


def test_attach_flow_run_allows_same_flow_type_with_distinct_execution(
    tmp_path: Path,
) -> None:
    task_run_id = "task_run_20260920_010203_123456Z_parent"
    create_task_run_for_flow(
        project_root=tmp_path,
        task_run_id=task_run_id,
        task_id="internal_dsur_qc",
        flow_id="document_consistency_qc",
        flow_run_id="document_consistency_qc_first",
    )

    attach_flow_run(
        project_root=tmp_path,
        task_run_id=task_run_id,
        flow_id="document_consistency_qc",
        flow_run_id="document_consistency_qc_rerun",
    )

    manifest = load_task_run(project_root=tmp_path, task_run_id=task_run_id)
    assert manifest["flow_runs"] == [
        {
            "flow_id": "document_consistency_qc",
            "flow_run_id": "document_consistency_qc_first",
        },
        {
            "flow_id": "document_consistency_qc",
            "flow_run_id": "document_consistency_qc_rerun",
        },
    ]


def test_attach_flow_run_rejects_duplicate_without_changing_manifest(
    tmp_path: Path,
) -> None:
    task_run_id = "task_run_20260920_010203_123456Z_parent"
    create_task_run_for_flow(
        project_root=tmp_path,
        task_run_id=task_run_id,
        task_id="internal_dsur_qc",
        flow_id="document_consistency_qc",
        flow_run_id="document_consistency_qc_first",
    )
    before = load_task_run(project_root=tmp_path, task_run_id=task_run_id)

    with pytest.raises(ValueError, match="duplicate flow_run_id"):
        attach_flow_run(
            project_root=tmp_path,
            task_run_id=task_run_id,
            flow_id="other_flow",
            flow_run_id="document_consistency_qc_first",
        )

    assert load_task_run(project_root=tmp_path, task_run_id=task_run_id) == before


def test_task_run_schema_0_1_0_is_rejected() -> None:
    legacy = {
        "artifact_type": "task_run",
        "schema_version": "0.1.0",
        "task_run_id": "task_run_20260920_010203_123456Z",
        "capability_id": "internal_dsur",
        "created_at": "2026-09-20T01:02:03Z",
        "updated_at": "2026-09-20T01:02:04Z",
        "flow_runs": [
            {
                "flow_id": "document_consistency_qc",
                "flow_run_id": "document_consistency_qc_run",
            }
        ],
    }
    with pytest.raises(ValueError, match="capability_id"):
        validate_task_run_manifest(legacy)
