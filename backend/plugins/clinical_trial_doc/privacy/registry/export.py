from __future__ import annotations

import warnings

from core.registry.alias import AliasEntityRecord, ScopedAliasEntityRecord
from plugins.clinical_trial_doc.privacy.registry.loader import load_clinical_registry
from plugins.clinical_trial_doc.privacy.registry.schemas import (
    ClinicalProgramRecord,
    StudyDrugRecord,
)
from privacy.detectors.registry_detector import RegistryEntry


def _non_empty_aliases(aliases: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(alias.strip() for alias in aliases if alias and alias.strip())


def _registry_entry(
    *,
    entity_type: str,
    canonical_id: str,
    token: str,
    aliases: tuple[str, ...],
    parent_canonical_id: str | None = None,
) -> RegistryEntry | None:
    cleaned = _non_empty_aliases(aliases)
    if not cleaned:
        return None
    return RegistryEntry(
        entity_type=entity_type,  # type: ignore[arg-type]
        canonical_id=canonical_id,
        token=token,
        aliases=cleaned,
        parent_canonical_id=parent_canonical_id,
    )


def _generic_name_token(study_drug: StudyDrugRecord) -> str:
    suffix = study_drug.canonical_id.removeprefix("study_drug_") or "001"
    return f"GenericName_{suffix}"


def _entry_from_alias_record(
    entity_type: str,
    record: AliasEntityRecord,
) -> RegistryEntry | None:
    return _registry_entry(
        entity_type=entity_type,
        canonical_id=record.canonical_id,
        token=record.token,
        aliases=record.aliases,
    )


def _entry_from_scoped_record(
    entity_type: str,
    record: ScopedAliasEntityRecord,
) -> RegistryEntry | None:
    return _registry_entry(
        entity_type=entity_type,
        canonical_id=record.canonical_id,
        token=record.token,
        aliases=record.aliases,
        parent_canonical_id=record.parent_canonical_id,
    )


def _append_program_alias_entities(
    entries: list[RegistryEntry],
    program: ClinicalProgramRecord,
) -> None:
    for indication in program.indications:
        if entry := _entry_from_alias_record("INDICATION", indication):
            entries.append(entry)

    for background_drug in program.background_drugs:
        if entry := _entry_from_alias_record("BACKGROUND_DRUG", background_drug):
            entries.append(entry)

    for dose_level in program.dose_levels:
        if entry := _entry_from_alias_record("DOSE_LEVEL", dose_level):
            entries.append(entry)

    for site in program.sites:
        if entry := _entry_from_alias_record("SITE", site):
            entries.append(entry)

    for investigator in program.investigators:
        if entry := _entry_from_alias_record("INVESTIGATOR", investigator):
            entries.append(entry)

    for subject_id in program.subject_ids:
        if entry := _entry_from_scoped_record("RECORD_ID", subject_id):
            entries.append(entry)


def export_clinical_registry_entries_for_program(
    program: ClinicalProgramRecord,
) -> tuple[RegistryEntry, ...]:
    """Export neutral detector entries for exactly one clinical Program."""

    if not isinstance(program, ClinicalProgramRecord):
        raise TypeError("program must be a ClinicalProgramRecord")
    entries: list[RegistryEntry] = []

    for study_drug in program.study_drugs:
        if entry := _registry_entry(
            entity_type="STUDY_DRUG",
            canonical_id=study_drug.canonical_id,
            token=study_drug.token,
            aliases=study_drug.aliases,
        ):
            entries.append(entry)

        if entry := _registry_entry(
            entity_type="GENERIC_NAME",
            canonical_id=f"{study_drug.canonical_id}:generic_name",
            token=_generic_name_token(study_drug),
            aliases=study_drug.generic_name_aliases,
        ):
            entries.append(entry)

    if program.sponsor:
        if entry := _entry_from_alias_record("SPONSOR", program.sponsor):
            entries.append(entry)

    for target in program.targets:
        if entry := _entry_from_alias_record("TARGET", target):
            entries.append(entry)

    _append_program_alias_entities(entries, program)

    for protocol in program.protocols:
        if entry := _registry_entry(
            entity_type="PROTOCOL_ID",
            canonical_id=protocol.canonical_id,
            token=protocol.token,
            aliases=protocol.protocol_ids,
        ):
            entries.append(entry)

    return tuple(entries)


def export_clinical_registry_entries() -> list[RegistryEntry]:
    """Legacy profile-wide flattening retained until the production cutover."""

    entries: list[RegistryEntry] = []
    for program in load_clinical_registry().values():
        entries.extend(export_clinical_registry_entries_for_program(program))

    return entries


def export_study_drug_registry_entries() -> list[RegistryEntry]:
    """Deprecated: use :func:`export_clinical_registry_entries`."""
    warnings.warn(
        "export_study_drug_registry_entries is deprecated; "
        "use export_clinical_registry_entries",
        DeprecationWarning,
        stacklevel=2,
    )
    return export_clinical_registry_entries()
