"""Tests for Comparison Finding Assessment execution runtime."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Condition, Event
from types import SimpleNamespace
from unittest.mock import patch

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from artifacts.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence import (
    build_aggregate_comparison_evidence,
)
from llm.providers.base import LLMRawResult
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.comparison_finding_assessment import (
    ComparisonFindingAssessmentGroup,
    ComparisonFindingAssessmentJob,
    filter_eligible_candidates,
    materialize_comparison_finding_assessment_llm_input,
    parse_and_validate_comparison_finding_assessment_response,
    resolve_formal_prompt_id,
)
from runtime.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence.comparison_finding_assessment import (
    run_comparison_finding_assessment_execution,
)
from runtime.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence.comparison_finding_assessment_plan import (
    load_comparison_finding_assessment_jobs_from_plan,
    run_comparison_finding_assessment_plan_inspection,
)
from runtime.io import load_json, save_json
from scripts.stage_runners.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence import (
    comparison_finding_assessment_runner,
)
from scripts.stage_runners.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence.comparison_finding_assessment_mock_provider import (
    ComparisonFindingAssessmentStandaloneMockProvider,
)

_FIXTURE_ROOT = (
    BACKEND_ROOT
    / "tests"
    / "fixtures"
    / "evidence_comparison"
    / "clinical_safety"
    / "aggregate_evidence"
)
_INTERNAL_EVIDENCE = (
    _FIXTURE_ROOT / "internal_dsur" / "aggregate_comparison_evidence.json"
)
_CROSS_EVIDENCE = (
    _FIXTURE_ROOT / "dsur_updated_ib" / "aggregate_comparison_evidence.json"
)


class _RecordingProvider:
    def __init__(self) -> None:
        self.calls: list[list[dict[str, str]]] = []

    def generate(self, messages: list[dict[str, str]]) -> LLMRawResult:
        self.calls.append(messages)
        user_content = messages[-1]["content"]
        alias = "T0001"
        if f"[{alias}]" not in user_content:
            first_line = next(
                (line for line in user_content.splitlines() if "[T" in line),
                user_content,
            )
            start = first_line.index("[T") + 1
            end = first_line.index("]", start)
            alias = first_line[start:end]
        payload = {
            "candidates": [
                {
                    "candidate_focus": "测试比较点",
                    "label": "fail",
                    "trigger_sentence_aliases": [alias],
                }
            ]
        }
        return LLMRawResult(
            provider_name="recording-mock",
            model="recording-mock",
            raw_text=json.dumps(payload, ensure_ascii=False),
        )


def _first_sentence_alias(messages: list[dict[str, str]]) -> str:
    match = re.search(r"\[(T\d{4})\]", messages[-1]["content"])
    if match is None:
        raise AssertionError("expected a sentence alias in rendered provider messages")
    return match.group(1)


def _valid_raw_result(messages: list[dict[str, str]]) -> LLMRawResult:
    alias = _first_sentence_alias(messages)
    return LLMRawResult(
        provider_name="controlled-mock",
        model="controlled-mock",
        raw_text=json.dumps(
            {
                "candidates": [
                    {
                        "candidate_focus": f"candidate for {alias}",
                        "label": "fail",
                        "trigger_sentence_aliases": [alias],
                    }
                ]
            }
        ),
    )


class _BlockingConcurrencyProvider:
    """Hold calls open so tests can observe the real provider-call overlap."""

    def __init__(self) -> None:
        self._condition = Condition()
        self._release = Event()
        self.active_call_count = 0
        self.peak_active_call_count = 0

    def generate(self, messages: list[dict[str, str]]) -> LLMRawResult:
        with self._condition:
            self.active_call_count += 1
            self.peak_active_call_count = max(
                self.peak_active_call_count,
                self.active_call_count,
            )
            self._condition.notify_all()
        try:
            if not self._release.wait(timeout=10):
                raise AssertionError("test did not release blocked provider calls")
            return _valid_raw_result(messages)
        finally:
            with self._condition:
                self.active_call_count -= 1
                self._condition.notify_all()

    def wait_for_peak(self, expected: int) -> bool:
        with self._condition:
            return self._condition.wait_for(
                lambda: self.peak_active_call_count >= expected,
                timeout=5,
            )

    def release(self) -> None:
        self._release.set()


class _CompletionOrderProvider:
    """Expose per-job gates so tests determine completion order without sleeps."""

    def __init__(self, aliases: tuple[str, ...]) -> None:
        self._condition = Condition()
        self._release_by_alias = {alias: Event() for alias in aliases}
        self.entered_aliases: set[str] = set()
        self.completed_aliases: list[str] = []

    def generate(self, messages: list[dict[str, str]]) -> LLMRawResult:
        alias = _first_sentence_alias(messages)
        release = self._release_by_alias[alias]
        with self._condition:
            self.entered_aliases.add(alias)
            self._condition.notify_all()
        if not release.wait(timeout=10):
            raise AssertionError(f"test did not release provider call for {alias}")
        with self._condition:
            self.completed_aliases.append(alias)
            self._condition.notify_all()
        return _valid_raw_result(messages)

    def wait_until_all_entered(self) -> bool:
        with self._condition:
            return self._condition.wait_for(
                lambda: len(self.entered_aliases) == len(self._release_by_alias),
                timeout=5,
            )

    def release_and_wait(self, alias: str, completed_count: int) -> bool:
        self._release_by_alias[alias].set()
        with self._condition:
            return self._condition.wait_for(
                lambda: len(self.completed_aliases) >= completed_count,
                timeout=5,
            )

    def release_all(self) -> None:
        for release in self._release_by_alias.values():
            release.set()


class _MixedOutcomeProvider:
    def generate(self, messages: list[dict[str, str]]) -> LLMRawResult:
        alias = _first_sentence_alias(messages)
        if alias == "T0016":
            raise RuntimeError("provider down")
        if alias == "T0019":
            return LLMRawResult(
                provider_name="mixed-mock",
                model="mixed-mock",
                raw_text="not-json",
            )
        if alias == "T0028":
            return LLMRawResult(
                provider_name="mixed-mock",
                model="mixed-mock",
                raw_text=json.dumps(
                    {
                        "candidates": [
                            {
                                "candidate_focus": "out of job alias",
                                "label": "fail",
                                "trigger_sentence_aliases": ["T9999"],
                            }
                        ]
                    }
                ),
            )
        return _valid_raw_result(messages)


def _minimal_evidence() -> dict:
    return build_aggregate_comparison_evidence(
        participants=[
            {
                "role_id": "source",
                "aggregate_evidence_source_bundle_id": "bundle",
                "doc_id": "doc",
                "file_hash": "sha256:test",
                "scopes": [
                    {
                        "scope_id": "HS0001",
                        "scope_alias": "H0001",
                        "heading_path": ["Heading"],
                        "units": [
                            {
                                "unit_id": "TU0001",
                                "unit_alias": "U0001",
                                "sentences": [
                                    {
                                        "sentence_id": "C0001:S001",
                                        "sentence_alias": "T0001",
                                        "text": "one",
                                    }
                                ],
                            }
                        ],
                    }
                ],
            }
        ],
    )


def _create_plan_run(
    tmp_path: Path,
    *,
    evidence: Path | str,
    capability_id: str,
    run_id: str = "plan_test",
) -> Path:
    report = run_comparison_finding_assessment_plan_inspection(
        project_root=BACKEND_ROOT,
        evidence=evidence,
        capability_id=capability_id,
        output_dir=tmp_path / "plan",
        run_id=run_id,
    )
    return report.result.output_dir


def test_execution_uses_existing_renderer_not_llm_inputs_file(tmp_path: Path) -> None:
    evidence_path = tmp_path / "aggregate_comparison_evidence.json"
    save_json(evidence_path, _minimal_evidence())
    plan_run_dir = _create_plan_run(
        tmp_path,
        evidence=evidence_path,
        capability_id="internal_dsur",
    )
    provider = _RecordingProvider()
    with patch(
        "runtime.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence.comparison_finding_assessment.materialize_comparison_finding_assessment_llm_input",
        wraps=materialize_comparison_finding_assessment_llm_input,
    ) as renderer:
        report = run_comparison_finding_assessment_execution(
            project_root=BACKEND_ROOT,
            plan_run_dir=plan_run_dir,
            llm_mode="mock",
            provider=provider,
            output_dir=tmp_path / "run",
            run_id="test_renderer",
            comparison_modes=["scope_local"],
            max_jobs=1,
        )
    renderer.assert_called()
    job_dir = report.result.job_results[0].job_dir
    assert (job_dir / "evidence_input.txt").is_file()
    assert provider.calls
    assert provider.calls[0][-1]["content"] == (
        job_dir / "evidence_input.txt"
    ).read_text(encoding="utf-8")


def test_mock_provider_call_count_matches_executed_jobs(tmp_path: Path) -> None:
    plan_run_dir = _create_plan_run(
        tmp_path,
        evidence=_INTERNAL_EVIDENCE,
        capability_id="internal_dsur",
    )
    provider = _RecordingProvider()
    report = run_comparison_finding_assessment_execution(
        project_root=BACKEND_ROOT,
        plan_run_dir=plan_run_dir,
        llm_mode="mock",
        provider=provider,
        output_dir=tmp_path / "run",
        run_id="test_counts",
        comparison_modes=["scope_local"],
        max_jobs=2,
    )
    assert len(provider.calls) == 2
    assert len(report.result.job_results) == 2
    assert all(
        result.comparison_mode_id == "scope_local" for result in report.result.job_results
    )
    assert [result.frozen_job_index for result in report.result.job_results] == [1, 2]


@pytest.mark.parametrize(
    ("comparison_mode_id", "expected_prompt_id"),
    [
        ("ib_to_dsur", "comparison_finding_assessment.ib_to_dsur"),
        ("dsur_to_ib", "comparison_finding_assessment.dsur_to_ib"),
    ],
)
def test_prompt_selection_follows_comparison_mode_mapping(
    tmp_path: Path,
    comparison_mode_id: str,
    expected_prompt_id: str,
) -> None:
    plan_run_dir = _create_plan_run(
        tmp_path,
        evidence=_CROSS_EVIDENCE,
        capability_id="dsur_updated_ib",
        run_id=f"plan_{comparison_mode_id}",
    )
    provider = _RecordingProvider()
    report = run_comparison_finding_assessment_execution(
        project_root=BACKEND_ROOT,
        plan_run_dir=plan_run_dir,
        llm_mode="mock",
        provider=provider,
        output_dir=tmp_path / f"run_{comparison_mode_id}",
        run_id="test_mapping",
        comparison_modes=[comparison_mode_id],
        max_jobs=1,
    )
    result = report.result.job_results[0]
    assert result.comparison_mode_id == comparison_mode_id
    assert result.prompt_id == expected_prompt_id


def test_fail_candidate_passes_validation() -> None:
    validated = parse_and_validate_comparison_finding_assessment_response(
        json.dumps(
            {
                "candidates": [
                    {
                        "candidate_focus": "不一致",
                        "label": "fail",
                        "trigger_sentence_aliases": ["T0001"],
                    }
                ]
            }
        ),
    )
    assert validated.candidates[0].trigger_sentence_aliases == ("T0001",)
    assert validated.candidates[0].label == "fail"


@pytest.mark.parametrize("label", ["fail", "need_review"])
def test_valid_candidates_accept_assessment_labels(label: str) -> None:
    validated = parse_and_validate_comparison_finding_assessment_response(
        json.dumps(
            {
                "candidates": [
                    {
                        "candidate_focus": "一致",
                        "label": label,
                        "trigger_sentence_aliases": ["T0001"],
                    }
                ]
            }
        ),
    )
    assert validated.candidates[0].label == label


def test_pass_label_fails_validation() -> None:
    with pytest.raises(ValueError, match="must be one of"):
        parse_and_validate_comparison_finding_assessment_response(
            json.dumps(
                {
                    "candidates": [
                        {
                            "candidate_focus": "一致",
                            "label": "pass",
                            "trigger_sentence_aliases": ["T0001"],
                        }
                    ]
                }
            ),
        )


def test_empty_candidates_passes_validation() -> None:
    validated = parse_and_validate_comparison_finding_assessment_response(
        json.dumps({"candidates": []}),
    )
    assert validated.candidates == ()


def test_missing_label_fails_validation() -> None:
    with pytest.raises(ValueError, match="candidate_focus, label"):
        parse_and_validate_comparison_finding_assessment_response(
            json.dumps(
                {
                    "candidates": [
                        {
                            "candidate_focus": "一致",
                            "trigger_sentence_aliases": ["T0001"],
                        }
                    ]
                }
            ),
        )


def test_unknown_label_fails_validation() -> None:
    with pytest.raises(ValueError, match="must be one of"):
        parse_and_validate_comparison_finding_assessment_response(
            json.dumps(
                {
                    "candidates": [
                        {
                            "candidate_focus": "一致",
                            "label": "unknown",
                            "trigger_sentence_aliases": ["T0001"],
                        }
                    ]
                }
            ),
        )


def test_out_of_job_alias_passes_structure_but_drops_in_eligibility() -> None:
    evidence = _minimal_evidence()
    job = ComparisonFindingAssessmentJob(
        comparison_mode_id="scope_local",
        groups=(
            ComparisonFindingAssessmentGroup(
                group_role="scope",
                scope_aliases=("H0001",),
            ),
        ),
    )
    validated = parse_and_validate_comparison_finding_assessment_response(
        json.dumps(
            {
                "candidates": [
                    {
                        "candidate_focus": "越界",
                        "label": "fail",
                        "trigger_sentence_aliases": ["T0099"],
                    }
                ]
            }
        ),
    )
    result = filter_eligible_candidates(
        validated,
        job=job,
        aggregate_comparison_evidence=evidence,
    )
    assert result.accepted_candidate_count == 0
    assert result.dropped_candidate_count == 1
    assert result.dropped_candidates[0].reason == "alias_outside_job_input"


def test_malformed_json_records_failure(tmp_path: Path) -> None:
    class _BrokenProvider:
        def generate(self, messages: list[dict[str, str]]) -> LLMRawResult:
            return LLMRawResult(
                provider_name="broken",
                model="broken",
                raw_text="not-json",
            )

    plan_run_dir = _create_plan_run(
        tmp_path,
        evidence=_INTERNAL_EVIDENCE,
        capability_id="internal_dsur",
    )
    report = run_comparison_finding_assessment_execution(
        project_root=BACKEND_ROOT,
        plan_run_dir=plan_run_dir,
        llm_mode="mock",
        provider=_BrokenProvider(),
        output_dir=tmp_path / "run",
        run_id="test_failure",
        comparison_modes=["scope_local"],
        max_jobs=1,
    )
    result = report.result.job_results[0]
    assert result.status == "failed"
    assert result.parse_status == "failed"
    assert (result.job_dir / "parse_error.txt").is_file()
    summary = load_json(report.result.run_summary_path)
    assert summary["stats"]["failed_count"] == 1


def test_provider_failure_persists_debug_failure(tmp_path: Path) -> None:
    class _RaisingProvider:
        def generate(self, messages: list[dict[str, str]]) -> LLMRawResult:
            raise RuntimeError("provider down")

    plan_run_dir = _create_plan_run(
        tmp_path,
        evidence=_INTERNAL_EVIDENCE,
        capability_id="internal_dsur",
    )
    report = run_comparison_finding_assessment_execution(
        project_root=BACKEND_ROOT,
        plan_run_dir=plan_run_dir,
        llm_mode="mock",
        provider=_RaisingProvider(),
        output_dir=tmp_path / "run",
        run_id="test_provider_failure",
        comparison_modes=["scope_local"],
        max_jobs=1,
    )
    result = report.result.job_results[0]
    assert result.status == "failed"
    assert (result.job_dir / "debug" / "failure.json").is_file()


def test_formal_prompt_id_matches_comparison_mode() -> None:
    assert (
        resolve_formal_prompt_id("focus_comparison")
        == "comparison_finding_assessment.focus_comparison"
    )
    assert (
        resolve_formal_prompt_id("ib_to_dsur")
        == "comparison_finding_assessment.ib_to_dsur"
    )
    assert (
        resolve_formal_prompt_id("dsur_to_ib")
        == "comparison_finding_assessment.dsur_to_ib"
    )


def test_execution_does_not_replan(tmp_path: Path) -> None:
    plan_run_dir = _create_plan_run(
        tmp_path,
        evidence=_INTERNAL_EVIDENCE,
        capability_id="internal_dsur",
    )
    with (
        patch(
            "plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.comparison_finding_assessment.plan_comparison_finding_assessment_jobs",
            side_effect=AssertionError("execution must not replan"),
        ),
        patch(
            "application.clinical_trial_doc_consistency_qc.comparison_finding_assessment_installation.resolve_installed_comparison_finding_assessment_config",
            side_effect=AssertionError("execution must not resolve discovery config"),
        ),
    ):
        run_comparison_finding_assessment_execution(
            project_root=BACKEND_ROOT,
            plan_run_dir=plan_run_dir,
            llm_mode="mock",
            provider=_RecordingProvider(),
            output_dir=tmp_path / "run",
            run_id="no_replan",
            comparison_modes=["scope_local"],
            max_jobs=1,
        )


def test_evidence_mismatch_fails_fast(tmp_path: Path) -> None:
    plan_run_dir = _create_plan_run(
        tmp_path,
        evidence=_INTERNAL_EVIDENCE,
        capability_id="internal_dsur",
    )
    summary_path = plan_run_dir / "run_summary.json"
    summary = load_json(summary_path)
    summary["inputs"]["participants"][0]["file_hash"] = "sha256:mutated"
    save_json(summary_path, summary)
    with pytest.raises(ValueError, match="participant provenance mismatch"):
        run_comparison_finding_assessment_execution(
            project_root=BACKEND_ROOT,
            plan_run_dir=plan_run_dir,
            llm_mode="mock",
            provider=_RecordingProvider(),
            output_dir=tmp_path / "run",
            run_id="mismatch",
            comparison_modes=["scope_local"],
            max_jobs=1,
        )


def test_execution_records_source_plan_lineage(tmp_path: Path) -> None:
    plan_run_dir = _create_plan_run(
        tmp_path,
        evidence=_INTERNAL_EVIDENCE,
        capability_id="internal_dsur",
        run_id="lineage_plan",
    )
    report = run_comparison_finding_assessment_execution(
        project_root=BACKEND_ROOT,
        plan_run_dir=plan_run_dir,
        llm_mode="mock",
        provider=_RecordingProvider(),
        output_dir=tmp_path / "run",
        run_id="lineage_exec",
        comparison_modes=["scope_local"],
        max_jobs=1,
    )
    summary = load_json(report.result.run_summary_path)
    assert summary["upstream_run_id"] == "lineage_plan"
    assert summary["inputs"]["source_plan_run"]["run_id"] == "lineage_plan"
    assert summary["inputs"]["source_plan_run"]["capability_id"] == "internal_dsur"
    assert summary["inputs"]["aggregate_comparison_evidence"]["resolved_from"] == (
        "source_plan_run"
    )
    _, frozen_jobs = load_comparison_finding_assessment_jobs_from_plan(plan_run_dir)
    assert summary["stats"]["frozen_job_count"] == len(frozen_jobs)
    assert summary["stats"]["executed_job_count"] == 1
    assert not (
        report.result.output_dir / "comparison_finding_assessment_jobs.json"
    ).exists()


def test_plan_run_stays_immutable_after_execution(tmp_path: Path) -> None:
    plan_run_dir = _create_plan_run(
        tmp_path,
        evidence=_INTERNAL_EVIDENCE,
        capability_id="internal_dsur",
    )
    before = {
        path.relative_to(plan_run_dir): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in plan_run_dir.rglob("*")
        if path.is_file()
    }
    run_comparison_finding_assessment_execution(
        project_root=BACKEND_ROOT,
        plan_run_dir=plan_run_dir,
        llm_mode="mock",
        provider=_RecordingProvider(),
        output_dir=tmp_path / "run",
        run_id="immutable",
        comparison_modes=["scope_local"],
        max_jobs=1,
    )
    after = {
        path.relative_to(plan_run_dir): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in plan_run_dir.rglob("*")
        if path.is_file()
    }
    assert before == after


def test_runner_cli_requires_plan_run_dir() -> None:
    with pytest.raises(SystemExit):
        comparison_finding_assessment_runner.parse_args(["--llm", "mock"])


def test_runner_cli_accepts_plan_run_dir(tmp_path: Path) -> None:
    plan_run_dir = _create_plan_run(
        tmp_path,
        evidence=_INTERNAL_EVIDENCE,
        capability_id="internal_dsur",
    )
    args = comparison_finding_assessment_runner.parse_args(
        [
            "--plan-run-dir",
            str(plan_run_dir),
            "--llm",
            "mock",
        ]
    )
    assert Path(args.plan_run_dir) == plan_run_dir


def test_runner_injects_standalone_mock_provider() -> None:
    with patch.object(
        comparison_finding_assessment_runner,
        "run_comparison_finding_assessment_execution",
        return_value=SimpleNamespace(messages=()),
    ) as execute:
        comparison_finding_assessment_runner.main(
            ["--plan-run-dir", "unused", "--llm", "mock"]
        )

    provider = execute.call_args.kwargs["provider"]
    assert isinstance(provider, ComparisonFindingAssessmentStandaloneMockProvider)


def test_runtime_mock_execution_requires_injected_provider(tmp_path: Path) -> None:
    plan_run_dir = _create_plan_run(
        tmp_path,
        evidence=_INTERNAL_EVIDENCE,
        capability_id="internal_dsur",
    )

    with pytest.raises(
        ValueError, match="mock execution requires an injected provider"
    ):
        run_comparison_finding_assessment_execution(
            project_root=BACKEND_ROOT,
            plan_run_dir=plan_run_dir,
            llm_mode="mock",
            output_dir=tmp_path / "run",
            run_id="missing_mock_provider",
            max_jobs=1,
        )


def test_runner_cli_accepts_positive_max_concurrency(tmp_path: Path) -> None:
    plan_run_dir = _create_plan_run(
        tmp_path,
        evidence=_INTERNAL_EVIDENCE,
        capability_id="internal_dsur",
    )
    args = comparison_finding_assessment_runner.parse_args(
        [
            "--plan-run-dir",
            str(plan_run_dir),
            "--llm",
            "mock",
            "--max-concurrency",
            "3",
        ]
    )
    assert args.max_concurrency == 3


@pytest.mark.parametrize("value", ["0", "-1"])
def test_runner_cli_rejects_non_positive_max_concurrency(value: str) -> None:
    with pytest.raises(SystemExit):
        comparison_finding_assessment_runner.parse_args(
            [
                "--plan-run-dir",
                "unused",
                "--llm",
                "mock",
                "--max-concurrency",
                value,
            ]
        )


@pytest.mark.parametrize("value", [0, -1, True, False, 1.5, "2"])
def test_runtime_rejects_invalid_max_concurrency(value: object) -> None:
    with pytest.raises(ValueError, match="max_concurrency must be a positive integer"):
        run_comparison_finding_assessment_execution(
            project_root=BACKEND_ROOT,
            plan_run_dir="unused",
            llm_mode="mock",
            max_concurrency=value,  # type: ignore[arg-type]
        )


def test_default_runs_all_selected_jobs_concurrently(tmp_path: Path) -> None:
    plan_run_dir = _create_plan_run(
        tmp_path,
        evidence=_INTERNAL_EVIDENCE,
        capability_id="internal_dsur",
    )
    provider = _BlockingConcurrencyProvider()
    with ThreadPoolExecutor(max_workers=1) as harness:
        future = harness.submit(
            run_comparison_finding_assessment_execution,
            project_root=BACKEND_ROOT,
            plan_run_dir=plan_run_dir,
            llm_mode="mock",
            provider=provider,
            output_dir=tmp_path / "run_default_concurrency",
            run_id="default_concurrency",
            comparison_modes=["scope_local"],
            max_jobs=6,
        )
        try:
            assert provider.wait_for_peak(6)
        finally:
            provider.release()
        report = future.result(timeout=15)

    assert provider.peak_active_call_count == 6
    summary = load_json(report.result.run_summary_path)
    assert summary["inputs"]["max_concurrency"] is None
    assert summary["stats"]["effective_concurrency"] == 6
    assert summary["stats"]["executed_job_count"] == 6
    assert summary["execution_wall_elapsed_ms"] >= 0


def test_explicit_max_concurrency_caps_real_provider_overlap(tmp_path: Path) -> None:
    plan_run_dir = _create_plan_run(
        tmp_path,
        evidence=_INTERNAL_EVIDENCE,
        capability_id="internal_dsur",
    )
    provider = _BlockingConcurrencyProvider()
    with ThreadPoolExecutor(max_workers=1) as harness:
        future = harness.submit(
            run_comparison_finding_assessment_execution,
            project_root=BACKEND_ROOT,
            plan_run_dir=plan_run_dir,
            llm_mode="mock",
            provider=provider,
            output_dir=tmp_path / "run_capped_concurrency",
            run_id="capped_concurrency",
            comparison_modes=["scope_local"],
            max_jobs=6,
            max_concurrency=2,
        )
        try:
            assert provider.wait_for_peak(2)
        finally:
            provider.release()
        report = future.result(timeout=15)

    assert provider.peak_active_call_count == 2
    summary = load_json(report.result.run_summary_path)
    assert summary["inputs"]["max_concurrency"] == 2
    assert summary["stats"]["effective_concurrency"] == 2


def test_max_concurrency_one_preserves_serial_job_semantics(tmp_path: Path) -> None:
    plan_run_dir = _create_plan_run(
        tmp_path,
        evidence=_INTERNAL_EVIDENCE,
        capability_id="internal_dsur",
    )
    provider = _BlockingConcurrencyProvider()
    with ThreadPoolExecutor(max_workers=1) as harness:
        future = harness.submit(
            run_comparison_finding_assessment_execution,
            project_root=BACKEND_ROOT,
            plan_run_dir=plan_run_dir,
            llm_mode="mock",
            provider=provider,
            output_dir=tmp_path / "run_serial_compatibility",
            run_id="serial_compatibility",
            comparison_modes=["scope_local"],
            max_jobs=3,
            max_concurrency=1,
        )
        try:
            assert provider.wait_for_peak(1)
        finally:
            provider.release()
        report = future.result(timeout=15)

    assert provider.peak_active_call_count == 1
    assert [result.frozen_job_index for result in report.result.job_results] == [
        1,
        2,
        3,
    ]
    assert [result.job_dir.name for result in report.result.job_results] == [
        "001_scope_local",
        "002_scope_local",
        "003_scope_local",
    ]
    assert all(
        result.prompt_id == "comparison_finding_assessment.scope_local"
        for result in report.result.job_results
    )
    assert all(
        result.validation_status == "success" for result in report.result.job_results
    )


def test_completion_order_does_not_change_result_or_summary_order(
    tmp_path: Path,
) -> None:
    plan_run_dir = _create_plan_run(
        tmp_path,
        evidence=_INTERNAL_EVIDENCE,
        capability_id="internal_dsur",
    )
    aliases = ("T0001", "T0016", "T0019")
    provider = _CompletionOrderProvider(aliases)
    with ThreadPoolExecutor(max_workers=1) as harness:
        future = harness.submit(
            run_comparison_finding_assessment_execution,
            project_root=BACKEND_ROOT,
            plan_run_dir=plan_run_dir,
            llm_mode="mock",
            provider=provider,
            output_dir=tmp_path / "run_completion_order",
            run_id="completion_order",
            comparison_modes=["scope_local"],
            max_jobs=3,
        )
        try:
            assert provider.wait_until_all_entered()
            assert provider.release_and_wait("T0019", 1)
            assert provider.release_and_wait("T0016", 2)
            assert provider.release_and_wait("T0001", 3)
        finally:
            provider.release_all()
        report = future.result(timeout=15)

    assert provider.completed_aliases == ["T0019", "T0016", "T0001"]
    assert [result.frozen_job_index for result in report.result.job_results] == [
        1,
        2,
        3,
    ]
    summary = load_json(report.result.run_summary_path)
    assert [job["frozen_job_index"] for job in summary["jobs"]] == [1, 2, 3]
    assert [result.job_dir.name for result in report.result.job_results] == [
        "001_scope_local",
        "002_scope_local",
        "003_scope_local",
    ]


def test_concurrent_batch_preserves_mixed_job_failure_semantics(tmp_path: Path) -> None:
    plan_run_dir = _create_plan_run(
        tmp_path,
        evidence=_INTERNAL_EVIDENCE,
        capability_id="internal_dsur",
    )
    report = run_comparison_finding_assessment_execution(
        project_root=BACKEND_ROOT,
        plan_run_dir=plan_run_dir,
        llm_mode="mock",
        provider=_MixedOutcomeProvider(),
        output_dir=tmp_path / "run_mixed_failures",
        run_id="mixed_failures",
        comparison_modes=["scope_local"],
        max_jobs=4,
    )

    assert [result.frozen_job_index for result in report.result.job_results] == [
        1,
        2,
        3,
        4,
    ]
    assert [result.status for result in report.result.job_results] == [
        "success",
        "failed",
        "failed",
        "success",
    ]
    first, second, third, fourth = report.result.job_results
    assert (first.job_dir / "validated_response.json").is_file()
    assert (first.job_dir / "accepted_candidates.json").is_file()
    assert (second.job_dir / "debug" / "failure.json").is_file()
    assert (third.job_dir / "parse_error.txt").is_file()
    assert (fourth.job_dir / "validated_response.json").is_file()
    assert (fourth.job_dir / "accepted_candidates.json").is_file()
    assert fourth.accepted_candidate_count == 0
    assert fourth.finding_count == 0
    summary = load_json(report.result.run_summary_path)
    assert summary["run_status"] == "partial_failure"
    assert summary["stats"]["success_count"] == 2
    assert summary["stats"]["failed_count"] == 2
    assert [job["frozen_job_index"] for job in summary["jobs"]] == [1, 2, 3, 4]


def test_single_frozen_job_caps_effective_concurrency_at_one(tmp_path: Path) -> None:
    plan_run_dir = _create_plan_run(
        tmp_path,
        evidence=_INTERNAL_EVIDENCE,
        capability_id="internal_dsur",
    )
    report = run_comparison_finding_assessment_execution(
        project_root=BACKEND_ROOT,
        plan_run_dir=plan_run_dir,
        llm_mode="mock",
        provider=_RecordingProvider(),
        output_dir=tmp_path / "run_single_capped",
        run_id="single_capped",
        frozen_job_index=6,
        max_concurrency=20,
    )
    summary = load_json(report.result.run_summary_path)
    assert summary["inputs"]["max_concurrency"] == 20
    assert summary["stats"]["effective_concurrency"] == 1


def test_zero_selected_jobs_still_fail_before_scheduling(tmp_path: Path) -> None:
    plan_run_dir = _create_plan_run(
        tmp_path,
        evidence=_INTERNAL_EVIDENCE,
        capability_id="internal_dsur",
    )
    with pytest.raises(ValueError, match="no assessment jobs matched"):
        run_comparison_finding_assessment_execution(
            project_root=BACKEND_ROOT,
            plan_run_dir=plan_run_dir,
            llm_mode="mock",
            provider=_RecordingProvider(),
            output_dir=tmp_path / "run_zero",
            comparison_modes=["ib_to_dsur"],
            max_concurrency=2,
        )


def test_frozen_job_index_selects_exact_job(tmp_path: Path) -> None:
    plan_run_dir = _create_plan_run(
        tmp_path,
        evidence=_INTERNAL_EVIDENCE,
        capability_id="internal_dsur",
    )
    report = run_comparison_finding_assessment_execution(
        project_root=BACKEND_ROOT,
        plan_run_dir=plan_run_dir,
        llm_mode="mock",
        provider=_RecordingProvider(),
        output_dir=tmp_path / "run_exact",
        run_id="exact_index",
        frozen_job_index=6,
    )
    assert len(report.result.job_results) == 1
    result = report.result.job_results[0]
    assert result.frozen_job_index == 6
    assert result.comparison_mode_id == "scope_local"
    assert result.job_dir.name == "006_scope_local"
    summary = load_json(report.result.run_summary_path)
    assert summary["inputs"]["frozen_job_index"] == 6
    assert summary["inputs"]["comparison_modes"] is None
    assert summary["inputs"]["max_jobs"] is None


def test_frozen_job_index_rejects_subset_selectors(tmp_path: Path) -> None:
    plan_run_dir = _create_plan_run(
        tmp_path,
        evidence=_INTERNAL_EVIDENCE,
        capability_id="internal_dsur",
    )
    with pytest.raises(ValueError, match="cannot be combined"):
        run_comparison_finding_assessment_execution(
            project_root=BACKEND_ROOT,
            plan_run_dir=plan_run_dir,
            llm_mode="mock",
            provider=_RecordingProvider(),
            output_dir=tmp_path / "run_conflict",
            frozen_job_index=6,
            comparison_modes=["scope_local"],
        )
    with pytest.raises(ValueError, match="cannot be combined"):
        run_comparison_finding_assessment_execution(
            project_root=BACKEND_ROOT,
            plan_run_dir=plan_run_dir,
            llm_mode="mock",
            provider=_RecordingProvider(),
            output_dir=tmp_path / "run_conflict2",
            frozen_job_index=6,
            max_jobs=1,
        )


def test_frozen_job_index_out_of_range(tmp_path: Path) -> None:
    plan_run_dir = _create_plan_run(
        tmp_path,
        evidence=_INTERNAL_EVIDENCE,
        capability_id="internal_dsur",
    )
    with pytest.raises(ValueError, match="frozen_job_index must be between"):
        run_comparison_finding_assessment_execution(
            project_root=BACKEND_ROOT,
            plan_run_dir=plan_run_dir,
            llm_mode="mock",
            provider=_RecordingProvider(),
            output_dir=tmp_path / "run_oob",
            frozen_job_index=999,
        )


def test_execution_records_prompt_version_in_job_metadata(tmp_path: Path) -> None:
    plan_run_dir = _create_plan_run(
        tmp_path,
        evidence=_INTERNAL_EVIDENCE,
        capability_id="internal_dsur",
    )
    report = run_comparison_finding_assessment_execution(
        project_root=BACKEND_ROOT,
        plan_run_dir=plan_run_dir,
        llm_mode="mock",
        provider=_RecordingProvider(),
        output_dir=tmp_path / "run_prompt_meta",
        run_id="prompt_meta",
        frozen_job_index=1,
    )
    result = report.result.job_results[0]
    assert result.comparison_mode_id == "scope_local"
    assert result.prompt_id == "comparison_finding_assessment.scope_local"
    assert result.prompt_version == "0.3.3"
    run_metadata = load_json(result.job_dir / "debug" / "run_metadata.json")
    assert run_metadata["comparison_mode_id"] == "scope_local"
    assert run_metadata["prompt_id"] == "comparison_finding_assessment.scope_local"
    assert run_metadata["prompt_version"] == "0.3.3"
    assert run_metadata["response_format_applied"] is False
    assert (result.job_dir / "debug" / "prompt.txt").is_file()
    summary = load_json(report.result.run_summary_path)
    job_summary = summary["jobs"][0]
    assert job_summary["response_format_applied"] is False


def test_api_execution_uses_formal_comparison_response_format_policy(
    tmp_path: Path,
) -> None:
    plan_run_dir = _create_plan_run(
        tmp_path,
        evidence=_INTERNAL_EVIDENCE,
        capability_id="internal_dsur",
    )
    captured: dict[str, object] = {}

    def fake_build_api_provider(**kwargs: object) -> _RecordingProvider:
        captured.update(kwargs)
        return _RecordingProvider()

    with patch(
        "runtime.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence.comparison_finding_assessment.build_api_provider",
        new=fake_build_api_provider,
    ):
        report = run_comparison_finding_assessment_execution(
            project_root=BACKEND_ROOT,
            plan_run_dir=plan_run_dir,
            llm_mode="api",
            llm_profile="qwen3_7_plus_2026_05_26",
            output_dir=tmp_path / "run_formal_response_format_policy",
            run_id="formal_response_format_policy",
            frozen_job_index=1,
        )

    assert captured["response_format"] is None
    runtime_request = load_json(
        report.result.job_results[0].job_dir / "debug" / "runtime_request.json"
    )
    assert runtime_request["response_format"] is None


def test_execution_run_summary_lists_only_executed_prompt_definitions(
    tmp_path: Path,
) -> None:
    plan_run_dir = _create_plan_run(
        tmp_path,
        evidence=_INTERNAL_EVIDENCE,
        capability_id="internal_dsur",
    )
    report = run_comparison_finding_assessment_execution(
        project_root=BACKEND_ROOT,
        plan_run_dir=plan_run_dir,
        llm_mode="mock",
        provider=_RecordingProvider(),
        output_dir=tmp_path / "run_prompt_summary",
        run_id="prompt_summary",
        frozen_job_index=11,
    )
    result = report.result.job_results[0]
    assert result.comparison_mode_id == "focus_comparison"
    assert result.prompt_id == "comparison_finding_assessment.focus_comparison"
    summary = load_json(report.result.run_summary_path)
    assert summary["prompt_definitions"] == {
        "comparison_finding_assessment.focus_comparison": {"version": "0.3.2"},
    }
    assert "comparison_finding_assessment.scope_local" not in summary["prompt_definitions"]
