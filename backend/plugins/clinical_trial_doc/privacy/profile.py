from __future__ import annotations

from privacy.profile import DEFAULT_DATE_SHIFT_OFFSET_DAYS, PrivacyProfile

from plugins.clinical_trial_doc.privacy.regex_rules_zh import (
    CLINICAL_TRIAL_DOC_REGEX_RULES_ZH,
)
from plugins.clinical_trial_doc.privacy.registry.export import (
    export_clinical_registry_entries,
)
from plugins.clinical_trial_doc.privacy.uie_schema_zh import (
    CLINICAL_TRIAL_DOC_UIE_GENERIC_TERM_DENYLIST,
    CLINICAL_TRIAL_DOC_UIE_SCHEMA_TO_ENTITY_TYPE_ZH,
)

PRIVACY_PROFILE_VERSION = "0.1.0"

CLINICAL_TOKEN_PREFIXES: dict[str, str] = {
    "SUBJECT": "Subject",
    "SITE": "Site",
    "STUDY_DRUG": "StudyDrug",
    "GENERIC_NAME": "GenericName",
    "TARGET": "Target",
    "INVESTIGATOR": "Investigator",
    "SPONSOR": "Sponsor",
    "RECORD_ID": "Record",
    "STUDY_ID": "Study",
    "OTHER_CCI": "CCI",
    "BACKGROUND_DRUG": "BackgroundDrug",
    "DOSE_LEVEL": "DoseLevel",
    "INDICATION": "Indication",
    "PROTOCOL_ID": "Protocol",
}

CLINICAL_TRIAL_DOC_PRIVACY_PROFILE = PrivacyProfile(
    entity_types_to_mask=frozenset(
        {
            "SUBJECT",
            "SITE",
            "STUDY_DRUG",
            "GENERIC_NAME",
            "TARGET",
            "PROTOCOL_ID",
            "PHASE",
            "INDICATION",
            "BACKGROUND_DRUG",
            "DOSE_LEVEL",
            "INVESTIGATOR",
            "SPONSOR",
            "RECORD_ID",
            "STUDY_ID",
            "OTHER_CCI",
        }
    ),
    entity_types_to_keep=frozenset(
        {
            "AE",
            "ADR",
            "SAE",
            "SAR",
            "SUSAR",
            "DOSE",
            "COUNT",
            "PERCENT",
            "DATE",
            "VISIT",
            "TREATMENT_GROUP",
        }
    ),
    date_shift_offset_days=DEFAULT_DATE_SHIFT_OFFSET_DAYS,
    regex_rules={"zh": tuple(CLINICAL_TRIAL_DOC_REGEX_RULES_ZH)},
    uie_schema_by_language={"zh": CLINICAL_TRIAL_DOC_UIE_SCHEMA_TO_ENTITY_TYPE_ZH},
    uie_denylist=frozenset(CLINICAL_TRIAL_DOC_UIE_GENERIC_TERM_DENYLIST),
    registry_entries=tuple(export_clinical_registry_entries()),
    token_prefixes=dict(CLINICAL_TOKEN_PREFIXES),
)
