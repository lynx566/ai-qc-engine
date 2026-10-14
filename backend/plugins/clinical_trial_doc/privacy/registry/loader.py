from __future__ import annotations

import warnings

from plugins.clinical_trial_doc.privacy.registry.records import clinical_program_001
from plugins.clinical_trial_doc.privacy.registry.schemas import (
    ClinicalProgramRecord,
    StudyDrugRecord,
)


def load_clinical_registry() -> dict[str, ClinicalProgramRecord]:
    programs = [
        clinical_program_001.CLINICAL_PROGRAM,
    ]
    return {program.canonical_id: program for program in programs}


def get_clinical_program(clinical_program_id: str | None) -> ClinicalProgramRecord | None:
    """Return one program record by canonical id, or ``None`` when *clinical_program_id* is empty."""
    if clinical_program_id is None:
        return None
    program_id = clinical_program_id.strip()
    if not program_id:
        return None
    return load_clinical_registry().get(program_id)


def load_study_drug_registry() -> dict[str, StudyDrugRecord]:
    """Deprecated: use :func:`load_clinical_registry`."""
    warnings.warn(
        "load_study_drug_registry is deprecated; use load_clinical_registry",
        DeprecationWarning,
        stacklevel=2,
    )
    study_drugs: list[StudyDrugRecord] = []
    for program in load_clinical_registry().values():
        study_drugs.extend(program.study_drugs)
    return {study_drug.canonical_id: study_drug for study_drug in study_drugs}
