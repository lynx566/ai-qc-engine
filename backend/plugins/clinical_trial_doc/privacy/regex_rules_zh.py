from __future__ import annotations

import re

from privacy.detectors.regex_detector import RegexRule

REGEX_RULES_ZH_VERSION = "0.1.1"

# ORR as an efficacy endpoint (e.g. "ORR 达 38.9%") must not match subject/record-id rules.
_RECORD_ID_TOKEN = (
    r"(?:ORR(?!\s*(?:达|达到|为|分别为))"
    r"|(?!ORR)[A-Za-z0-9-]{3,})"
)

CLINICAL_TRIAL_DOC_REGEX_RULES_ZH: list[RegexRule] = [
    (
        "OTHER_CCI",
        "regex",
        re.compile(
            r"(?<![A-Za-z0-9._%+-])"
            r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
            r"(?![A-Za-z0-9._%+-])"
        ),
    ),
    (
        "OTHER_CCI",
        "regex",
        re.compile(r"(?:\+?86[-\s]?)?1[3-9]\d{9}\b"),
    ),
    (
        "RECORD_ID",
        "regex",
        re.compile(r"\b\d{17}[\dXx]\b|\b\d{15}\b"),
    ),
    (
        "STUDY_ID",
        "regex",
        re.compile(r"\bNCT\d{8}\b", re.IGNORECASE),
    ),
    (
        "RECORD_ID",
        "regex",
        re.compile(r"(?:病例|病案)(?:编号|号|ID|Id|id)?[\s:：._-]*([A-Za-z0-9-]{4,})"),
    ),
    (
        "RECORD_ID",
        "regex",
        re.compile(
            r"(?:受试者|试验参与者|筛选|随机)(?:编号|号)?[\s:：._-]*"
            rf"({_RECORD_ID_TOKEN})",
            re.IGNORECASE,
        ),
    ),
    (
        "RECORD_ID",
        "regex",
        re.compile(r"编号[\s:：._-]*([A-Za-z0-9-]{3,})"),
    ),
]
