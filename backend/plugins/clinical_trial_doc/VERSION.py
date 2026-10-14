from __future__ import annotations

from plugins.clinical_trial_doc.privacy.profile import PRIVACY_PROFILE_VERSION
from plugins.clinical_trial_doc.privacy.regex_rules_zh import REGEX_RULES_ZH_VERSION
from plugins.clinical_trial_doc.privacy.uie_schema_zh import UIE_SCHEMA_ZH_VERSION
from plugins.clinical_trial_doc.privacy.registry import CLINICAL_REGISTRY_VERSION

CLINICAL_TRIAL_DOC_PLUGIN_VERSION = "0.1.0"

CLINICAL_TRIAL_DOC_COMPONENT_VERSIONS = {
    "privacy_profile": PRIVACY_PROFILE_VERSION,
    "regex_rules_zh": REGEX_RULES_ZH_VERSION,
    "uie_schema_zh": UIE_SCHEMA_ZH_VERSION,
    "registry": CLINICAL_REGISTRY_VERSION,
}
