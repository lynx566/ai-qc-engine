"""Boundary regressions for narrow Evidence Comparison ownership."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def test_comparison_finding_assessment_is_owned_by_aggregate_evidence() -> None:
    nested_module = (
        "plugins.clinical_trial_doc.evidence_comparison.clinical_safety."
        "aggregate_evidence.comparison_finding_assessment"
    )
    imported = importlib.import_module(nested_module)

    assert imported.__name__ == nested_module
    assert not (
        BACKEND_ROOT
        / "plugins"
        / "clinical_trial_doc"
        / "evidence_comparison"
        / "clinical_safety"
        / "comparison_finding_assessment"
    ).exists()


def test_comparison_mode_id_lives_in_aggregate_evidence_specialization() -> None:
    module = importlib.import_module(
        "plugins.clinical_trial_doc.evidence_comparison.clinical_safety."
        "aggregate_evidence.comparison_mode"
    )
    assert hasattr(module, "ComparisonModeId")
