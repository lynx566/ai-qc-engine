"""Slice D: Product Task canonical package ownership regression."""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def test_product_start_modules_live_under_task_package() -> None:
    task_root = BACKEND_ROOT / "task" / "clinical_trial_doc_qc"
    for name in (
        "start.py",
        "start_resolution.py",
        "task_input_binding.py",
        "task_run_read.py",
        "definitions.py",
        "catalog.py",
    ):
        assert (task_root / name).is_file()


def test_dcqc_application_no_longer_owns_product_start_modules() -> None:
    app_root = BACKEND_ROOT / "application" / "clinical_trial_doc_consistency_qc"
    for legacy in (
        "start_task.py",
        "task_start_resolution.py",
        "installed_tasks.py",
        "task_ids.py",
        "catalog.py",
    ):
        assert not (app_root / legacy).is_file()


def test_definitions_module_has_no_dcqc_participant_imports() -> None:
    source = (
        BACKEND_ROOT / "task" / "clinical_trial_doc_qc" / "definitions.py"
    ).read_text(encoding="utf-8")
    assert "DocumentConsistencyQcParticipantSlot" not in source
    assert "DocumentConsistencyQcCapabilityConfig" not in source
