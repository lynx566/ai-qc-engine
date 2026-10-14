from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from plugins.clinical_trial_doc.privacy.profile import (
    CLINICAL_TRIAL_DOC_PRIVACY_PROFILE,
)
from plugins.clinical_trial_doc.privacy.regex_rules_zh import (
    CLINICAL_TRIAL_DOC_REGEX_RULES_ZH,
)
from plugins.clinical_trial_doc.privacy.uie_schema_zh import (
    CLINICAL_TRIAL_DOC_UIE_GENERIC_TERM_DENYLIST,
)
from privacy.detectors.composite import CompositeDetector
from privacy.detectors.regex_detector import RegexDetector
from privacy.detectors.uie_filters import filter_uie_denied_terms
from privacy.document_transform import run
from privacy.schemas import SensitiveEntityCandidate


class SimulatedUIEDetector:
    """Stand-in for UIEDetector when paddlenlp is unavailable."""

    def __init__(
        self,
        *,
        raw_candidates: list[SensitiveEntityCandidate],
        denylist=frozenset(CLINICAL_TRIAL_DOC_UIE_GENERIC_TERM_DENYLIST),
    ) -> None:
        self._raw_candidates = raw_candidates
        self._denylist = denylist

    def detect(self, text: str) -> list[SensitiveEntityCandidate]:
        matched = [c for c in self._raw_candidates if text[c.start : c.end] == c.original_text]
        return filter_uie_denied_terms(matched, self._denylist)


def _clinical_composite(*, uie_raw: list[SensitiveEntityCandidate]) -> CompositeDetector:
    return CompositeDetector(
        detectors=[
            RegexDetector(rules=CLINICAL_TRIAL_DOC_REGEX_RULES_ZH),
            SimulatedUIEDetector(raw_candidates=uie_raw),
        ]
    )


def _candidate(
    text: str,
    term: str,
    entity_type: str,
    *,
    source: str = "uie",
    confidence: float = 0.95,
) -> SensitiveEntityCandidate:
    start = text.index(term)
    return SensitiveEntityCandidate(
        original_text=term,
        entity_type=entity_type,  # type: ignore[arg-type]
        start=start,
        end=start + len(term),
        source=source,
        confidence=confidence,
    )


def _mask_block(text: str, *, uie_raw: list[SensitiveEntityCandidate]):
    detector = _clinical_composite(uie_raw=uie_raw)
    result = run(
        doc_id="test_doc",
        blocks=[{"block_id": "B0001", "text": text}],
        detector=detector,
        profile=CLINICAL_TRIAL_DOC_PRIVACY_PROFILE,
    )
    return result.masked_blocks[0]


def test_uie_denylist_drops_generic_role_terms() -> None:
    text = "在既往研究中，试验药物总体耐受性良好。"
    denied = _candidate(text, "试验药物", "STUDY_DRUG")
    kept = filter_uie_denied_terms([denied], CLINICAL_TRIAL_DOC_UIE_GENERIC_TERM_DENYLIST)
    assert kept == []


def test_generic_study_drug_term_is_not_masked() -> None:
    text = "在既往研究中，试验药物总体耐受性良好。"
    uie_raw = [_candidate(text, "试验药物", "STUDY_DRUG")]
    block = _mask_block(text, uie_raw=uie_raw)
    assert block.masked_text == text
    assert block.mask_hits == []


def test_subject_id_maps_to_record_id_not_subject() -> None:
    text = "试验参与者编号：SUBJ-001"
    block = _mask_block(text, uie_raw=[])
    assert len(block.mask_hits) == 1
    hit = block.mask_hits[0]
    assert hit.entity_type == "RECORD_ID"
    assert hit.original_text == "SUBJ-001"
    assert hit.source == "regex"


def test_subject_name_maps_to_subject_via_uie() -> None:
    text = "试验参与者姓名：王六"
    uie_raw = [_candidate(text, "王六", "SUBJECT")]
    block = _mask_block(text, uie_raw=uie_raw)
    assert len(block.mask_hits) == 1
    hit = block.mask_hits[0]
    assert hit.entity_type == "SUBJECT"
    assert hit.original_text == "王六"
    assert hit.source == "uie"


def test_investigator_name_maps_to_investigator_via_uie() -> None:
    text = "研究者姓名：王五"
    uie_raw = [_candidate(text, "王五", "INVESTIGATOR")]
    block = _mask_block(text, uie_raw=uie_raw)
    assert len(block.mask_hits) == 1
    hit = block.mask_hits[0]
    assert hit.entity_type == "INVESTIGATOR"
    assert hit.original_text == "王五"
    assert hit.source == "uie"


def test_study_id_still_masked_by_regex() -> None:
    text = "Trial NCT12345678 registered."
    block = _mask_block(text, uie_raw=[])
    assert len(block.mask_hits) == 1
    hit = block.mask_hits[0]
    assert hit.entity_type == "STUDY_ID"
    assert hit.original_text == "NCT12345678"
    assert hit.source == "regex"


def _regex_record_id_hits(text: str) -> list[SensitiveEntityCandidate]:
    detector = RegexDetector(rules=CLINICAL_TRIAL_DOC_REGEX_RULES_ZH)
    return [hit for hit in detector.detect(text) if hit.entity_type == "RECORD_ID"]


def _record_id_values(text: str) -> list[str]:
    return [hit.original_text for hit in _regex_record_id_hits(text)]


def test_orr_efficacy_with_space_is_not_record_id() -> None:
    text = "可评价试验参与者 ORR 达 38.9%"
    assert _record_id_values(text) == []


def test_orr_efficacy_without_space_is_not_record_id() -> None:
    text = "试验参与者 ORR为38.9%"
    assert _record_id_values(text) == []


def test_subject_alpha_token_still_record_id() -> None:
    text = "受试者 ABCD 于给药后出现发热"
    assert "ABCD" in _record_id_values(text)


def test_subject_number_orr_still_record_id() -> None:
    text = "受试者编号 ORR"
    assert "ORR" in _record_id_values(text)


def test_subject_hyphenated_id_still_record_id() -> None:
    text = "受试者 ABC-001 于第 8 天退出研究"
    assert "ABC-001" in _record_id_values(text)
