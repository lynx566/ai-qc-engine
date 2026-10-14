from __future__ import annotations

from core.registry.alias import AliasEntityRecord

INDICATION_ADVANCED_SOLID_TUMOR = AliasEntityRecord(
    canonical_id="indication_001",
    token="Indication_001",
    aliases=(
        "晚期实体瘤",
        "advanced solid tumor",
        "advanced solid tumors",
    ),
)

INDICATION_NON_SQUAMOUS_NSCLC = AliasEntityRecord(
    canonical_id="indication_002",
    token="Indication_002",
    aliases=(
        "非鳞状非小细胞肺癌",
        "晚期非鳞状非小细胞肺癌",
        "晚期非鳞状 NSCLC",
        "晚期非鳞状NSCLC",
        "非鳞状 NSCLC",
        "非鳞状NSCLC",
        "advanced non-squamous non-small cell lung cancer",
        "non-squamous non-small cell lung cancer",
        "advanced non-squamous NSCLC",
        "non-squamous NSCLC",
    ),
)
