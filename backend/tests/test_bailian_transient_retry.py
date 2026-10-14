"""Deterministic transport retry tests using the installed SDK exceptions."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import openai
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from llm.invocation import invoke_llm, llm_invocations_from_exception
from llm.providers.bailian import BailianQwenProvider
from llm.providers.config import ProviderConfig


def timeout():
    return openai.APITimeoutError(httpx.Request("POST", "https://example.test"))


def status(code, error_class=openai.APIStatusError):
    return error_class("status failure", response=httpx.Response(
        code, request=httpx.Request("POST", "https://example.test")
    ), body=None)


def provider(monkeypatch, outcomes):
    create = Mock(side_effect=outcomes)
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    build = Mock(return_value=client)
    monkeypatch.setattr("llm.providers.bailian.build_openai_client", build)
    instance = BailianQwenProvider(ProviderConfig(
        provider_name="bailian_qwen", api_key="test", base_url="https://example.test",
        model="qwen-test", model_alias="test",
    ))
    return instance, create, build


def completion(text="{}"):
    return SimpleNamespace(id="request-2", usage=SimpleNamespace(
        prompt_tokens=3, completion_tokens=2, total_tokens=5
    ), choices=[SimpleNamespace(message=SimpleNamespace(content=text), finish_reason="stop")])


def test_timeout_configuration(monkeypatch):
    _, _, build = provider(monkeypatch, [])
    assert build.call_args.kwargs["timeout"] == 300.0
    assert build.call_args.kwargs["max_retries"] == 0


@pytest.mark.parametrize("error", [timeout(), openai.APIConnectionError(
    request=httpx.Request("POST", "https://example.test")
), status(429, openai.RateLimitError), status(429), status(500), status(503)])
def test_transient_then_success(monkeypatch, error, caplog):
    instance, create, _ = provider(monkeypatch, [error, completion()])
    ticks = iter([0., 300., 300., 370.])
    monkeypatch.setattr("llm.invocation.perf_counter", lambda: next(ticks))
    outcome = invoke_llm(instance, [])
    assert outcome.unwrap().request_id == "request-2"
    assert create.call_count == 2
    assert [r.status for r in outcome.invocations] == ["failed", "success"]
    assert [r.attempt_index for r in outcome.invocations] == [1, 2]
    assert [r.elapsed_ms for r in outcome.invocations] == [300000, 70000]
    assert outcome.invocations[0].error_type == type(error).__name__
    assert outcome.invocations[0].provider == "bailian_qwen"
    assert outcome.invocations[0].model == "qwen-test"
    assert outcome.invocations[1].usage["total_tokens"] == 5
    assert "retrying" in caplog.text


def test_timeout_twice_preserves_original_exception_and_history(monkeypatch):
    final = timeout()
    instance, create, _ = provider(monkeypatch, [timeout(), final])
    ticks = iter([0., 300., 300., 600.])
    monkeypatch.setattr("llm.invocation.perf_counter", lambda: next(ticks))
    outcome = invoke_llm(instance, [])
    with pytest.raises(openai.APITimeoutError) as caught:
        outcome.unwrap()
    assert caught.value is final
    assert create.call_count == 2
    history = llm_invocations_from_exception(final)
    assert history == outcome.invocations
    assert [r.status for r in history] == ["failed", "failed"]
    assert [r.attempt_index for r in history] == [1, 2]
    assert [r.elapsed_ms for r in history] == [300000, 300000]


@pytest.mark.parametrize("error", [status(400), status(401), status(403), status(408),
                                         status(499), status(600), ValueError("config"), TimeoutError()])
def test_non_transient_does_not_retry(monkeypatch, error):
    instance, create, _ = provider(monkeypatch, [error, completion()])
    outcome = invoke_llm(instance, [])
    assert outcome.error is error
    assert create.call_count == 1
    assert len(outcome.invocations) == 1


@pytest.mark.parametrize("text", ["not json", '{"candidates": [{"label": "invalid"}]}'])
def test_ec_downstream_failure_is_successful_single_invocation(monkeypatch, text):
    from tests.test_comparison_finding_assessment_execution_core import _job, _evidence
    from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.comparison_finding_assessment import execute_comparison_finding_assessment_job

    instance, create, _ = provider(monkeypatch, [completion(text)])
    execution = execute_comparison_finding_assessment_job(
        frozen_job_index=1, execution_index=1,
        job=_job("scope_local", ("scope", ("H0001",))),
        aggregate_comparison_evidence=_evidence(), provider=instance,
    )
    assert execution.status == "failed"
    assert create.call_count == 1
    assert [r.status for r in execution.llm_invocations] == ["success"]


def test_ec_retry_success_persists_both_attempts(monkeypatch, tmp_path):
    from tests.test_comparison_finding_assessment_execution_core import _job, _evidence
    from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.comparison_finding_assessment import execute_comparison_finding_assessment_job
    from runtime.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence.comparison_finding_assessment_persistence import persist_comparison_finding_assessment_job_execution
    from runtime.io import load_json

    instance, create, _ = provider(monkeypatch, [timeout(), completion('{"candidates": []}')])
    execution = execute_comparison_finding_assessment_job(
        frozen_job_index=1, execution_index=1,
        job=_job("scope_local", ("scope", ("H0001",))),
        aggregate_comparison_evidence=_evidence(), provider=instance,
    )
    assert execution.status == "success"
    assert create.call_count == 2
    persist_comparison_finding_assessment_job_execution(
        execution=execution, job_dir=tmp_path, evidence_input="test",
        llm_profile=None, thinking=None, response_format=None, seed=1,
    )
    history = load_json(tmp_path / "debug" / "run_metadata.json")["llm_invocations"]
    assert [r["status"] for r in history] == ["failed", "success"]
    assert [r["attempt_index"] for r in history] == [1, 2]


def test_ec_exhausted_retry_is_job_local(monkeypatch):
    from tests.test_aggregate_evidence_comparison_scheduler_robustness import _scheduler_from_planned
    from tests.test_aggregate_evidence_comparison_pipelining import _PipelineMockProvider

    instance, create, _ = provider(monkeypatch, [timeout(), timeout()])
    successful = _PipelineMockProvider()
    calls = 0

    def generate(messages):
        nonlocal calls
        calls += 1
        if calls <= 2:
            return instance.generate(messages)
        return successful.generate(messages)

    wrapper = SimpleNamespace(generate=generate, is_transient_request_error=instance.is_transient_request_error)
    scheduler = _scheduler_from_planned(job_count=2, provider=wrapper, max_concurrency=1)
    scheduler.run()
    executions = sorted(scheduler.assessment_executions.values(), key=lambda e: e.frozen_job_index)
    assert [e.status for e in executions] == ["failed", "success"]
    assert [r.status for r in executions[0].llm_invocations] == ["failed", "failed"]
    assert create.call_count == 2
    assert scheduler._fatal_error is None


@pytest.mark.parametrize("business_failure", ["parse", "length", "schema", "none", "exhausted"])
def test_esp_business_conditions_and_order(monkeypatch, business_failure):
    import json
    from tests.test_scope_assessments import _assessment_input, _runtime_context, _llm_input, _raw_response_for_llm_input
    from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.scope_assess import run_scope_assessment_api

    assessment_input = _assessment_input()
    llm_input = _llm_input(assessment_input)
    valid = completion(json.dumps(_raw_response_for_llm_input(llm_input)))
    first = completion("not json") if business_failure in {"parse", "exhausted"} else completion("{}")
    if business_failure == "length":
        first.choices[0].finish_reason = "length"
    if business_failure == "none":
        first = valid
    outcomes = [timeout(), first]
    if business_failure in {"parse", "length"}:
        outcomes += [timeout(), valid]
    if business_failure == "exhausted":
        outcomes += [timeout(), timeout()]
    instance, create, _ = provider(monkeypatch, outcomes)

    def run():
        return run_scope_assessment_api(
            assessment_input=assessment_input, assessment_runtime_context=_runtime_context(),
            prompt_input_bundle=llm_input.prompt_input_bundle,
            alias_to_scope_id=llm_input.alias_to_scope_id,
            assessment_profile_name="clinical_safety_aggregate_heading_scope_assessment_zh",
            llm_profile="qwen3_7_plus_2026_05_26", provider=instance,
        )
    if business_failure == "exhausted":
        with pytest.raises(openai.APITimeoutError) as caught:
            run()
        history = llm_invocations_from_exception(caught.value)
        assert create.call_count == 4
        assert [r.attempt_index for r in history] == [1, 2, 3, 4]
        assert [r.status for r in history] == ["failed", "success", "failed", "failed"]
        return
    if business_failure == "schema":
        from llm.execution_errors import APIStructuredResponseError
        with pytest.raises(APIStructuredResponseError) as caught:
            run()
        history = llm_invocations_from_exception(caught.value)
    else:
        history = run()["llm_invocations"]
    expected = 4 if business_failure in {"parse", "length"} else 2
    assert create.call_count == expected
    assert [r.attempt_index for r in history] == list(range(1, expected + 1))
    assert [r.status for r in history] == ["failed", "success"] * (expected // 2)


def test_other_provider_does_not_gain_transport_retries():
    instance = SimpleNamespace(generate=Mock(side_effect=timeout()))
    outcome = invoke_llm(instance, [])
    assert isinstance(outcome.error, openai.APITimeoutError)
    assert instance.generate.call_count == 1


def test_ec_second_pass_role_starts_again_at_one(monkeypatch):
    from tests.test_aggregate_evidence_comparison_pipelining import _planned_subset, _FIXTURE_EVIDENCE, _valid_assessment_response, _PipelineMockProvider
    from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.execution import _PipelineWorkScheduler
    from runtime.io import load_json

    primary, primary_create, _ = provider(monkeypatch, [timeout(), completion('{"candidates": []}')])
    secondary, secondary_create, _ = provider(monkeypatch, [])
    secondary_create.side_effect = lambda **kwargs: completion(_valid_assessment_response(kwargs["messages"]).raw_text)
    scheduler = _PipelineWorkScheduler(
        selected_jobs=tuple(enumerate(_planned_subset(1), start=1)),
        aggregate_comparison_evidence=load_json(_FIXTURE_EVIDENCE),
        assessment_provider=primary, assessment_second_pass_provider=secondary,
        verification_provider=_PipelineMockProvider(), max_concurrency=1,
        assessment_llm_execution_config={"config_id": "clinical_trial_doc_ec_assessment"},
        assessment_second_pass_llm_execution_config={"config_id": "clinical_trial_doc_ec_assessment_second_pass"},
    )
    scheduler.run()
    first = scheduler.assessment_executions[1].llm_invocations
    second = scheduler.second_pass_assessment_executions[1].llm_invocations
    assert primary_create.call_count == 2
    assert secondary_create.call_count == 1
    assert [r.attempt_index for r in first] == [1, 2]
    assert [r.attempt_index for r in second] == [1]
    assert {r.config_id for r in first} == {"clinical_trial_doc_ec_assessment"}
    assert {r.config_id for r in second} == {"clinical_trial_doc_ec_assessment_second_pass"}
