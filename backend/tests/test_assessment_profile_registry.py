from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.assessment.profile import (
    CLINICAL_SAFETY_AGGREGATE_HEADING_SCOPE_ASSESSMENT_ZH_PROFILE,
    CLINICAL_SAFETY_AGGREGATE_HEADING_SCOPE_ASSESSMENT_ZH_PROFILE_NAME,
    ClinicalTrialDocAssessmentProfile,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.assessment.prompts.clinical_safety_aggregate_heading_scope_assessment_zh import (
    PROMPT_NAME as SCOPE_PROMPT_NAME,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.assessment.prompts.clinical_safety_aggregate_heading_scope_assessment_zh import (
    PROMPT_VERSION as SCOPE_PROMPT_VERSION,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.assessment.registry import (
    ASSESSMENT_PROFILE_REGISTRY,
    normalize_assessment_profile_name,
    resolve_clinical_trial_doc_assessment_profile,
)
_CANONICAL = CLINICAL_SAFETY_AGGREGATE_HEADING_SCOPE_ASSESSMENT_ZH_PROFILE_NAME
_RETIRED_PER_UNIT_PROFILE = "clinical_safety_aggregate_finding_zh"


def test_assessment_profile_registry_has_single_canonical_profile() -> None:
    assert set(ASSESSMENT_PROFILE_REGISTRY.keys()) == {_CANONICAL}
    profile = ASSESSMENT_PROFILE_REGISTRY[_CANONICAL]
    assert profile is CLINICAL_SAFETY_AGGREGATE_HEADING_SCOPE_ASSESSMENT_ZH_PROFILE
    assert isinstance(profile, ClinicalTrialDocAssessmentProfile)
    assert profile.prompt_name == SCOPE_PROMPT_NAME


def test_active_assessment_package_does_not_expose_tag_profile_type() -> None:
    import plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.assessment as active_assessment

    assert not hasattr(active_assessment, "ClinicalTrialDocTagProfile")
    assert hasattr(active_assessment, "ClinicalTrialDocAssessmentProfile")


def test_assessment_profile_registry_excludes_deprecated_aliases() -> None:
    assert "clinical_safety_scope_annotation_zh" not in ASSESSMENT_PROFILE_REGISTRY
    assert _RETIRED_PER_UNIT_PROFILE not in ASSESSMENT_PROFILE_REGISTRY


def test_normalize_assessment_profile_name_keeps_canonical_name() -> None:
    assert normalize_assessment_profile_name(_CANONICAL) == _CANONICAL


def test_normalize_assessment_profile_name_maps_scope_alias() -> None:
    assert (
        normalize_assessment_profile_name("clinical_safety_scope_annotation_zh")
        == _CANONICAL
    )


def test_normalize_assessment_profile_name_maps_aggregate_finding_alias() -> None:
    assert (
        normalize_assessment_profile_name(_RETIRED_PER_UNIT_PROFILE)
        == _CANONICAL
    )


def test_resolve_clinical_trial_doc_assessment_profile_for_canonical_name() -> None:
    profile = resolve_clinical_trial_doc_assessment_profile(_CANONICAL)
    assert profile.name == _CANONICAL
    assert profile.prompt_name == SCOPE_PROMPT_NAME


def test_runtime_default_assessment_profile_is_canonical() -> None:
    from runtime.assessment_registry import (
        ASSESSMENT_PROFILE_CHOICES,
        DEFAULT_ASSESSMENT_PROFILE,
    )

    assert DEFAULT_ASSESSMENT_PROFILE == _CANONICAL
    assert ASSESSMENT_PROFILE_CHOICES == (_CANONICAL,)


def test_prompt_identity_reset_for_new_family() -> None:
    assert SCOPE_PROMPT_NAME == _CANONICAL
    assert SCOPE_PROMPT_VERSION == "0.3.2"


def test_runtime_assessment_llm_choices_include_api() -> None:
    from runtime.assessment_registry import ASSESSMENT_LLM_CHOICES

    assert "mock" in ASSESSMENT_LLM_CHOICES
    assert "api" in ASSESSMENT_LLM_CHOICES


@pytest.mark.parametrize(
    ("alias", "phrase"),
    [
        (
            "clinical_safety_scope_annotation_zh",
            "deprecated ambiguous profile name",
        ),
        (
            _RETIRED_PER_UNIT_PROFILE,
            "retired per-unit profile name",
        ),
    ],
)
def test_runtime_resolve_assessment_profile_warns_for_aliases(
    capsys: pytest.CaptureFixture[str],
    alias: str,
    phrase: str,
) -> None:
    from runtime.assessment_registry import resolve_assessment_profile

    resolved = resolve_assessment_profile(alias)
    assert resolved == _CANONICAL
    captured = capsys.readouterr()
    assert "deprecated assessment profile alias" in captured.err
    assert phrase in captured.err
    assert _CANONICAL in captured.err
