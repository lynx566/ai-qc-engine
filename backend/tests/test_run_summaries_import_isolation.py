"""Import-boundary regressions for shared run-summary helpers."""

from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_TAGGING_MODULES = (
    "core.tagging.review_gate",
    "core.tagging.taggers.llm_api_helpers",
    "core.tagging.taggers.llm_debug_artifacts",
)


def _run_isolated(script: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", textwrap.dedent(script)],
        cwd=BACKEND_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_shared_run_summaries_import_does_not_load_retired_tagging_helpers() -> None:
    forbidden = ", ".join(repr(module) for module in FORBIDDEN_TAGGING_MODULES)
    result = _run_isolated(
        f"""
        import sys

        import runtime.run_summaries

        assert "runtime.run_summaries" in sys.modules
        for module in ({forbidden}):
            assert module not in sys.modules
        """
    )

    assert result.returncode == 0, result.stderr


def test_assess_summary_preserves_api_usability_fields() -> None:
    result = _run_isolated(
        """
        import tempfile
        from pathlib import Path

        from runtime.run_summaries import build_aggregate_evidence_assess_run_summary

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            summary = build_aggregate_evidence_assess_run_summary(
                run_id="assess_test_run",
                assessment_input={
                    "doc_id": "doc_test",
                    "zone_key": "ib_clinical_safety_zh",
                    "file_hash": "sha256:test",
                    "units": [],
                },
                assessment_input_path=temp_path / "assessment_input.json",
                scope_assessments_path=temp_path / "scope_assessments.json",
                scope_assessments={
                    "scope_assessment_count": 0,
                    "scope_assessments": [],
                    "api_result": {
                        "api_result_usable": True,
                        "fallback_used": False,
                        "fallback_reason": None,
                        "fallback_source": None,
                    },
                },
                scope_assessment_review_path=None,
                scope_assessment_review=None,
                assessment_profile_name="test_profile",
                llm_mode="api",
                zone_key="ib_clinical_safety_zh",
                phase="assess",
                completed_operation="aggregate_evidence.assess_heading_scopes",
                git_provenance={"git_commit": "test", "git_dirty": False},
                paths_base=temp_path,
            )

        assert summary["api_result_usable"] is True
        assert summary["fallback_used"] is False
        assert summary["fallback_reason"] is None
        assert summary["fallback_source"] is None
        """
    )

    assert result.returncode == 0, result.stderr
