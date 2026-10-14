from __future__ import annotations

from plugins.clinical_trial_doc.privacy.profile import CLINICAL_TRIAL_DOC_PRIVACY_PROFILE
from privacy.policy import filter_candidates_by_profile
from privacy.schemas import SensitiveEntityCandidate


def _candidate(entity_type: str) -> SensitiveEntityCandidate:
    return SensitiveEntityCandidate(
        original_text="x",
        entity_type=entity_type,  # type: ignore[arg-type]
        start=0,
        end=1,
        source="mock",
        confidence=1.0,
    )


def test_profile_drops_keep_types() -> None:
    profile = CLINICAL_TRIAL_DOC_PRIVACY_PROFILE
    candidates = [
        _candidate("SUBJECT"),
        _candidate("DATE"),
        _candidate("ADR"),
    ]
    filtered = filter_candidates_by_profile(
        candidates,
        entity_types_to_mask=profile.entity_types_to_mask,
        entity_types_to_keep=profile.entity_types_to_keep,
    )
    assert [c.entity_type for c in filtered] == ["SUBJECT"]


def test_profile_drops_unknown_types() -> None:
    profile = CLINICAL_TRIAL_DOC_PRIVACY_PROFILE
    filtered = filter_candidates_by_profile(
        [_candidate("UNKNOWN_TYPE")],
        entity_types_to_mask=profile.entity_types_to_mask,
        entity_types_to_keep=profile.entity_types_to_keep,
    )
    assert filtered == []
