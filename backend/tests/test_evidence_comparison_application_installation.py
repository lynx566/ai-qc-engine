"""Application installation tests for clinical-trial Evidence Comparison."""

from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from application.clinical_trial_doc_consistency_qc import (
    build_clinical_trial_doc_consistency_qc_application_composition,
)
from application.clinical_trial_doc_consistency_qc.capability_bindings import (
    INSTALLED_CLINICAL_TRIAL_DOC_COMPARISON_FINDING_ASSESSMENT_DECLARATIONS,
    INSTALLED_CLINICAL_TRIAL_DOC_COMPARISON_FINDING_CONSOLIDATION_DECLARATIONS,
)
from application.clinical_trial_doc_consistency_qc.comparison_finding_assessment_installation import (
    resolve_installed_comparison_finding_assessment_config,
)
from application.clinical_trial_doc_consistency_qc.comparison_finding_consolidation_installation import (
    resolve_installed_comparison_finding_consolidation_config,
)
from application.clinical_trial_doc_consistency_qc.evidence_comparison_consumer_installation import (
    INSTALLED_CLINICAL_TRIAL_DOC_EVIDENCE_COMPARISON_CONSUMER_BINDINGS,
    build_evidence_comparison_participant_requirements,
)
from application.clinical_trial_doc_consistency_qc.evidence_comparison_installation import (
    INSTALLED_CLINICAL_TRIAL_DOC_EVIDENCE_COMPARISON_EXECUTOR,
    INSTALLED_CLINICAL_TRIAL_DOC_EVIDENCE_COMPARISON_MAX_CONCURRENCY,
    INSTALLED_CLINICAL_TRIAL_DOC_EVIDENCE_COMPARISON_STAGE_EXECUTOR,
)
from application.clinical_trial_doc_consistency_qc.execution import (
    materialize_installed_evidence_comparison_execution_dependencies,
)
from application.clinical_trial_doc_consistency_qc.filter_output_projection_installation import (
    CLINICAL_SAFETY_SEMANTIC_MODULE_ID,
)
from application.clinical_trial_doc_consistency_qc.llm_binding_installation import (
    CLINICAL_SAFETY_AGGREGATE_EVIDENCE_COMPARISON_ASSESSMENT_LLM_SLOT,
    CLINICAL_SAFETY_AGGREGATE_EVIDENCE_COMPARISON_ASSESSMENT_SECOND_PASS_LLM_SLOT,
    CLINICAL_SAFETY_AGGREGATE_EVIDENCE_COMPARISON_CONSOLIDATION_LLM_SLOT,
    CLINICAL_SAFETY_AGGREGATE_EVIDENCE_COMPARISON_VERIFICATION_LLM_SLOT,
    INSTALLED_CLINICAL_TRIAL_DOC_LLM_DEPENDENCY_BINDINGS,
)
from artifacts.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence import (
    FINAL_FINDINGS_FILENAME,
    validate_final_findings,
)
from llm.execution_configs import (
    CLINICAL_TRIAL_DOC_EC_ASSESSMENT_LLM_EXECUTION_CONFIG_ID,
    CLINICAL_TRIAL_DOC_EC_ASSESSMENT_SECOND_PASS_LLM_EXECUTION_CONFIG_ID,
    CLINICAL_TRIAL_DOC_EC_CONSOLIDATION_LLM_EXECUTION_CONFIG_ID,
    CLINICAL_TRIAL_DOC_EC_VERIFICATION_LLM_EXECUTION_CONFIG_ID,
    resolve_llm_execution_config,
)
from llm.providers.base import LLMRawResult
from operations.evidence_comparison.handoff import resolve_evidence_comparison_handoff
from operations.evidence_comparison.participants import (
    EvidenceComparisonParticipantReference,
    ProducedEvidenceSourcePreparationOutputReference,
)
from operations.evidence_comparison.stage import (
    EvidenceComparisonStageContext,
    EvidenceComparisonStageInput,
)
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence import (
    CLINICAL_TRIAL_AGGREGATE_EVIDENCE_COMPARISON_EXECUTOR,
)
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.dependencies import (
    CLINICAL_SAFETY_AGGREGATE_EVIDENCE_COMPARISON_ASSESSMENT_LLM_SLOT as PLUGIN_ASSESSMENT_LLM_SLOT,
)
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.dependencies import (
    CLINICAL_SAFETY_AGGREGATE_EVIDENCE_COMPARISON_CONSOLIDATION_LLM_SLOT as PLUGIN_CONSOLIDATION_LLM_SLOT,
)
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.dependencies import (
    CLINICAL_SAFETY_AGGREGATE_EVIDENCE_COMPARISON_VERIFICATION_LLM_SLOT as PLUGIN_VERIFICATION_LLM_SLOT,
)
from runtime.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence.stage import (
    CLINICAL_TRIAL_AGGREGATE_EVIDENCE_COMPARISON_STAGE_EXECUTOR_ID,
    ClinicalTrialAggregateEvidenceComparisonExecutionDependencies,
)
from runtime.io import load_json
from tests.current_evidence_comparison_test_helpers import (
    write_current_ec_source_fixture,
)

_PLUGIN_ROOT = (
    BACKEND_ROOT
    / "plugins"
    / "clinical_trial_doc"
    / "evidence_comparison"
    / "clinical_safety"
    / "aggregate_evidence"
)


@pytest.mark.parametrize(
    ("capability_id", "enabled_modes"),
    [
        ("internal_dsur", ("focus_comparison",)),
        ("internal_ib", ("focus_comparison",)),
        ("internal_csr", ("focus_comparison",)),
        ("dsur_updated_ib", ()),
    ],
)
def test_installed_consolidation_activation_is_capability_owned(
    capability_id: str,
    enabled_modes: tuple[str, ...],
) -> None:
    config = resolve_installed_comparison_finding_consolidation_config(
        capability_id
    )

    assert config.enabled_comparison_modes == enabled_modes
    assert (
        INSTALLED_CLINICAL_TRIAL_DOC_COMPARISON_FINDING_CONSOLIDATION_DECLARATIONS[
            capability_id
        ].enabled_comparison_modes
        == enabled_modes
    )


def _participant(*, role_id: str, slot_id: str, path: Path):
    return EvidenceComparisonParticipantReference(
        role_id=role_id,
        slot_id=slot_id,
        semantic_module_id=CLINICAL_SAFETY_SEMANTIC_MODULE_ID,
        declared_output_path=path,
    )


def _first_alias(messages: list[dict[str, str]]) -> str:
    match = re.search(r"\[(T\d{4})\]", messages[-1]["content"])
    if match is None:
        raise AssertionError("expected sentence alias in prompt")
    return match.group(1)


def _extract_verification_finding_ids(user_content: str) -> list[str]:
    marker = "## Findings\n"
    marker_index = user_content.find(marker)
    if marker_index == -1:
        return []
    findings_section = user_content[marker_index + len(marker) :]
    finding_ids: list[str] = []
    for line in findings_section.splitlines():
        stripped = line.strip()
        if stripped.startswith("L") and len(stripped) == 4 and stripped[1:].isdigit():
            finding_ids.append(stripped)
    return finding_ids


class _RecordingProvider:
    def __init__(self, *, label: str = "application-stage-mock") -> None:
        self.label = label
        self.calls: list[list[dict[str, str]]] = []

    def generate(self, messages: list[dict[str, str]]) -> LLMRawResult:
        self.calls.append(messages)
        user_content = messages[-1]["content"]
        if "## Conclusions" in user_content:
            return LLMRawResult(
                provider_name=self.label,
                model=self.label,
                raw_text=json.dumps({"consolidated_groups": []}),
            )
        if "## Findings" in user_content:
            finding_ids = _extract_verification_finding_ids(user_content)
            return LLMRawResult(
                provider_name=self.label,
                model=self.label,
                raw_text=json.dumps(
                    {
                        "finding_verifications": [
                            {
                                "finding_id": finding_id,
                                "verification_result": "confirmed",
                            }
                            for finding_id in finding_ids
                        ],
                        "additional_findings": [],
                    }
                ),
            )
        alias = _first_alias(messages)
        return LLMRawResult(
            provider_name=self.label,
            model=self.label,
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


def test_installed_executor_and_stage_executor_are_bound() -> None:
    assert INSTALLED_CLINICAL_TRIAL_DOC_EVIDENCE_COMPARISON_EXECUTOR is (
        CLINICAL_TRIAL_AGGREGATE_EVIDENCE_COMPARISON_EXECUTOR
    )
    assert callable(INSTALLED_CLINICAL_TRIAL_DOC_EVIDENCE_COMPARISON_STAGE_EXECUTOR)


def test_composition_installs_consumer_bindings_for_all_declared_capabilities() -> None:
    composition = build_clinical_trial_doc_consistency_qc_application_composition()

    assert set(composition.evidence_comparison_consumer_bindings.bindings) == set(
        INSTALLED_CLINICAL_TRIAL_DOC_COMPARISON_FINDING_ASSESSMENT_DECLARATIONS
    )


def test_unbound_capability_returns_none() -> None:
    binding = INSTALLED_CLINICAL_TRIAL_DOC_EVIDENCE_COMPARISON_CONSUMER_BINDINGS.resolve_consumer_binding(
        "unknown_capability"
    )
    assert binding is None


def test_dsur_updated_ib_participant_requirements_match_declaration() -> None:
    binding = INSTALLED_CLINICAL_TRIAL_DOC_EVIDENCE_COMPARISON_CONSUMER_BINDINGS.resolve_consumer_binding(
        "dsur_updated_ib"
    )
    assert binding is not None
    declaration = (
        INSTALLED_CLINICAL_TRIAL_DOC_COMPARISON_FINDING_ASSESSMENT_DECLARATIONS[
            "dsur_updated_ib"
        ]
    )
    assert (
        tuple(requirement.role_id for requirement in binding.participant_requirements)
        == declaration.participant_role_ids
    )
    assert tuple(
        requirement.slot_id for requirement in binding.participant_requirements
    ) == ("source_a", "source_b")
    assert all(
        requirement.semantic_module_id == CLINICAL_SAFETY_SEMANTIC_MODULE_ID
        for requirement in binding.participant_requirements
    )


def test_participant_requirements_builder_matches_declaration() -> None:
    declaration = (
        INSTALLED_CLINICAL_TRIAL_DOC_COMPARISON_FINDING_ASSESSMENT_DECLARATIONS[
            "internal_dsur"
        ]
    )
    requirements = build_evidence_comparison_participant_requirements(
        declaration=declaration,
    )
    assert len(requirements) == 1
    assert requirements[0].role_id == "source"
    assert requirements[0].slot_id == "source"
    assert requirements[0].semantic_module_id == CLINICAL_SAFETY_SEMANTIC_MODULE_ID


def test_materialize_execution_dependencies_resolves_assessment_config() -> None:
    composition = build_clinical_trial_doc_consistency_qc_application_composition()
    assessment_provider = _RecordingProvider(label="assessment")
    assessment_second_pass_provider = _RecordingProvider(label="assessment-second-pass")
    verification_provider = _RecordingProvider(label="verification")
    consolidation_provider = _RecordingProvider(label="consolidation")
    dependencies = materialize_installed_evidence_comparison_execution_dependencies(
        composition=composition,
        capability_id="internal_dsur",
        assessment_provider=assessment_provider,
        assessment_second_pass_provider=assessment_second_pass_provider,
        verification_provider=verification_provider,
        consolidation_provider=consolidation_provider,
    )

    assert isinstance(
        dependencies,
        ClinicalTrialAggregateEvidenceComparisonExecutionDependencies,
    )
    assert dependencies.capability_id == "internal_dsur"
    assert dependencies.assessment_provider is assessment_provider
    assert (
        dependencies.assessment_second_pass_provider
        is assessment_second_pass_provider
    )
    assert dependencies.verification_provider is verification_provider
    assert dependencies.consolidation_provider is consolidation_provider
    assert (
        dependencies.assessment_config
        == resolve_installed_comparison_finding_assessment_config("internal_dsur")
    )
    assert dependencies.consolidation_config == (
        resolve_installed_comparison_finding_consolidation_config("internal_dsur")
    )
    assert dependencies.max_concurrency == (
        INSTALLED_CLINICAL_TRIAL_DOC_EVIDENCE_COMPARISON_MAX_CONCURRENCY
    )
    assert dependencies.assessment_llm_execution_config is None
    assert dependencies.assessment_second_pass_llm_execution_config is None
    assert dependencies.verification_llm_execution_config is None
    assert dependencies.consolidation_llm_execution_config is None


def test_materialize_execution_dependencies_requires_all_injected_providers() -> None:
    composition = build_clinical_trial_doc_consistency_qc_application_composition()

    with pytest.raises(ValueError, match="must be injected together"):
        materialize_installed_evidence_comparison_execution_dependencies(
            composition=composition,
            capability_id="internal_dsur",
            assessment_provider=_RecordingProvider(label="assessment"),
            verification_provider=_RecordingProvider(label="verification"),
        )


@pytest.mark.allow_external_provider_factory
def test_materialize_execution_dependencies_uses_installed_llm_bindings() -> None:
    composition = build_clinical_trial_doc_consistency_qc_application_composition()
    dependencies = materialize_installed_evidence_comparison_execution_dependencies(
        composition=composition,
        capability_id="internal_dsur",
    )

    assert (
        dependencies.assessment_llm_execution_config
        == resolve_llm_execution_config(
            CLINICAL_TRIAL_DOC_EC_ASSESSMENT_LLM_EXECUTION_CONFIG_ID
        ).to_provenance_record()
    )
    assert (
        dependencies.verification_llm_execution_config
        == resolve_llm_execution_config(
            CLINICAL_TRIAL_DOC_EC_VERIFICATION_LLM_EXECUTION_CONFIG_ID
        ).to_provenance_record()
    )
    assert (
        dependencies.consolidation_llm_execution_config
        == resolve_llm_execution_config(
            CLINICAL_TRIAL_DOC_EC_CONSOLIDATION_LLM_EXECUTION_CONFIG_ID
        ).to_provenance_record()
    )
    assert dependencies.assessment_provider is not None
    assert dependencies.verification_provider is not None
    assert dependencies.consolidation_provider is not None
    assert dependencies.assessment_provider is not dependencies.verification_provider
    assert dependencies.max_concurrency is None


@pytest.mark.allow_external_provider_factory
def test_materialize_execution_dependencies_has_no_installed_concurrency_cap() -> None:
    composition = build_clinical_trial_doc_consistency_qc_application_composition()
    dependencies = materialize_installed_evidence_comparison_execution_dependencies(
        composition=composition,
        capability_id="internal_dsur",
    )

    assert INSTALLED_CLINICAL_TRIAL_DOC_EVIDENCE_COMPARISON_MAX_CONCURRENCY is None
    assert dependencies.max_concurrency is None


@pytest.mark.allow_external_provider_factory
def test_aggregate_execution_input_preserves_explicit_concurrency_override() -> None:
    from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence import (
        AggregateEvidenceComparisonExecutionInput,
    )
    from runtime.io import load_json
    from tests.test_aggregate_evidence_comparison_execution import (
        _invocation_from_evidence,
    )

    composition = build_clinical_trial_doc_consistency_qc_application_composition()
    installed = materialize_installed_evidence_comparison_execution_dependencies(
        composition=composition,
        capability_id="internal_dsur",
    )
    evidence_payload = load_json(
        BACKEND_ROOT
        / "tests"
        / "fixtures"
        / "evidence_comparison"
        / "clinical_safety"
        / "aggregate_evidence"
        / "internal_dsur"
        / "aggregate_comparison_evidence.json"
    )
    execution_input = AggregateEvidenceComparisonExecutionInput(
        invocation=_invocation_from_evidence(evidence_payload),
        assessment_config=installed.assessment_config,
        assessment_provider=installed.assessment_provider,
        assessment_second_pass_provider=installed.assessment_second_pass_provider,
        verification_provider=installed.verification_provider,
        consolidation_config=installed.consolidation_config,
        consolidation_provider=installed.consolidation_provider,
        max_concurrency=2,
    )

    assert installed.max_concurrency is None
    assert execution_input.max_concurrency == 2


@pytest.mark.allow_external_provider_factory
def test_materialize_execution_dependencies_reflects_distinct_execution_policies() -> (
    None
):
    composition = build_clinical_trial_doc_consistency_qc_application_composition()
    dependencies = materialize_installed_evidence_comparison_execution_dependencies(
        composition=composition,
        capability_id="internal_dsur",
    )

    assessment_config = resolve_llm_execution_config(
        dependencies.assessment_llm_execution_config["config_id"]
    )
    assessment_second_pass_config = resolve_llm_execution_config(
        dependencies.assessment_second_pass_llm_execution_config["config_id"]
    )
    verification_config = resolve_llm_execution_config(
        dependencies.verification_llm_execution_config["config_id"]
    )
    consolidation_config = resolve_llm_execution_config(
        dependencies.consolidation_llm_execution_config["config_id"]
    )
    assert assessment_config.thinking is None
    assert assessment_config.seed == 1234
    assert assessment_second_pass_config.thinking is True
    assert assessment_second_pass_config.seed == 1234
    assert verification_config.thinking is None
    assert verification_config.seed == 1234
    assert consolidation_config.thinking is None
    assert consolidation_config.seed == 1234
    assert len(
        {
            assessment_config.config_id,
            assessment_second_pass_config.config_id,
            verification_config.config_id,
            consolidation_config.config_id,
        }
    ) == 4


def test_installed_llm_slots_are_bound_in_application_registry() -> None:
    assert (
        INSTALLED_CLINICAL_TRIAL_DOC_LLM_DEPENDENCY_BINDINGS[
            CLINICAL_SAFETY_AGGREGATE_EVIDENCE_COMPARISON_ASSESSMENT_SECOND_PASS_LLM_SLOT
        ]
        == CLINICAL_TRIAL_DOC_EC_ASSESSMENT_SECOND_PASS_LLM_EXECUTION_CONFIG_ID
    )
    assert (
        INSTALLED_CLINICAL_TRIAL_DOC_LLM_DEPENDENCY_BINDINGS[
            CLINICAL_SAFETY_AGGREGATE_EVIDENCE_COMPARISON_ASSESSMENT_LLM_SLOT
        ]
        == CLINICAL_TRIAL_DOC_EC_ASSESSMENT_LLM_EXECUTION_CONFIG_ID
    )
    assert (
        INSTALLED_CLINICAL_TRIAL_DOC_LLM_DEPENDENCY_BINDINGS[
            CLINICAL_SAFETY_AGGREGATE_EVIDENCE_COMPARISON_VERIFICATION_LLM_SLOT
        ]
        == CLINICAL_TRIAL_DOC_EC_VERIFICATION_LLM_EXECUTION_CONFIG_ID
    )
    assert (
        INSTALLED_CLINICAL_TRIAL_DOC_LLM_DEPENDENCY_BINDINGS[
            CLINICAL_SAFETY_AGGREGATE_EVIDENCE_COMPARISON_CONSOLIDATION_LLM_SLOT
        ]
        == CLINICAL_TRIAL_DOC_EC_CONSOLIDATION_LLM_EXECUTION_CONFIG_ID
    )
    assert (
        PLUGIN_ASSESSMENT_LLM_SLOT
        == CLINICAL_SAFETY_AGGREGATE_EVIDENCE_COMPARISON_ASSESSMENT_LLM_SLOT
    )
    assert (
        PLUGIN_VERIFICATION_LLM_SLOT
        == CLINICAL_SAFETY_AGGREGATE_EVIDENCE_COMPARISON_VERIFICATION_LLM_SLOT
    )
    assert (
        PLUGIN_CONSOLIDATION_LLM_SLOT
        == CLINICAL_SAFETY_AGGREGATE_EVIDENCE_COMPARISON_CONSOLIDATION_LLM_SLOT
    )


def test_materialize_rejects_unbound_capability() -> None:
    composition = build_clinical_trial_doc_consistency_qc_application_composition()
    with pytest.raises(
        ValueError, match="no installed Evidence Comparison consumer binding"
    ):
        materialize_installed_evidence_comparison_execution_dependencies(
            composition=composition,
            capability_id="unknown_capability",
            assessment_provider=_RecordingProvider(),
            verification_provider=_RecordingProvider(),
        )


def test_application_installed_stage_execution_success(
    tmp_path: Path,
) -> None:
    source_bundle = write_current_ec_source_fixture(
        tmp_path,
        label="application_internal_dsur",
        document_type="dsur",
        heading_paths=(("Safety findings",), ("Additional safety findings",)),
    )
    composition = build_clinical_trial_doc_consistency_qc_application_composition()
    assessment_provider = _RecordingProvider(label="assessment")
    verification_provider = _RecordingProvider(label="verification")
    consolidation_provider = _RecordingProvider(label="consolidation")
    binding = (
        composition.evidence_comparison_consumer_bindings.resolve_consumer_binding(
            "internal_dsur"
        )
    )
    assert binding is not None
    dependencies = materialize_installed_evidence_comparison_execution_dependencies(
        composition=composition,
        capability_id="internal_dsur",
        assessment_provider=assessment_provider,
        assessment_second_pass_provider=assessment_provider,
        verification_provider=verification_provider,
        consolidation_provider=consolidation_provider,
    )
    stage_input = EvidenceComparisonStageInput(
        participants=(
            _participant(
                role_id="source",
                slot_id="source",
                path=source_bundle,
            ),
        ),
        context=EvidenceComparisonStageContext(
            output_dir=tmp_path / "evidence_comparison" / "application_run",
            run_id="20260908_application_test",
        ),
        execution_dependencies=dependencies,
    )

    result = binding.stage_executor(stage_input=stage_input)

    assert result.stage_executor_id == (
        CLINICAL_TRIAL_AGGREGATE_EVIDENCE_COMPARISON_STAGE_EXECUTOR_ID
    )
    assert result.run_status == "success"
    assert result.declared_output_path == result.output_dir / FINAL_FINDINGS_FILENAME
    validate_final_findings(load_json(result.declared_output_path))
    assert len(assessment_provider.calls) >= 1
    assert len(verification_provider.calls) >= 1
    assert any(
        "## Findings" not in call[-1]["content"] for call in assessment_provider.calls
    )
    assert any(
        "## Findings" in call[-1]["content"] for call in verification_provider.calls
    )


def test_handoff_resolution_uses_installed_binding_participant_order(
    tmp_path: Path,
) -> None:
    composition = build_clinical_trial_doc_consistency_qc_application_composition()
    binding = (
        composition.evidence_comparison_consumer_bindings.resolve_consumer_binding(
            "dsur_updated_ib"
        )
    )
    assert binding is not None

    handoff_resolution = resolve_evidence_comparison_handoff(
        consumer_binding=binding,
        produced_outputs=(
            ProducedEvidenceSourcePreparationOutputReference(
                slot_id="source_a",
                semantic_module_id=CLINICAL_SAFETY_SEMANTIC_MODULE_ID,
                declared_output_path=tmp_path / "source_a.json",
            ),
            ProducedEvidenceSourcePreparationOutputReference(
                slot_id="source_b",
                semantic_module_id=CLINICAL_SAFETY_SEMANTIC_MODULE_ID,
                declared_output_path=tmp_path / "source_b.json",
            ),
        ),
    )

    assert handoff_resolution.handoff is not None
    assert tuple(
        participant.role_id for participant in handoff_resolution.handoff.participants
    ) == ("source_a", "source_b")


def test_plugin_execution_files_have_no_application_imports() -> None:
    forbidden_prefixes = ("application",)
    plugin_files = (
        _PLUGIN_ROOT / "execution.py",
        _PLUGIN_ROOT / "execution_types.py",
        _PLUGIN_ROOT / "executor.py",
        _PLUGIN_ROOT / "dependencies.py",
        _PLUGIN_ROOT / "comparison_finding_assessment" / "execution.py",
        _PLUGIN_ROOT / "comparison_finding_verification" / "execution.py",
    )
    violations: list[str] = []
    for path in plugin_files:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                modules = [node.module or ""]
            else:
                continue
            for imported in modules:
                if any(
                    imported == prefix or imported.startswith(prefix + ".")
                    for prefix in forbidden_prefixes
                ):
                    violations.append(f"{path.name} imports {imported}")
    assert not violations, "\n".join(violations)
