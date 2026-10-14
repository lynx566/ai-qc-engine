from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from plugins.clinical_trial_doc.VERSION import (
    CLINICAL_TRIAL_DOC_COMPONENT_VERSIONS,
    CLINICAL_TRIAL_DOC_PLUGIN_VERSION,
)
from plugins.clinical_trial_doc.privacy.profile import PRIVACY_PROFILE_VERSION
from plugins.clinical_trial_doc.privacy.regex_rules_zh import REGEX_RULES_ZH_VERSION
from plugins.clinical_trial_doc.privacy.uie_schema_zh import UIE_SCHEMA_ZH_VERSION
from plugins.clinical_trial_doc.privacy.registry import CLINICAL_REGISTRY_VERSION


def test_clinical_trial_doc_component_versions_are_0_1_0() -> None:
    assert CLINICAL_TRIAL_DOC_PLUGIN_VERSION == "0.1.0"
    assert PRIVACY_PROFILE_VERSION == "0.1.0"
    assert REGEX_RULES_ZH_VERSION == "0.1.1"
    assert UIE_SCHEMA_ZH_VERSION == "0.1.0"
    assert CLINICAL_REGISTRY_VERSION == "0.1.0"
    assert CLINICAL_TRIAL_DOC_COMPONENT_VERSIONS == {
        "privacy_profile": "0.1.0",
        "regex_rules_zh": "0.1.1",
        "uie_schema_zh": "0.1.0",
        "registry": "0.1.0",
    }
