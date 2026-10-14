"""Installed Doc Meta dependency resolution."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from application.clinical_trial_doc_consistency_qc.composition import (
    build_clinical_trial_doc_consistency_qc_application_composition,
)
from application.clinical_trial_doc_consistency_qc.doc_meta_installation import (
    resolve_installed_doc_meta_dependencies,
)
from scripts.stage_runners import doc_meta_runner


def test_resolve_installed_doc_meta_dependencies_returns_profile_and_builder() -> None:
    installed = resolve_installed_doc_meta_dependencies()

    assert installed.profile.name == "clinical_trial_doc.meta.zh.v0_1"
    assert callable(installed.summary_builder)


def test_composition_uses_same_installed_doc_meta_dependencies() -> None:
    installed = resolve_installed_doc_meta_dependencies()
    composition = build_clinical_trial_doc_consistency_qc_application_composition()

    assert composition.doc_meta_profile is installed.profile
    assert composition.doc_meta_summary_builder is installed.summary_builder


def test_doc_meta_runner_resolves_same_installed_doc_meta_dependencies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    installed = resolve_installed_doc_meta_dependencies()
    resolve_calls: list[object] = []
    stage_calls: list[dict[str, object]] = []

    def capture_resolve():
        resolve_calls.append("called")
        return installed

    def capture_stage(**kwargs):
        stage_calls.append(kwargs)
        return {
            "output_dir": "",
            "doc_meta_bundle_path": "",
            "document_context_preview_path": "",
            "run_summary_path": "",
        }

    monkeypatch.setattr(
        doc_meta_runner,
        "resolve_installed_doc_meta_dependencies",
        capture_resolve,
    )
    monkeypatch.setattr(doc_meta_runner, "run_doc_meta_stage", capture_stage)
    monkeypatch.setattr(
        doc_meta_runner,
        "parse_args",
        lambda: SimpleNamespace(
            analysis_bundle="analysis_bundle.json",
            analysis_bundle_dir=None,
            output_dir=None,
        ),
    )
    monkeypatch.setattr(
        doc_meta_runner,
        "resolve_artifact_file",
        lambda *args, **kwargs: Path("analysis_bundle.json"),
    )
    monkeypatch.setattr(
        doc_meta_runner,
        "load_json",
        lambda path: {"doc_id": "doc_test", "stage": "prepare_analysis"},
    )
    monkeypatch.setattr(
        doc_meta_runner,
        "snapshot_git_provenance_before_run",
        lambda **_: {"git_commit": "abc", "git_dirty": False},
    )
    monkeypatch.setattr(doc_meta_runner, "utc_run_stamp", lambda: "20260825_000000_000000Z")
    monkeypatch.setattr(
        doc_meta_runner,
        "allocate_session_dir",
        lambda *args, **kwargs: Path("runs/doc_meta/20260825_000000_000000Z"),
    )
    monkeypatch.setattr(
        doc_meta_runner,
        "resolve_index_root",
        lambda **kwargs: Path("runs/doc_meta/20260825_000000_000000Z"),
    )
    monkeypatch.setattr(
        doc_meta_runner,
        "build_stage_run_layout",
        lambda **kwargs: SimpleNamespace(run_id="doc_meta_doc_test"),
    )
    monkeypatch.setattr(
        doc_meta_runner,
        "build_doc_meta_session_run_naming",
        lambda **kwargs: SimpleNamespace(run_id="doc_meta_doc_test"),
    )
    monkeypatch.setattr(
        doc_meta_runner,
        "ensure_stage_doc_run_dir",
        lambda *args, **kwargs: Path("runs/doc_meta/20260825_000000_000000Z/doc_test"),
    )
    monkeypatch.setattr(
        doc_meta_runner,
        "build_doc_meta_index_document",
        lambda **kwargs: {},
    )
    monkeypatch.setattr(
        doc_meta_runner,
        "write_run_index",
        lambda *args, **kwargs: Path("runs/doc_meta/20260825_000000_000000Z/index.json"),
    )
    monkeypatch.setattr(
        doc_meta_runner,
        "posix_relative",
        lambda path, root: path.as_posix(),
    )

    doc_meta_runner.main()

    assert resolve_calls == ["called"]
    assert len(stage_calls) == 1
    assert stage_calls[0]["profile"] is installed.profile
    assert stage_calls[0]["build_summary"] is installed.summary_builder
