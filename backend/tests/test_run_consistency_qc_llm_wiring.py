"""Tests for production LLM policy closure in run_consistency_qc.py."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from application.clinical_trial_doc_consistency_qc.capabilities import (
    INSTALLED_CLINICAL_TRIAL_DOC_CONSISTENCY_QC_CAPABILITIES,
)
from llm.execution_configs import (
    CLINICAL_TRIAL_DOC_FOP_OVERVIEW_LLM_EXECUTION_CONFIG_ID,
    resolve_llm_execution_config,
)
from operations.evidence_comparison.stage import EvidenceComparisonStageResult
from operations.evidence_source_preparation.stage import (
    EvidenceSourcePreparationStageResult,
)
from scripts import run_consistency_qc
from tests.document_consistency_qc_flow_helpers import (
    FlowOverviewFakeProvider,
)
from tests.test_run_consistency_qc_cli import (
    RUN_CONSISTENCY_QC_PATH,
    _flow_report,
)

SECOND_SAMPLE_DOCX = (
    BACKEND_ROOT
    / "tests"
    / "fixtures"
    / "clinical_trial_doc"
    / "tag_integration"
    / "ib_safety_tag_integration_001.docx"
)

_INSTALLED_OVERVIEW_CONFIG = resolve_llm_execution_config(
    CLINICAL_TRIAL_DOC_FOP_OVERVIEW_LLM_EXECUTION_CONFIG_ID
)

_REJECTED_LLM_CLI_FLAGS = (
    ["--llm", "api"],
    ["--llm-profile", "deepseek_v4_flash"],
    ["--thinking"],
    ["--no-thinking"],
)


def _help_text() -> str:
    result = subprocess.run(
        [sys.executable, str(RUN_CONSISTENCY_QC_PATH), "--help"],
        cwd=BACKEND_ROOT.parent,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


def test_help_excludes_llm_cli_arguments() -> None:
    help_text = _help_text()

    assert "--llm " not in help_text
    assert "--llm-profile" not in help_text
    assert "--thinking" not in help_text
    assert "--no-thinking" not in help_text
    assert "Filter Output Projection" in help_text
    assert "Route" in help_text


@pytest.mark.parametrize("extra_argv", _REJECTED_LLM_CLI_FLAGS)
def test_llm_cli_arguments_are_rejected(extra_argv: list[str]) -> None:
    capabilities = INSTALLED_CLINICAL_TRIAL_DOC_CONSISTENCY_QC_CAPABILITIES
    with pytest.raises(SystemExit):
        run_consistency_qc._parse_args(
            capabilities,
            ["--capability", "internal_dsur", *extra_argv],
        )


def test_installed_overview_binding_resolves_production_default() -> None:
    assert _INSTALLED_OVERVIEW_CONFIG.profile_id == "qwen3_7_plus_2026_05_26"
    assert _INSTALLED_OVERVIEW_CONFIG.thinking is None
    assert _INSTALLED_OVERVIEW_CONFIG.seed == 1234



def test_main_without_cli_override_delegates_runtime_materialization_to_application(
    tmp_path: Path,
) -> None:
    source = tmp_path / "sample.docx"
    source.write_bytes(b"doc")
    capability_config = INSTALLED_CLINICAL_TRIAL_DOC_CONSISTENCY_QC_CAPABILITIES[
        "internal_dsur"
    ]
    application_result = SimpleNamespace(
        flow_report=_flow_report(
            capability_config=capability_config,
            uploads={"source": source},
            tmp_path=tmp_path,
        )
    )

    with (
        patch.object(
            run_consistency_qc,
            "prepare_and_allocate_installed_clinical_trial_document_consistency_qc",
            return_value=object(),
        ) as prepare,
        patch.object(
            run_consistency_qc,
            "execute_prepared_installed_clinical_trial_document_consistency_qc",
            return_value=application_result,
        ),
        patch.object(run_consistency_qc, "_print_summary"),
    ):
        run_consistency_qc.main(
            [
                "--capability",
                "internal_dsur",
                "--source",
                str(source),
                "--project-root",
                str(tmp_path),
            ]
        )

    assert "projection_runtime_dependencies" not in prepare.call_args.kwargs


def test_overview_flow_integration_uses_installed_binding_materialization(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert SECOND_SAMPLE_DOCX.is_file()
    fake_provider = FlowOverviewFakeProvider()

    def _fake_esp_stage(*, stage_input, stage_executor):
        _ = stage_executor
        output_dir = stage_input.context.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        declared_output_path = output_dir / "declared_output.json"
        declared_output_path.write_text("{}", encoding="utf-8")
        run_summary_path = output_dir / "run_summary.json"
        run_summary_path.write_text("{}", encoding="utf-8")
        return EvidenceSourcePreparationStageResult(
            output_dir=output_dir,
            run_id="esp_mock",
            doc_id=stage_input.route_stage.doc_id,
            semantic_module_id=stage_input.route_stage.semantic_module_id,
            stage_executor_id="mock.executor",
            declared_output_path=declared_output_path,
            run_summary_path=run_summary_path,
        )

    monkeypatch.setattr(
        "application.clinical_trial_doc_consistency_qc.execution.materialize_llm_provider",
        lambda _config: fake_provider,
    )
    monkeypatch.setattr(
        "application.clinical_trial_doc_consistency_qc.projection_runtime."
        "materialize_llm_provider",
        lambda _config: fake_provider,
    )
    def _fake_comparison_stage(*, stage_input, stage_executor):
        _ = stage_executor
        output_dir = stage_input.context.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        run_summary_path = output_dir / "run_summary.json"
        run_summary_path.write_text("{}", encoding="utf-8")
        return EvidenceComparisonStageResult(
            output_dir=output_dir,
            run_id=stage_input.context.run_id or "comparison_mock",
            stage_executor_id="mock.comparison",
            run_status="success",
            run_summary_path=run_summary_path,
            declared_output_path=None,
        )

    monkeypatch.setattr(
        "execution_flow.document_consistency_qc.flow.run_evidence_source_preparation_stage",
        _fake_esp_stage,
    )
    monkeypatch.setattr(
        "execution_flow.document_consistency_qc.flow.run_evidence_comparison_stage",
        _fake_comparison_stage,
    )

    run_consistency_qc.main(
        [
            "--capability",
            "internal_ib",
            "--source",
            str(SECOND_SAMPLE_DOCX),
            "--project-root",
            str(tmp_path),
        ]
    )

    flow_summary = next(
        tmp_path.glob("runs/document_consistency_qc/*/flow_run_summary.json")
    )
    assert flow_summary.is_file()
