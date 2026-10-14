"""Standalone/dev composition for the canonical Prepare Analysis Runtime.

This module translates low-level developer invocation syntax into canonical
Runtime inputs.  Clinical registry, rule, detector, date, and provenance
semantics remain exclusively in the configured resolver.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from operations.prepare_analysis.contracts import (
    PrepareAnalysisConfigId,
    PrepareAnalysisRequestOptions,
)
from privacy.config import PrivacyConfig
from runtime.io import load_json
from runtime.prepare_analysis.context import infer_language_from_bundle

from plugins.clinical_trial_doc.prepare_analysis.config import (
    CURRENT_CLINICAL_PREPARE_ANALYSIS_CONFIG_ID,
    build_current_clinical_prepare_analysis_config_registry,
)
from plugins.clinical_trial_doc.prepare_analysis.inputs import (
    CLINICAL_REGEX_RULE_SET_ZH,
    CLINICAL_UIE_CONFIG_ZH,
    build_clinical_prepare_privacy_config,
    clinical_prepare_privacy_behaviors_selected,
    resolve_clinical_prepare_date_shift_enabled,
)
from operations.prepare_analysis.registry import PrepareAnalysisConfigRegistry

STANDALONE_RUNTIME_CONTEXT_LABEL = "clinical_trial_doc"


@dataclass(frozen=True, slots=True)
class ClinicalPrepareAnalysisStandaloneInvocation:
    """Canonical Runtime composition produced from standalone/debug inputs."""

    prepare_analysis_config_id: PrepareAnalysisConfigId
    config_registry: PrepareAnalysisConfigRegistry
    request_options: PrepareAnalysisRequestOptions
    runtime_context_label: str


def _resolve_language(
    *,
    language: str | None,
    bundle: Mapping[str, Any] | None,
    bundle_path: Path | str | None,
    bundle_dir: Path | str | None,
) -> str:
    if language:
        return language.lower()
    candidate: Mapping[str, Any] | None = bundle
    if candidate is None and bundle_path is not None:
        candidate = load_json(Path(bundle_path).resolve())
    if candidate is None and bundle_dir is not None:
        directory = Path(bundle_dir).resolve()
        direct = directory / "bundle.json"
        paths = (
            [direct]
            if direct.is_file()
            else sorted(
                path for path in directory.rglob("bundle.json") if path.is_file()
            )
        )
        if not paths:
            raise ValueError(f"no bundle.json under {directory}")
        candidate = load_json(paths[0])
    inferred = infer_language_from_bundle(dict(candidate)) if candidate else None
    if inferred:
        return inferred
    raise ValueError(
        "prepare_analysis requires --language or bundle document_meta.language"
    )


def build_clinical_prepare_analysis_standalone_invocation(
    *,
    clinical_program_id: str | None = None,
    language: str | None = None,
    bundle: Mapping[str, Any] | None = None,
    bundle_path: Path | str | None = None,
    bundle_dir: Path | str | None = None,
    privacy_after_extract_detectors: str | None = None,
    privacy_config: PrivacyConfig | None = None,
    date_shift_explicit: bool | None = None,
) -> ClinicalPrepareAnalysisStandaloneInvocation:
    """Translate standalone CLI flags into installed Prepare Analysis Runtime inputs."""

    program_id = str(clinical_program_id or "").strip() or None

    configured = privacy_config or PrivacyConfig.from_cli(
        after_extract=privacy_after_extract_detectors
    )
    if configured.transform_detectors("after_filter"):
        raise ValueError(
            "Prepare Analysis after_filter detectors are unsupported; "
            "remove the after_filter configuration"
        )
    detector_ids = tuple(configured.transform_detectors("after_extract"))
    unknown_detectors = sorted(set(detector_ids) - {"registry", "regex", "uie"})
    if unknown_detectors:
        raise ValueError(
            "unsupported standalone Prepare detector(s): "
            + ", ".join(unknown_detectors)
        )

    resolved_language = _resolve_language(
        language=language,
        bundle=bundle,
        bundle_path=bundle_path,
        bundle_dir=bundle_dir,
    )
    if resolved_language != "zh" and ({"regex", "uie"} & set(detector_ids)):
        raise ValueError(
            "standalone language shorthand has no installed regex/UIE selector: "
            f"{resolved_language!r}"
        )
    registry_enabled = "registry" in detector_ids
    regex_rule_set_ref = (
        CLINICAL_REGEX_RULE_SET_ZH if "regex" in detector_ids else None
    )
    uie_config_ref = CLINICAL_UIE_CONFIG_ZH if "uie" in detector_ids else None
    masking_behaviors_selected = clinical_prepare_privacy_behaviors_selected(
        registry_enabled=registry_enabled,
        regex_rule_set_ref=regex_rule_set_ref,
        uie_config_ref=uie_config_ref,
    )
    date_shift_enabled = resolve_clinical_prepare_date_shift_enabled(
        masking_behaviors_selected=masking_behaviors_selected,
        date_shift_explicit=date_shift_explicit,
    )
    if registry_enabled and not program_id:
        raise RuntimeError(
            "clinical_program_id must be set for registry masking "
            "(e.g. --clinical-program clinical_program_001)"
        )
    formal_privacy_config = build_clinical_prepare_privacy_config(
        registry_enabled=registry_enabled,
        regex_rule_set_ref=regex_rule_set_ref,
        uie_config_ref=uie_config_ref,
        date_shift_enabled=date_shift_enabled,
        clinical_program_id=program_id if registry_enabled else None,
    )

    return ClinicalPrepareAnalysisStandaloneInvocation(
        prepare_analysis_config_id=CURRENT_CLINICAL_PREPARE_ANALYSIS_CONFIG_ID,
        config_registry=build_current_clinical_prepare_analysis_config_registry(),
        request_options=PrepareAnalysisRequestOptions(
            privacy_config=formal_privacy_config
        ),
        runtime_context_label=STANDALONE_RUNTIME_CONTEXT_LABEL,
    )


__all__ = [
    "STANDALONE_RUNTIME_CONTEXT_LABEL",
    "ClinicalPrepareAnalysisStandaloneInvocation",
    "build_clinical_prepare_analysis_standalone_invocation",
]
