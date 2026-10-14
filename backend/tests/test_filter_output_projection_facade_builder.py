"""Tests for Filter-output projection facade construction installation."""

from __future__ import annotations

import ast
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from application.clinical_trial_doc_consistency_qc import (
    INSTALLED_CLINICAL_TRIAL_DOC_FILTER_OUTPUT_PROJECTION_FACADE_BUILDER,
)
from application.clinical_trial_doc_consistency_qc import (
    build_clinical_trial_doc_consistency_qc_application_composition,
)
from llm.providers.base import LLMRawResult
from operations.filter_output_projection.contracts import (
    ResolvedFilterOutputProjectionJob,
)
from operations.filter_output_projection.runtime_dependencies import (
    FilterOutputProjectionRuntimeDependencies,
)
from plugins.clinical_trial_doc.filter_output_projection import (
    DIRECT_FILTER_OUTPUT_PROJECTION_STRATEGY_ID,
    OVERVIEW_SEMANTIC_DECOMPOSITION_FILTER_OUTPUT_PROJECTION_STRATEGY_ID,
    DirectFilterOutputProjectionFacade,
    OverviewSemanticDecompositionProjectionFacade,
)
from plugins.clinical_trial_doc.filter_profiles.ib.clinical_safety_zh import (
    IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH,
)
from plugins.clinical_trial_doc.filter_profiles.ib.overview_zh import (
    IB_OVERVIEW_FILTER_PROFILE_ZH,
)

RUNTIME_PROJECTION_STAGE_PATH = (
    BACKEND_ROOT / "runtime" / "filter_output_projection_stage.py"
)


@dataclass(frozen=True)
class _FakeProvider:
  def generate(self, messages: list[dict[str, str]]) -> LLMRawResult:
      _ = messages
      return LLMRawResult(
          provider_name="fake",
          model="fake",
          raw_text='{"assessments":[]}',
      )


def test_direct_job_builds_without_llm_provider() -> None:
    composition = build_clinical_trial_doc_consistency_qc_application_composition()
    job = composition.resolve_filter_output_projection_job(
        IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH.filter_job_id
    )
    facade = composition.filter_output_projection_facade_builder(
        job=job,
        runtime_dependencies=FilterOutputProjectionRuntimeDependencies(),
    )
    assert isinstance(facade, DirectFilterOutputProjectionFacade)


def test_overview_job_builds_with_fake_provider() -> None:
    composition = build_clinical_trial_doc_consistency_qc_application_composition()
    job = composition.resolve_filter_output_projection_job(
        IB_OVERVIEW_FILTER_PROFILE_ZH.filter_job_id
    )
    facade = composition.filter_output_projection_facade_builder(
        job=job,
        runtime_dependencies=FilterOutputProjectionRuntimeDependencies(
            llm_provider=_FakeProvider(),
        ),
    )
    assert isinstance(facade, OverviewSemanticDecompositionProjectionFacade)


def test_overview_job_without_provider_fails_explicitly() -> None:
    job = ResolvedFilterOutputProjectionJob(
        filter_job_id=IB_OVERVIEW_FILTER_PROFILE_ZH.filter_job_id,
        strategy_id=OVERVIEW_SEMANTIC_DECOMPOSITION_FILTER_OUTPUT_PROJECTION_STRATEGY_ID,
    )
    with pytest.raises(ValueError, match="llm_provider is required"):
        INSTALLED_CLINICAL_TRIAL_DOC_FILTER_OUTPUT_PROJECTION_FACADE_BUILDER(
            job=job,
            runtime_dependencies=FilterOutputProjectionRuntimeDependencies(),
        )


def test_runtime_projection_stage_has_no_strategy_branching() -> None:
    source = RUNTIME_PROJECTION_STAGE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(RUNTIME_PROJECTION_STAGE_PATH))
    joined = source
    for token in (
        DIRECT_FILTER_OUTPUT_PROJECTION_STRATEGY_ID,
        OVERVIEW_SEMANTIC_DECOMPOSITION_FILTER_OUTPUT_PROJECTION_STRATEGY_ID,
        "overview_semantic_decomposition",
        "if job.strategy_id",
        "if \"overview\" in",
    ):
        assert token not in joined, f"runtime must not branch on {token!r}"
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    forbidden_prefixes = (
        "plugins.clinical_trial_doc.filter_output_projection.direct",
        "plugins.clinical_trial_doc.filter_output_projection.overview",
    )
    assert not any(
        module.startswith(forbidden_prefixes)
        for module in imported
    )
