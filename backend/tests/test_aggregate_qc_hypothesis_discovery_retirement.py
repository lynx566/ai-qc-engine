from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def test_legacy_planning_production_path_is_retired() -> None:
    retired = [
        BACKEND_ROOT / "artifacts" / "evidence_comparison" / "aggregate_comparison_plan.py",
        BACKEND_ROOT / "plugins" / "clinical_trial_doc" / "evidence_comparison" / "comparison_planning",
        BACKEND_ROOT / "runtime" / "evidence_comparison_aggregate_comparison_planning_stage.py",
        BACKEND_ROOT / "scripts" / "stage_runners" / "aggregate_comparison_planning_runner.py",
        BACKEND_ROOT / "scripts" / "dev" / "preview_aggregate_comparison_planning.py",
    ]
    assert all(
        not path.exists() if path.suffix else not any(path.rglob("*.py"))
        for path in retired
    )


def test_active_production_python_has_no_retired_operation_symbols() -> None:
    active_roots = [
        BACKEND_ROOT / "artifacts",
        BACKEND_ROOT / "steps",
        BACKEND_ROOT / "plugins",
        BACKEND_ROOT / "runtime",
        BACKEND_ROOT / "scripts",
    ]
    violations = []
    for root in active_roots:
        for path in root.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            if "aggregate_comparison_planning" in text or "aggregate_comparison_plan" in text:
                violations.append(path.relative_to(BACKEND_ROOT).as_posix())
    assert violations == []
