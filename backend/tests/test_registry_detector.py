from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from privacy.detectors.registry_detector import RegistryDetector, RegistryEntry


def test_registry_detector_vt8802_study_drug_with_stable_token() -> None:
    entry = RegistryEntry(
        entity_type="STUDY_DRUG",
        canonical_id="study_drug_001",
        token="StudyDrug_001",
        aliases=("VT-8802",),
    )
    detector = RegistryDetector([entry])
    text = "药物 VT-8802 总体耐受性良好。"
    candidates = detector.detect(text)

    assert len(candidates) == 1
    hit = candidates[0]
    assert hit.entity_type == "STUDY_DRUG"
    assert hit.original_text == "VT-8802"
    assert hit.source == "registry"
    assert hit.confidence == 1.0
    assert hit.canonical_id == "study_drug_001"
    assert hit.predefined_token == "StudyDrug_001"
    assert hit.parent_canonical_id is None


def test_registry_detector_scoped_subject_id_carries_parent() -> None:
    entry = RegistryEntry(
        entity_type="RECORD_ID",
        canonical_id="protocol_001:subject_id_001",
        token="SubjectId_001",
        aliases=("SCR-001",),
        parent_canonical_id="protocol_001",
    )
    detector = RegistryDetector([entry])
    text = "筛选SCR-001入组。"
    hit = detector.detect(text)[0]
    assert hit.entity_type == "RECORD_ID"
    assert hit.canonical_id == "protocol_001:subject_id_001"
    assert hit.predefined_token == "SubjectId_001"
    assert hit.parent_canonical_id == "protocol_001"
