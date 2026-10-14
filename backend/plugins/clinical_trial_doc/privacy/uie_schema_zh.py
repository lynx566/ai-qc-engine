from __future__ import annotations

UIE_SCHEMA_ZH_VERSION = "0.1.0"

# UIE schema for clinical-trial zh documents.
#
# Rule: labels must describe concrete value fields, not role/generic terms.
#   good: 受试者姓名、研究中心名称、申办方名称
#   bad:  受试者、研究中心、申办方、试验药物
# STUDY_DRUG is handled by registry + regex by default — do not add to UIE schema.
# See privacy/README.md (under backend source root)
CLINICAL_TRIAL_DOC_UIE_SCHEMA_TO_ENTITY_TYPE_ZH = {
    "受试者姓名": "SUBJECT",
    "病历号": "RECORD_ID",
    "住院号": "RECORD_ID",
    "受试者编号": "RECORD_ID",
    "研究中心名称": "SITE",
    "研究者姓名": "INVESTIGATOR",
    "申办方名称": "SPONSOR",
    "研究编号": "STUDY_ID",
    "其他敏感信息": "OTHER_CCI",
}

# Generic role terms UIE may still over-extract; filter inside UIEDetector only.
CLINICAL_TRIAL_DOC_UIE_GENERIC_TERM_DENYLIST: frozenset[str] = frozenset(
    {
        "受试者",
        "试验参与者",
        "试验药",
        "试验药物",
        "研究药物",
        "试验用药品",
        "本品",
        "该药",
        "研究中心",
        "研究者",
        "申办方",
    }
)
