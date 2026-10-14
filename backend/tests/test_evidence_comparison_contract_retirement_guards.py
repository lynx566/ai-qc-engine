"""Retirement guards for Evidence Comparison contract migration."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent

FORBIDDEN_PATTERNS = [
    "comparison_point_canonicalization",
    "candidate_focus_canonicalized",
    "ComparisonPointDiscovery",
    "search_view_id",
    "comparison_point_discovery",
    "ComparisonPoint",
]

SCAN_PATHS = [
    BACKEND_ROOT / "plugins" / "clinical_trial_doc" / "evidence_comparison",
    BACKEND_ROOT / "runtime" / "evidence_comparison",
    BACKEND_ROOT / "scripts" / "stage_runners" / "evidence_comparison",
    BACKEND_ROOT / "application" / "clinical_trial_doc_consistency_qc",
    BACKEND_ROOT / "artifacts" / "evidence_comparison",
    BACKEND_ROOT / "tests",
]

ALLOWLIST_SUBSTRINGS = [
    "runs/evidence_comparison",
    "contract_retirement_guards",
]


def test_active_production_sources_do_not_reintroduce_retired_vocabulary() -> None:
    hits: list[str] = []
    for scan_root in SCAN_PATHS:
        assert scan_root.is_dir(), f"guard scan root must exist: {scan_root}"
        for path in scan_root.rglob("*.py"):
            rel = path.relative_to(REPO_ROOT).as_posix()
            if any(token in rel for token in ALLOWLIST_SUBSTRINGS):
                continue
            text = path.read_text(encoding="utf-8")
            for pattern in FORBIDDEN_PATTERNS:
                if pattern in text:
                    hits.append(f"{rel}: {pattern}")
    assert hits == [], "retired vocabulary found:\n" + "\n".join(hits)
