from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from runtime.upstream_privacy_context import resolve_upstream_privacy_runtime_context


def test_resolve_upstream_privacy_runtime_context_from_run_summary(tmp_path: Path) -> None:
    analysis_dir = tmp_path / "analysis"
    analysis_dir.mkdir()
    (analysis_dir / "analysis_bundle.json").write_text("{}", encoding="utf-8")
    (analysis_dir / "run_summary.json").write_text(
        json.dumps(
            {
                "privacy_transform": {
                    "settings": {"date_shift_offset_days": 17},
                },
                "stats": {"clinical_program_id": "clinical_program_001"},
            }
        ),
        encoding="utf-8",
    )
    upstream = resolve_upstream_privacy_runtime_context(
        analysis_bundle_path=analysis_dir / "analysis_bundle.json",
    )
    assert upstream.date_shift_offset_days == 17


def test_resolve_upstream_privacy_runtime_context_from_privacy_audit(tmp_path: Path) -> None:
    analysis_dir = tmp_path / "analysis"
    analysis_dir.mkdir()
    (analysis_dir / "analysis_bundle.json").write_text("{}", encoding="utf-8")
    (analysis_dir / "privacy_audit.json").write_text(
        json.dumps({"date_shift": {"enabled": True, "offset_days": 17}}),
        encoding="utf-8",
    )
    upstream = resolve_upstream_privacy_runtime_context(
        analysis_bundle_path=analysis_dir / "analysis_bundle.json",
    )
    assert upstream.date_shift_offset_days == 17
