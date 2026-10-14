from __future__ import annotations

from plugins.clinical_trial_doc.privacy.registry.records.clinical_program_001.background_drugs import (
    BACKGROUND_DRUG_CARBOPLATIN,
    BACKGROUND_DRUG_PEMETREXED,
)
from plugins.clinical_trial_doc.privacy.registry.records.clinical_program_001.dose_levels import (
    DOSE_LEVEL_001,
    DOSE_LEVEL_002,
    DOSE_LEVEL_003,
)
from plugins.clinical_trial_doc.privacy.registry.records.clinical_program_001.indications import (
    INDICATION_ADVANCED_SOLID_TUMOR,
    INDICATION_NON_SQUAMOUS_NSCLC,
)
from plugins.clinical_trial_doc.privacy.registry.records.clinical_program_001.investigators import (
    INVESTIGATOR_001,
)
from plugins.clinical_trial_doc.privacy.registry.records.clinical_program_001.protocols import (
    PROTOCOL_001,
    PROTOCOL_002,
)
from plugins.clinical_trial_doc.privacy.registry.records.clinical_program_001.sites import (
    SITE_001,
)
from plugins.clinical_trial_doc.privacy.registry.records.clinical_program_001.sponsor import (
    SPONSOR_001,
)
from plugins.clinical_trial_doc.privacy.registry.records.clinical_program_001.study_drugs import (
    STUDY_DRUG_001,
)
from plugins.clinical_trial_doc.privacy.registry.records.clinical_program_001.subject_ids import (
    SUBJECT_ID_001,
)
from plugins.clinical_trial_doc.privacy.registry.records.clinical_program_001.targets import (
    TARGET_CLASS_PD_1_PD_L1,
    TARGET_PD_L1,
)
from plugins.clinical_trial_doc.privacy.registry.schemas import ClinicalProgramRecord

CLINICAL_PROGRAM = ClinicalProgramRecord(
    canonical_id="clinical_program_001",
    sponsor=SPONSOR_001,
    study_drugs=(STUDY_DRUG_001,),
    targets=(TARGET_CLASS_PD_1_PD_L1, TARGET_PD_L1),
    protocols=(PROTOCOL_001, PROTOCOL_002),
    indications=(
        INDICATION_ADVANCED_SOLID_TUMOR,
        INDICATION_NON_SQUAMOUS_NSCLC,
    ),
    background_drugs=(
        BACKGROUND_DRUG_CARBOPLATIN,
        BACKGROUND_DRUG_PEMETREXED,
    ),
    dose_levels=(
        DOSE_LEVEL_001,
        DOSE_LEVEL_002,
        DOSE_LEVEL_003,
    ),
    sites=(SITE_001,),
    investigators=(INVESTIGATOR_001,),
    subject_ids=(SUBJECT_ID_001,),
)
