from __future__ import annotations

from dataclasses import dataclass

from core.registry.alias import AliasEntityRecord, ScopedAliasEntityRecord


@dataclass(frozen=True)
class ProtocolRecord:
    canonical_id: str
    token: str
    protocol_ids: tuple[str, ...]


@dataclass(frozen=True)
class StudyDrugRecord:
    """Registry record for a study drug and its maskable aliases."""

    canonical_id: str
    token: str
    drug_key: str

    aliases: tuple[str, ...]
    # True or proposed generic names only. Drug modality/class descriptions must
    # not be listed here — they are whole-span masked as GenericName_N. Modality
    # text should preserve structure and rely on target masking for embedded targets.
    generic_name_aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class ClinicalProgramRecord:
    canonical_id: str
    study_drugs: tuple[StudyDrugRecord, ...]
    sponsor: AliasEntityRecord | None = None
    targets: tuple[AliasEntityRecord, ...] = ()
    protocols: tuple[ProtocolRecord, ...] = ()
    indications: tuple[AliasEntityRecord, ...] = ()
    background_drugs: tuple[AliasEntityRecord, ...] = ()
    dose_levels: tuple[AliasEntityRecord, ...] = ()
    sites: tuple[AliasEntityRecord, ...] = ()
    investigators: tuple[AliasEntityRecord, ...] = ()
    subject_ids: tuple[ScopedAliasEntityRecord, ...] = ()
