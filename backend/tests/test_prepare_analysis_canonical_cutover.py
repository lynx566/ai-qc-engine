"""Focused S3 guards for the atomic Prepare Analysis Runtime/Step cutover."""

from __future__ import annotations

import ast
import inspect
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from core.registry.alias import AliasEntityRecord
from operations.prepare_analysis import (
    PrepareAnalysisConfig,
    PrepareAnalysisConfigId,
    PrepareAnalysisDomainConfiguration,
    PrepareAnalysisRequestOptions,
)
from operations.prepare_analysis.registry import PrepareAnalysisConfigRegistry
from core.document.sentence_index import build_sentences
from steps.prepare_analysis import prepare_analysis_bundle
from plugins.clinical_trial_doc.prepare_analysis import (
    CLINICAL_REGEX_RULE_SET_ZH,
    CLINICAL_UIE_CONFIG_ZH,
    CURRENT_CLINICAL_PREPARE_ANALYSIS_CONFIG,
    CURRENT_CLINICAL_PREPARE_ANALYSIS_CONFIG_ID,
    ClinicalPreparePrivacyConfig,
    build_clinical_prepare_analysis_standalone_invocation,
    register_current_clinical_prepare_analysis_config,
)
from plugins.clinical_trial_doc.prepare_analysis import resolver as clinical_resolver
from plugins.clinical_trial_doc.privacy.registry.schemas import ClinicalProgramRecord
from privacy.config import PrivacyConfig
from runtime.prepare_analysis import (
    PrepareAnalysisExecutionContext,
    operations,
    run_prepare_analysis_operation,
)


def _bundle(text: str = "Protocol ACME-101 dated 2024-01-02.") -> dict[str, Any]:
    sentences = build_sentences(
        "C0001",
        "paragraph",
        raw_text=text,
        normalized_text=text,
    )
    return {
        "doc_id": "s3_doc",
        "file_hash": "sha256:" + "a" * 64,
        "file_name": "s3.docx",
        "source_type": "docx",
        "document_meta": {"language": "zh", "bundle_schema_version": "0.2.0"},
        "front_matter_blocks": [],
        "content_blocks": [
            {
                "block_id": "C0001",
                "kind": "paragraph",
                "raw_text": text,
                "normalized_text": text,
                "order": 1,
                "doc_order_index": 0,
                "source_ref": {
                    "source_type": "docx",
                    "locator_type": "paragraph",
                    "locator_payload": {"para_index": 0},
                },
                "sentences": [asdict(sentence) for sentence in sentences],
            }
        ],
        "table_blocks": [],
        "format_blocks": [],
    }


def _request_options(
    detectors: tuple[str, ...],
    date_shift: bool | None,
    *,
    program_id: str | None = "clinical_program_001",
) -> PrepareAnalysisRequestOptions:
    date_enabled = bool(detectors) if date_shift is None else date_shift
    registry_enabled = "registry" in detectors
    return PrepareAnalysisRequestOptions(
        ClinicalPreparePrivacyConfig(
            enabled=bool(detectors) or date_enabled,
            registry_enabled=registry_enabled,
            regex_rule_set_ref=(
                CLINICAL_REGEX_RULE_SET_ZH if "regex" in detectors else None
            ),
            uie_config_ref=(
                CLINICAL_UIE_CONFIG_ZH if "uie" in detectors else None
            ),
            date_shift_enabled=date_enabled,
            clinical_program_id=(
                program_id if registry_enabled else None
            ),
        )
    )


def _resolve(
    detectors: tuple[str, ...],
    date_shift: bool | None,
    *,
    program_id: str | None = "clinical_program_001",
):
    return CURRENT_CLINICAL_PREPARE_ANALYSIS_CONFIG.domain.resolve(  # type: ignore[attr-defined]
        config=CURRENT_CLINICAL_PREPARE_ANALYSIS_CONFIG,
        request_options=_request_options(
            detectors,
            date_shift,
            program_id=program_id,
        ),
    )


def _registry() -> PrepareAnalysisConfigRegistry:
    registry = PrepareAnalysisConfigRegistry()
    register_current_clinical_prepare_analysis_config(registry)
    return registry


def _fail_late_lookup(*_args, **_kwargs):
    raise AssertionError("clinical lookup occurred after plan resolution")


def test_step_contract_is_plan_only_and_has_no_clinical_import() -> None:
    signature = inspect.signature(prepare_analysis_bundle)
    assert set(signature.parameters) == {
        "bundle",
        "resolved_plan",
        "analysis_bundle_id",
    }
    source = BACKEND_ROOT / "steps" / "prepare_analysis.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    imports = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert not any(name.startswith("plugins.clinical_trial_doc") for name in imports)
    for raw_name in (
        "clinical_program_id",
        "privacy_config",
        "detector",
        "profile",
        "date_shift_offset_days",
    ):
        assert raw_name not in signature.parameters


def test_step_executes_resolved_plan_without_later_clinical_lookup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = _resolve(("registry", "regex"), False)
    monkeypatch.setattr(clinical_resolver, "get_clinical_program", _fail_late_lookup)
    monkeypatch.setattr(
        clinical_resolver,
        "export_clinical_registry_entries_for_program",
        _fail_late_lookup,
    )
    monkeypatch.setattr(clinical_resolver, "_uie_runtime_available", _fail_late_lookup)

    result = prepare_analysis_bundle(_bundle(), resolved_plan=plan)

    assert "clinical_program_id" not in result.analysis_bundle
    assert result.mask_result.detectors == ["registry", "regex"]


def test_document_language_does_not_select_installed_regex_rules() -> None:
    bundle = _bundle("Contact alice@example.com")
    bundle["document_meta"] = {"language": "en"}
    plan = _resolve(("regex",), False)

    result = prepare_analysis_bundle(bundle, resolved_plan=plan)

    analysis_text = result.analysis_bundle["content_blocks"][0]["analysis_text"]
    assert "alice@example.com" not in analysis_text
    assert result.mask_result.detectors == ["regex"]


def test_runtime_resolves_config_and_plan_once_then_passes_that_plan(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = _resolve((), False)
    resolve_calls: list[object] = []

    @dataclass(frozen=True)
    class _SpyDomain(PrepareAnalysisDomainConfiguration):
        def resolve(self, *, config, request_options):
            resolve_calls.append((config, request_options))
            return plan

    config_id = PrepareAnalysisConfigId("pacfg_s3_spy")
    registry = PrepareAnalysisConfigRegistry()
    registry.register(PrepareAnalysisConfig(config_id, _SpyDomain()))
    passed_plans: list[object] = []
    real_step = operations.prepare_analysis_bundle

    def _capture(bundle, *, resolved_plan, analysis_bundle_id=None):
        passed_plans.append(resolved_plan)
        return real_step(
            bundle,
            resolved_plan=resolved_plan,
            analysis_bundle_id=analysis_bundle_id,
        )

    monkeypatch.setattr(operations, "prepare_analysis_bundle", _capture)
    report = operations.run_prepare_analysis_operation(
        execution=PrepareAnalysisExecutionContext(tmp_path, persist=False),
        prepare_analysis_config_id=config_id,
        config_registry=registry,
        request_options=_request_options((), False),
        bundle=_bundle(),
    )

    assert report.status == "success"
    assert len(resolve_calls) == 1
    assert passed_plans == [plan]


def test_resolved_plan_composes_result_extension_validator() -> None:
    plan = _resolve((), False)
    calls: list[dict[str, Any]] = []

    class _ValidationSpy:
        def __getattr__(self, name):
            return getattr(plan, name)

        def validate_result_extension(self, payload):
            calls.append(dict(payload))
            plan.validate_result_extension(payload)

    result = prepare_analysis_bundle(_bundle(), resolved_plan=_ValidationSpy())

    assert calls == [result.analysis_bundle]
    assert "clinical_program_id" not in result.analysis_bundle


def test_canonical_runtime_uses_program_scoped_registry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _program(program_id: str, alias: str) -> ClinicalProgramRecord:
        return ClinicalProgramRecord(
            canonical_id=program_id,
            study_drugs=(),
            sponsor=AliasEntityRecord(
                canonical_id=f"{program_id}:sponsor",
                token=f"Sponsor_{program_id[-1]}",
                aliases=(alias,),
            ),
        )

    programs = {
        "program_a": _program("program_a", "ALIAS_ONLY_A"),
        "program_b": _program("program_b", "ALIAS_ONLY_B"),
    }
    monkeypatch.setattr(
        clinical_resolver,
        "get_clinical_program",
        lambda program_id: programs.get(program_id),
    )
    invocation = build_clinical_prepare_analysis_standalone_invocation(
        clinical_program_id="program_a",
        bundle=_bundle("ALIAS_ONLY_A and ALIAS_ONLY_B"),
        privacy_after_extract_detectors="registry",
        date_shift_explicit=False,
    )
    report = operations.run_prepare_analysis_operation(
        execution=PrepareAnalysisExecutionContext(tmp_path, persist=False),
        prepare_analysis_config_id=invocation.prepare_analysis_config_id,
        config_registry=invocation.config_registry,
        request_options=invocation.request_options,
        bundle=_bundle("ALIAS_ONLY_A and ALIAS_ONLY_B"),
        runtime_context_label=invocation.runtime_context_label,
    )

    text = report.documents[0].artifacts.analysis_bundle["content_blocks"][0][
        "analysis_text"
    ]
    assert "ALIAS_ONLY_A" not in text
    assert "ALIAS_ONLY_B" in text


@pytest.mark.parametrize(
    ("detectors", "date_shift"),
    [
        ((), False),
        (("registry", "regex"), None),
        ((), True),
        (("registry", "regex"), False),
    ],
    ids=["identity", "registry-regex", "dates-only", "mask-no-date"],
)
def test_standalone_adapter_matches_direct_canonical_execution(
    tmp_path: Path,
    detectors: tuple[str, ...],
    date_shift: bool | None,
) -> None:
    config = PrivacyConfig.default().with_transform_detectors(
        "after_extract", list(detectors)
    )
    invocation = build_clinical_prepare_analysis_standalone_invocation(
        clinical_program_id="clinical_program_001",
        bundle=_bundle(),
        privacy_config=config,
        date_shift_explicit=date_shift,
    )
    standalone = run_prepare_analysis_operation(
        execution=PrepareAnalysisExecutionContext(
            tmp_path, run_id="s3_parity", persist=False
        ),
        prepare_analysis_config_id=invocation.prepare_analysis_config_id,
        config_registry=invocation.config_registry,
        request_options=invocation.request_options,
        bundle=_bundle(),
        runtime_context_label=invocation.runtime_context_label,
    )
    canonical = operations.run_prepare_analysis_operation(
        execution=PrepareAnalysisExecutionContext(
            tmp_path, run_id="s3_parity", persist=False
        ),
        prepare_analysis_config_id=CURRENT_CLINICAL_PREPARE_ANALYSIS_CONFIG_ID,
        config_registry=_registry(),
        request_options=_request_options(detectors, date_shift),
        bundle=_bundle(),
    )

    standalone_document = standalone.documents[0]
    canonical_document = canonical.documents[0]
    assert standalone_document.artifacts.analysis_bundle == (
        canonical_document.artifacts.analysis_bundle
    )
    assert standalone_document.step_result.mask_result == (
        canonical_document.step_result.mask_result
    )


def test_generic_artifact_and_summary_paths_do_not_import_clinical_plugin() -> None:
    for relative in (
        Path("artifacts/prepare_analysis.py"),
        Path("runtime/run_summaries.py"),
    ):
        tree = ast.parse((BACKEND_ROOT / relative).read_text(encoding="utf-8"))
        imported = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        }
        assert not any(
            name.startswith("plugins.clinical_trial_doc") for name in imported
        )


def test_canonical_runtime_does_not_import_clinical_implementation() -> None:
    source = BACKEND_ROOT / "runtime/prepare_analysis/operations.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    imported = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert not any(name.startswith("plugins.clinical_trial_doc") for name in imported)
