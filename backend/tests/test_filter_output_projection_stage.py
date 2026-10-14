"""Filter-output projection runtime stage tests."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from artifacts.filter_output_projection_bundle import (
    FILTER_OUTPUT_PROJECTION_BUNDLE_FILENAME,
    filter_output_projection_step_result_from_bundle,
    validate_filter_output_projection_bundle,
)
from llm.providers.base import LLMRawResult
from plugins.clinical_trial_doc.filter_output_projection import (
    DIRECT_FILTER_OUTPUT_PROJECTION_FACADE,
    build_overview_semantic_decomposition_facade,
)
from plugins.clinical_trial_doc.filter_profiles.ib.clinical_safety_zh import (
    IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH,
)
from plugins.clinical_trial_doc.filter_profiles.ib.overview_zh import (
    IB_OVERVIEW_FILTER_PROFILE_ZH,
)
from runtime.filter_output_projection_stage import run_filter_output_projection_stage
from runtime.io import load_json
from runtime.run_summaries import (
    filter_output_projection_lineage_from_zone_match_bundle,
)
from scripts.stage_runners.filter_output_projection_overview_mock_provider import (
    OverviewStandaloneMockProvider,
)
from tests.test_filter_output_projection_direct import (
    LINEAGE_FILE_HASH,
    _analysis_bundle_for_zone_match,
    _filter_artifacts_for_profile,
    _resolved_direct_job,
)
from tests.test_filter_output_projection_overview import _zone_match_bundle


def test_projection_lineage_from_filter_zone_match_bundle() -> None:
    source_stage, pipeline = filter_output_projection_lineage_from_zone_match_bundle(
        {"stage": "filter"}
    )
    assert source_stage == "filter"
    assert pipeline == [
        "extract",
        "prepare_analysis",
        "filter",
        "filter_output_projection",
    ]


def test_projection_lineage_from_candidate_scope_zone_match_bundle() -> None:
    source_stage, pipeline = filter_output_projection_lineage_from_zone_match_bundle(
        {"stage": "candidate_scope"}
    )
    assert source_stage == "candidate_scope"
    assert pipeline == [
        "extract",
        "prepare_analysis",
        "filter",
        "candidate_scope",
        "filter_output_projection",
    ]


def test_direct_projection_runtime_persists_semantic_artifact(tmp_path: Path) -> None:
    zone_match_bundle, _coverage, _block_manifest, analysis_bundle = (
        _filter_artifacts_for_profile(IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH)
    )
    zone_path = tmp_path / "zone_match_bundle.json"
    zone_path.write_text(
        json.dumps(zone_match_bundle, ensure_ascii=False),
        encoding="utf-8",
    )
    analysis_path = tmp_path / "analysis_bundle.json"
    analysis_path.write_text(
        json.dumps(analysis_bundle, ensure_ascii=False),
        encoding="utf-8",
    )
    output_dir = tmp_path / "projection"

    result = run_filter_output_projection_stage(
        filter_job_id=IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH.filter_job_id,
        resolved_job=_resolved_direct_job(IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH),
        zone_match_bundle_path=zone_path,
        analysis_bundle_path=analysis_path,
        facade=DIRECT_FILTER_OUTPUT_PROJECTION_FACADE,
        output_dir=output_dir,
        run_id="projection_runtime_test",
    )

    bundle_path = output_dir / FILTER_OUTPUT_PROJECTION_BUNDLE_FILENAME
    assert bundle_path.is_file()
    bundle = load_json(bundle_path)
    validate_filter_output_projection_bundle(bundle)
    for forbidden in (
        "consumed",
        "route_status",
        "execution_status",
        "not_installed_consumer",
    ):
        assert forbidden not in bundle

    roundtrip = filter_output_projection_step_result_from_bundle(bundle)
    assert roundtrip.filter_job_id == result.filter_job_id
    assert len(roundtrip.projected_sources) == len(result.step_result.projected_sources)
    assert roundtrip.projected_sources[0].representation_kind == "raw_source"
    assert roundtrip.projected_sources[0].semantic_module_id == "clinical_safety"

    summary = load_json(result.run_summary_path)
    assert summary["source_stage"] == "filter"
    assert summary["pipeline"] == [
        "extract",
        "prepare_analysis",
        "filter",
        "filter_output_projection",
    ]
    assert summary["llm_invocations"] == []


def test_overview_projection_runtime_persists_llm_invocation(tmp_path: Path) -> None:
    zone_match_bundle = _zone_match_bundle(
        blocks=[
            {
                "block_id": "P0001",
                "kind": "paragraph",
                "analysis_text": "Summary safety information.",
                "heading_path": ["Summary"],
            }
        ]
    )
    zone_match_bundle["file_hash"] = LINEAGE_FILE_HASH
    analysis_bundle = _analysis_bundle_for_zone_match(zone_match_bundle)
    zone_path = tmp_path / "zone_match_bundle.json"
    zone_path.write_text(
        json.dumps(zone_match_bundle, ensure_ascii=False),
        encoding="utf-8",
    )
    analysis_path = tmp_path / "analysis_bundle.json"
    analysis_path.write_text(
        json.dumps(analysis_bundle, ensure_ascii=False),
        encoding="utf-8",
    )
    output_dir = tmp_path / "projection"
    job = _resolved_direct_job(IB_OVERVIEW_FILTER_PROFILE_ZH)
    facade = build_overview_semantic_decomposition_facade(
        llm_provider=OverviewStandaloneMockProvider(),
        llm_execution_config={
            "config_id": "clinical_trial_doc_fop_overview",
            "profile_id": "qwen3_7_plus_2026_05_26",
            "thinking": None,
            "response_format": "json_object",
            "seed": 1234,
        },
    )

    result = run_filter_output_projection_stage(
        filter_job_id=IB_OVERVIEW_FILTER_PROFILE_ZH.filter_job_id,
        resolved_job=job,
        zone_match_bundle_path=zone_path,
        analysis_bundle_path=analysis_path,
        facade=facade,
        output_dir=output_dir,
        run_id="projection_runtime_test",
    )

    summary = load_json(result.run_summary_path)
    assert len(summary["llm_invocations"]) == 1
    invocation = summary["llm_invocations"][0]
    assert invocation["status"] == "success"
    assert invocation["attempt_index"] == 1
    assert invocation["provider"] == "mock"
    assert invocation["model"] == "overview-standalone-mock"
    assert invocation["config_id"] == "clinical_trial_doc_fop_overview"
    assert invocation["profile_id"] == "qwen3_7_plus_2026_05_26"
    assert isinstance(invocation["elapsed_ms"], int)


@dataclass(frozen=True)
class _FailingOverviewProvider:
    def generate(self, messages: list[dict[str, str]]) -> LLMRawResult:
        raise TimeoutError("overview timed out")


@pytest.mark.parametrize("transport_retry", [False, True])
def test_overview_provider_failure_persists_invocation_before_reraising(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, transport_retry: bool,
) -> None:
    from tests.test_bailian_transient_retry import provider, timeout
    import openai

    failing_provider = _FailingOverviewProvider()
    expected_error = TimeoutError
    expected_message = "overview timed out"
    if transport_retry:
        failing_provider, create, _ = provider(monkeypatch, [timeout(), timeout()])
        ticks = iter([0., 300., 300., 600.])
        monkeypatch.setattr("llm.invocation.perf_counter", lambda: next(ticks))
        expected_error = openai.APITimeoutError
        expected_message = "Request timed out"
    zone_match_bundle = _zone_match_bundle(
        blocks=[
            {
                "block_id": "P0001",
                "kind": "paragraph",
                "analysis_text": "Summary safety information.",
                "heading_path": ["Summary"],
            }
        ]
    )
    zone_match_bundle["file_hash"] = LINEAGE_FILE_HASH
    analysis_bundle = _analysis_bundle_for_zone_match(zone_match_bundle)
    zone_path = tmp_path / "zone_match_bundle.json"
    zone_path.write_text(json.dumps(zone_match_bundle), encoding="utf-8")
    analysis_path = tmp_path / "analysis_bundle.json"
    analysis_path.write_text(json.dumps(analysis_bundle), encoding="utf-8")
    output_dir = tmp_path / "projection"
    facade = build_overview_semantic_decomposition_facade(
        llm_provider=failing_provider,
        llm_execution_config={
            "config_id": "clinical_trial_doc_fop_overview",
            "profile_id": "qwen3_7_plus_2026_05_26",
        },
    )

    with pytest.raises(expected_error, match=expected_message):
        run_filter_output_projection_stage(
            filter_job_id=IB_OVERVIEW_FILTER_PROFILE_ZH.filter_job_id,
            resolved_job=_resolved_direct_job(IB_OVERVIEW_FILTER_PROFILE_ZH),
            zone_match_bundle_path=zone_path,
            analysis_bundle_path=analysis_path,
            facade=facade,
            output_dir=output_dir,
            run_id="projection_failure_test",
        )

    summary = load_json(output_dir / "run_summary.json")
    assert summary["status"] == "failed"
    if transport_retry:
        assert create.call_count == 2
        assert [r["attempt_index"] for r in summary["llm_invocations"]] == [1, 2]
        assert [r["elapsed_ms"] for r in summary["llm_invocations"]] == [300000, 300000]
        assert [r["error_type"] for r in summary["llm_invocations"]] == ["APITimeoutError"] * 2
        assert [r["status"] for r in summary["llm_invocations"]] == ["failed"] * 2
        return
    invocation = summary["llm_invocations"][0]
    assert invocation["status"] == "failed"
    assert invocation["error_type"] == "TimeoutError"
    assert invocation["error_message"] == "overview timed out"
    assert isinstance(invocation["elapsed_ms"], int)
