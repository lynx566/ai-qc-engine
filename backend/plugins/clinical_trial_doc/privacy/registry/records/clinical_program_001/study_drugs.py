from __future__ import annotations

from plugins.clinical_trial_doc.privacy.registry.schemas import StudyDrugRecord

STUDY_DRUG_001 = StudyDrugRecord(
    canonical_id="study_drug_001",
    token="StudyDrug_001",
    drug_key="emetezumab",
    aliases=(
        "VT-8802",
        "VT8802",
        "艾美",
    ),
    generic_name_aliases=(
        "艾美妥珠单抗",
        "Emetuzumab",
    ),
)
